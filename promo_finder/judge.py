"""Judge stage: score built clips 1–5 on hook, cliff, standalone, trope pull and pacing (TECH_SPEC §4.5).

Pipeline position: stage 4, after build.py and before rank.py. Each call sees a small batch of clips as
the exact script lines inside their segments (what a viewer sees), with the first 3 seconds marked.
The judge returns scores, reasons and flags only; it never sees or writes anything that moves a cut.
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Callable, Literal

from pydantic import BaseModel, Field

from promo_finder.build import EPS, Candidate
from promo_finder.compact import compact_block
from promo_finder.llm import call_llm, load_prompt
from promo_finder.parse import Episode

log = logging.getLogger(__name__)

RiskFlag = Literal["needs_context", "cliff_may_resolve", "graphic_violence", "slow_middle", "confusing_cut"]
DIMENSIONS = ("hook", "cliff", "standalone", "trope_pull", "pacing")


class ClipScore(BaseModel):
    id: str
    hook_text: str
    cliff_text: str
    reasons: str                    # before the numbers, so the model reasons first
    hook: int = Field(ge=1, le=5)
    cliff: int = Field(ge=1, le=5)
    standalone: int = Field(ge=1, le=5)
    trope_pull: int = Field(ge=1, le=5)
    pacing: int = Field(ge=1, le=5)
    why: str
    risk_flags: list[RiskFlag] = Field(default_factory=list)


class JudgeBatch(BaseModel):
    scores: list[ClipScore]


def excerpt(cand: Candidate, episodes: dict[int, Episode], hook_window_s: float = 3.0) -> str:
    """The clip as the viewer gets it: full compact lines of every block that starts inside a segment.

    Lines starting in the first `hook_window_s` seconds of the clip get a `>>` mark, so the judge scores
    the actual opening rather than the best line anywhere in the clip.
    """
    clip_start = cand.segments[0].start
    lines = [f"CLIP {cand.id} · {cand.type} · {cand.total_s:.1f} s"]
    for i, seg in enumerate(cand.segments):
        if i:
            lines.append("--- CUT ---")
        for block in episodes[seg.ep].blocks:
            if seg.start - EPS <= block.start < seg.end - EPS:
                mark = ">> " if i == 0 and block.start < clip_start + hook_window_s - EPS else ""
                lines.append(mark + compact_block(block))
    return "\n".join(lines)


def editor_context(cand: Candidate, episodes: dict[int, Episode]) -> str:
    eps = sorted({s.ep for s in cand.segments})
    return "\n".join(f"Editor context, viewer does NOT see this. Episode {n} logline: {episodes[n].logline}" for n in eps)


def build_messages(batch: list[Candidate], episodes: dict[int, Episode], hook_window_s: float = 3.0) -> list[dict]:
    _version, sections = load_prompt("judge")
    clips = "\n\n".join(editor_context(c, episodes) + "\n" + excerpt(c, episodes, hook_window_s) for c in batch)
    # str.replace, not str.format: script text can contain braces.
    user = sections["user"].replace("{count}", str(len(batch))).replace("{clips}", clips)
    return [{"role": "system", "content": sections["system"]}, {"role": "user", "content": user}]


def _judge_batch(batch: list[Candidate], episodes: dict[int, Episode], cfg: dict, usage: list[dict],
                 raw_path: Path | None, completion_fn: Callable | None) -> dict[str, ClipScore]:
    version, _ = load_prompt("judge")
    hook_window = cfg.get("build", {}).get("hook_max_offset_s", 3.0)
    result, raw = call_llm("judge", build_messages(batch, episodes, hook_window), JudgeBatch, cfg, version, usage,
                           completion_fn=completion_fn)
    if raw_path is not None:
        raw_path.parent.mkdir(parents=True, exist_ok=True)
        raw_path.write_text(raw, encoding="utf-8")   # unedited
    wanted = {c.id for c in batch}
    # First score per wanted id wins; unknown ids (a model inventing or mangling one) are ignored.
    scores: dict[str, ClipScore] = {}
    for s in result.scores:
        if s.id in wanted and s.id not in scores:
            scores[s.id] = s
    return scores


def judge_candidates(cands: list[Candidate], episodes: dict[int, Episode], cfg: dict, usage: list[dict],
                     raw_dir: Path | None = None, completion_fn: Callable | None = None
                     ) -> tuple[dict[str, ClipScore], list[dict]]:
    """Score all candidates in batches. Returns (scores by candidate id, errors).

    A clip the batch reply skipped is retried once on its own; a batch that fails outright is retried
    clip by clip, so one bad clip can't sink its neighbours. Anything still unscored is reported, not guessed.
    """
    size = max(1, int(cfg.get("judge", {}).get("batch_size", 3)))
    scores: dict[str, ClipScore] = {}
    errors: list[dict] = []
    retry: list[Candidate] = []
    for n, start in enumerate(range(0, len(cands), size), 1):
        batch = cands[start:start + size]
        raw_path = raw_dir / f"batch_{n:03d}.json" if raw_dir else None
        try:
            got = _judge_batch(batch, episodes, cfg, usage, raw_path, completion_fn)
        except Exception as error:
            log.warning("judge batch %d failed (%s); retrying its clips one by one", n, type(error).__name__)
            errors.append({"batch": n, "ids": [c.id for c in batch], "error": f"{type(error).__name__}: {error}"[:300]})
            retry += batch
            continue
        scores.update(got)
        retry += [c for c in batch if c.id not in got]
    for c in retry:
        raw_path = raw_dir / f"single_{c.id}.json" if raw_dir else None
        try:
            scores.update(_judge_batch([c], episodes, cfg, usage, raw_path, completion_fn))
        except Exception as error:
            errors.append({"id": c.id, "error": f"{type(error).__name__}: {error}"[:300]})
            continue
        if c.id not in scores:
            errors.append({"id": c.id, "error": "unscored after a single-clip retry"})
    return scores, errors
