"""Cross-episode arc promos: open on one episode's hook, close on another episode's cliff (TECH_SPEC §4.4).

Pipeline position: between build.py and judge.py. One LLM call sees every episode's logline and the
built single-episode candidates (ID, beat type, hook/cliff summaries) and pairs them up by candidate ID
only. Code then cuts both parts on shot boundaries (segment 1 keeps the hook, segment 2 ends on the
cliff), checks 20–60 s, and the arc is judged and ranked like any other promo (D-039).
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Callable

from pydantic import BaseModel, Field

from promo_finder.build import (EPS, Candidate, Segment, _block_at_end, _block_at_start, _dialogue_starts_in,
                                _inside_dialogue, _shots)
from promo_finder.llm import call_llm, load_prompt
from promo_finder.parse import Episode

log = logging.getLogger(__name__)


class ArcPick(BaseModel):
    reasoning: str
    opener: str           # candidate ID whose opening (hook) starts the arc
    closer: str           # candidate ID whose ending (cliff) ends the arc
    hook_summary: str
    cliff_summary: str


class ArcProposals(BaseModel):
    arcs: list[ArcPick] = Field(default_factory=list, max_length=8)


def candidate_line(c: Candidate) -> str:
    return f"{c.id} | episode {c.ep} | {c.beat_type} | opens: {c.hook_summary} | ends: {c.cliff_summary}"


def build_messages(cands: list[Candidate], episodes: dict[int, Episode], logline_max_chars: int = 160) -> list[dict]:
    _version, sections = load_prompt("arc")
    eps = sorted({c.ep for c in cands})
    # Loglines only for episodes that have candidates, shortened: keeps one call under 8k tokens/minute.
    loglines = "\n".join(f"E{n:02d}: {episodes[n].logline[:logline_max_chars]}" for n in eps)
    user = (sections["user"].replace("{loglines}", loglines)
            .replace("{candidates}", "\n".join(candidate_line(c) for c in cands)))
    return [{"role": "system", "content": sections["system"]}, {"role": "user", "content": user}]


def _opening_part(ep: Episode, cand: Candidate, bcfg: dict) -> tuple[float, float] | None:
    """Segment 1: the opener's start through the first clean shot end at least `arc_seg1_min_s` in,
    after the hook line has finished, and at most `jumpcut_s1_max_s` long."""
    start = cand.segments[0].start
    hook = next(b for b in ep.blocks if b.id == cand.hook_block)
    lo = max(hook.end, start + bcfg.get("arc_seg1_min_s", 8.0))
    hi = min(start + bcfg["jumpcut_s1_max_s"], cand.segments[0].end)
    ends = sorted({s.end for s in _shots(ep) if lo - EPS <= s.end <= hi + EPS and not _inside_dialogue(ep, s.end)})
    return (start, ends[0]) if ends else None


def _closing_part(ep: Episode, cand: Candidate, budget_s: float, bcfg: dict) -> tuple[float, float] | None:
    """Segment 2: from the earliest clean shot start that fits the time budget through the closer's end.
    It must keep the whole cliff line and be at least `arc_min_segment_s` long."""
    end = cand.segments[-1].end
    cliff = next(b for b in ep.blocks if b.id == cand.cliff_block)
    earliest = cand.segments[-1].start
    for s2 in sorted({s.start for s in _shots(ep) if earliest - EPS <= s.start <= cliff.start + EPS}):
        if end - s2 > budget_s + EPS or _inside_dialogue(ep, s2):
            continue
        if end - s2 < bcfg["arc_min_segment_s"] - EPS:
            return None
        return s2, end
    return None


def build_arc(k: int, pick: ArcPick, by_id: dict[str, Candidate], episodes: dict[int, Episode],
              bcfg: dict) -> Candidate | dict:
    """One model pick -> an arc Candidate, or a rejection dict with the reason."""
    rejected = {"k": k, "pick": pick.model_dump()}
    if pick.opener not in by_id or pick.closer not in by_id:
        return {**rejected, "reason": "unknown_candidate"}
    a, b = by_id[pick.opener], by_id[pick.closer]
    if a.ep == b.ep:
        return {**rejected, "reason": "same_episode"}
    ep_a, ep_b = episodes[a.ep], episodes[b.ep]
    seg1 = _opening_part(ep_a, a, bcfg)
    if seg1 is None:
        return {**rejected, "reason": "no_clean_opening_cut"}
    seg2 = _closing_part(ep_b, b, bcfg["jumpcut_target_max_s"] - (seg1[1] - seg1[0]), bcfg)
    if seg2 is None:
        return {**rejected, "reason": "no_clean_closing_cut"}
    total = round((seg1[1] - seg1[0]) + (seg2[1] - seg2[0]), 3)
    if not bcfg["min_duration_s"] - EPS <= total <= bcfg["max_duration_s"] + EPS:
        return {**rejected, "reason": "duration", "total_s": total}
    shot_starts = {(n, round(s.start, 3)) for n, e in ((a.ep, ep_a), (b.ep, ep_b)) for s in _shots(e)}
    shot_ends = {(n, round(s.end, 3)) for n, e in ((a.ep, ep_a), (b.ep, ep_b)) for s in _shots(e)}
    hook = next(x for x in ep_a.blocks if x.id == a.hook_block)
    cliff = next(x for x in ep_b.blocks if x.id == b.cliff_block)
    checks = {
        "dur_ok": True,
        "hook_within_3s": 0 - EPS <= hook.start - seg1[0] <= bcfg["hook_max_offset_s"] + EPS,
        "starts_on_shot": (a.ep, round(seg1[0], 3)) in shot_starts and (b.ep, round(seg2[0], 3)) in shot_starts,
        "ends_on_shot": (a.ep, round(seg1[1], 3)) in shot_ends and (b.ep, round(seg2[1], 3)) in shot_ends,
        "no_dialogue_after_cliff": not _dialogue_starts_in(ep_b, cliff.end, seg2[1]),
        "segments_ordered": True,
    }
    return Candidate(
        id=f"ARC-{k}", ep=a.ep, type="arc",
        segments=[Segment(ep=a.ep, start=seg1[0], end=seg1[1], start_block=_block_at_start(ep_a, seg1[0]),
                          end_block=_block_at_end(ep_a, seg1[1])),
                  Segment(ep=b.ep, start=seg2[0], end=seg2[1], start_block=_block_at_start(ep_b, seg2[0]),
                          end_block=_block_at_end(ep_b, seg2[1]))],
        hook_block=a.hook_block, cliff_block=b.cliff_block, start_block=a.start_block, end_block=b.end_block,
        beat_type=a.beat_type, hook_summary=pick.hook_summary, cliff_summary=pick.cliff_summary,
        reasoning=pick.reasoning, flags=sorted(set(a.flags) & {"midshot_start"} | set(b.flags) & {"midshot_end"}),
        checks=checks, hook_offset_s=round(hook.start - seg1[0], 3), total_s=total)


def propose_arcs(cands: list[Candidate], episodes: dict[int, Episode], cfg: dict, usage: list[dict],
                 raw_path: Path | None = None, completion_fn: Callable | None = None
                 ) -> tuple[list[Candidate], list[dict]]:
    """Returns (built arcs, rejected picks). Needs candidates from at least two episodes."""
    if len({c.ep for c in cands}) < 2:
        return [], []
    version, _ = load_prompt("arc")
    picks, raw = call_llm("arc", build_messages(cands, episodes), ArcProposals, cfg, version, usage,
                          completion_fn=completion_fn)
    if raw_path is not None:
        raw_path.parent.mkdir(parents=True, exist_ok=True)
        raw_path.write_text(raw, encoding="utf-8")   # unedited
    by_id = {c.id: c for c in cands}
    arcs, rejected = [], []
    for k, pick in enumerate(picks.arcs, 1):
        result = build_arc(k, pick, by_id, episodes, cfg["build"])
        (arcs if isinstance(result, Candidate) else rejected).append(result)
    log.info("arcs: %d picked, %d built, %d rejected", len(picks.arcs), len(arcs), len(rejected))
    return arcs, rejected
