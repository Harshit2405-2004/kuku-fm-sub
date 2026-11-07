"""Cut builder: turn proposed block IDs into real, checked clips (pure code, no LLM).

Pipeline position: stage 3, between propose.py and judge.py. IDs → times, start snapped to a camera
shot so the hook lands in the first 3 s, end snapped to a shot without leaking the next line, then
the 20–60 s rule (single cut, jump-cut, or extend/reject) and dedupe. TECH_SPEC §4.3, D-004, D-015.
Worked examples with exact numbers: docs/PROCESS_GUIDE.md Process 3 (all are unit tests).
"""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel

from promo_finder.parse import Block, Episode

EPS = 1e-6   # float tolerance for comparing times like 60.0 or 3.0 at the boundary


class Segment(BaseModel):
    ep: int
    start: float
    end: float
    start_block: str
    end_block: str


class Candidate(BaseModel):
    id: str                      # P03-1, or ARC-1 for cross-episode promos
    ep: int                      # episode of the hook (segment 1)
    type: Literal["single", "jumpcut", "arc"]
    segments: list[Segment]
    hook_block: str
    cliff_block: str
    start_block: str             # as proposed (informational: the cut is computed from hook and cliff)
    end_block: str
    beat_type: str
    hook_summary: str
    cliff_summary: str
    reasoning: str
    flags: list[str]
    checks: dict[str, bool]
    hook_offset_s: float
    total_s: float


class Rejected(BaseModel):
    ep: int
    k: int
    reason: str                  # unknown_block, bad_order, too_short, cliff_segment_too_long
    proposal: dict
    detail: dict = {}


# --- small helpers over one episode's blocks

def _shots(ep: Episode) -> list[Block]:
    # Sorted by time, not file order: real scripts list a line before the shot it sits under.
    return sorted((b for b in ep.blocks if b.type == "CAMERA"), key=lambda b: (b.start, b.end))


def _dialogue_starts_in(ep: Episode, after: float, up_to: float) -> bool:
    """Does any spoken line start in (after, up_to]? If so, cutting at up_to would leak it."""
    return any(b.type == "DIALOGUE" and after + EPS < b.start <= up_to + EPS for b in ep.blocks)


def _inside_dialogue(ep: Episode, t: float) -> bool:
    return any(b.type == "DIALOGUE" and b.start + EPS < t < b.end - EPS for b in ep.blocks)


def _block_at_start(ep: Episode, t: float) -> str:
    shot = next((b for b in _shots(ep) if abs(b.start - t) < EPS), None)
    if shot:
        return shot.id
    covering = [b for b in ep.blocks if b.start - EPS <= t < b.end]
    return covering[0].id if covering else min(ep.blocks, key=lambda b: abs(b.start - t)).id


def _block_at_end(ep: Episode, t: float) -> str:
    shot = next((b for b in _shots(ep) if abs(b.end - t) < EPS), None)
    if shot:
        return shot.id
    covering = [b for b in ep.blocks if b.start < t <= b.end + EPS]
    return covering[0].id if covering else min(ep.blocks, key=lambda b: abs(b.end - t)).id


def interval_iou(a: tuple[float, float], b: tuple[float, float]) -> float:
    overlap = max(0.0, min(a[1], b[1]) - max(a[0], b[0]))
    union = max(a[1], b[1]) - min(a[0], b[0])
    return overlap / union if union > 0 else 0.0


# --- snapping (TECH_SPEC §4.3 steps 2–3)

def snap_start(ep: Episode, t_hook: float, bcfg: dict) -> tuple[float, list[str]]:
    """Start on a shot boundary with about 1 s of lead-in before the hook, never more than 3 s."""
    target = t_hook - bcfg["lead_in_target_s"]
    window = [s.start for s in _shots(ep) if t_hook - bcfg["lead_in_window_s"] - EPS <= s.start <= t_hook + EPS]
    if window:
        # Closest to the target; on a tie the earlier shot wins (more lead-in), D-024.
        return min(window, key=lambda s: (round(abs(s - target), 6), s)), []
    containing = [s.start for s in _shots(ep) if s.start <= t_hook < s.end]
    if containing and t_hook - max(containing) <= bcfg["hook_max_offset_s"] + EPS:
        return max(containing), []
    return t_hook, ["midshot_start"]


def snap_end(ep: Episode, t_cliff_end: float) -> tuple[float, list[str]]:
    """End at the end of the shot holding the cliff, unless the next line would start before it."""
    holding = [s.end for s in _shots(ep) if s.start < t_cliff_end <= s.end + EPS]
    if not holding:
        return t_cliff_end, ["midshot_end"]
    end = min(holding)
    if _dialogue_starts_in(ep, t_cliff_end, end):
        return t_cliff_end, ["midshot_end"]   # cutting at the shot end would leak a resolving line
    return end, []


# --- duration rules (TECH_SPEC §4.3 step 4)

def _extend_short(ep: Episode, start: float, end: float, t_hook: float, bcfg: dict) -> tuple[float, float]:
    """Add whole silent shots after the end (max +8 s), then earlier shots if the hook stays ≤ 3 s in."""
    limit = end + bcfg["extend_max_s"]
    for boundary in sorted({s.end for s in _shots(ep) if end + EPS < s.end <= limit + EPS}):
        if end - start >= bcfg["min_duration_s"] - EPS or _dialogue_starts_in(ep, end, boundary):
            break
        end = boundary
    for earlier in sorted((s.start for s in _shots(ep) if s.start < start - EPS), reverse=True):
        if end - start >= bcfg["min_duration_s"] - EPS or t_hook - earlier > bcfg["hook_max_offset_s"] + EPS:
            break
        start = earlier
    return start, end


def _jumpcut(ep: Episode, start: float, end: float, hook: Block, cliff: Block,
             bcfg: dict) -> tuple[list[tuple[float, float]], list[str]] | str:
    """Keep [start, s1_end] (hook + setup) and [s2_start, end] (build-up + cliff), D-015.

    Returns the two intervals and flags, or a rejection reason.
    """
    flags = ["trimmed"]
    boundaries = sorted({s.start for s in _shots(ep)} | {s.end for s in _shots(ep)})
    lo, hi = max(hook.end, start + bcfg["jumpcut_s1_min_s"]), start + bcfg["jumpcut_s1_max_s"]
    in_range = [b for b in boundaries if lo - EPS <= b <= hi + EPS]
    fallback = [b for b in boundaries if hook.end - EPS <= b <= hi + EPS]
    if in_range:
        s1_end = in_range[0]
    elif fallback:
        s1_end = fallback[-1]
    else:
        s1_end, flags = hook.end, flags + ["midshot_s1"]
    seg1 = s1_end - start
    for s2 in sorted({s.start for s in _shots(ep) if s.start > s1_end + EPS}):
        if seg1 + (end - s2) > bcfg["jumpcut_target_max_s"] + EPS or _inside_dialogue(ep, s2):
            continue
        if s2 > cliff.start + EPS:
            break   # every later start would chop the cliff line
        return [(start, s1_end), (s2, end)], flags
    return "cliff_segment_too_long"


# --- validity checks (TECH_SPEC §4.3 step 6)

def validity_checks(ep: Episode, segments: list[tuple[float, float]], t_hook: float,
                    t_cliff_end: float, bcfg: dict) -> dict[str, bool]:
    shot_starts = {round(s.start, 3) for s in _shots(ep)}
    shot_ends = {round(s.end, 3) for s in _shots(ep)}
    total = sum(b - a for a, b in segments)
    ordered = all(a < b for a, b in segments) and all(
        segments[i][1] <= segments[i + 1][0] + EPS for i in range(len(segments) - 1))
    return {
        "dur_ok": bcfg["min_duration_s"] - EPS <= total <= bcfg["max_duration_s"] + EPS,
        "hook_within_3s": 0 - EPS <= t_hook - segments[0][0] <= bcfg["hook_max_offset_s"] + EPS,
        "starts_on_shot": all(round(a, 3) in shot_starts for a, _ in segments),
        "ends_on_shot": all(round(b, 3) in shot_ends for _, b in segments),
        "no_dialogue_after_cliff": not _dialogue_starts_in(ep, t_cliff_end, segments[-1][1]),
        "segments_ordered": ordered,
    }


def build_candidate(ep: Episode, proposal: dict, k: int, bcfg: dict) -> Candidate | Rejected:
    """One proposal (block IDs) -> a checked Candidate, or a Rejected with the reason."""
    by_id = {b.id: b for b in ep.blocks}
    ids = [proposal["start_block"], proposal["hook_block"], proposal["cliff_block"], proposal["end_block"]]
    if any(i not in by_id for i in ids):
        return Rejected(ep=ep.ep, k=k, reason="unknown_block", proposal=proposal,
                        detail={"missing": [i for i in ids if i not in by_id]})
    hook, cliff = by_id[proposal["hook_block"]], by_id[proposal["cliff_block"]]
    t_hook, t_cliff_end = hook.start, cliff.end
    if t_hook >= t_cliff_end:
        return Rejected(ep=ep.ep, k=k, reason="bad_order", proposal=proposal,
                        detail={"t_hook": t_hook, "t_cliff_end": t_cliff_end})

    start, flags = snap_start(ep, t_hook, bcfg)
    end, end_flags = snap_end(ep, t_cliff_end)
    flags += end_flags
    duration = end - start
    if duration > bcfg["max_duration_s"] + EPS:
        result = _jumpcut(ep, start, end, hook, cliff, bcfg)
        if isinstance(result, str):
            return Rejected(ep=ep.ep, k=k, reason=result, proposal=proposal,
                            detail={"start": start, "end": end, "duration_s": round(duration, 3)})
        segments, jc_flags = result
        flags += jc_flags
        kind = "jumpcut"
    else:
        if duration < bcfg["min_duration_s"] - EPS:
            start, end = _extend_short(ep, start, end, t_hook, bcfg)
            flags.append("extended")
        segments, kind = [(start, end)], "single"

    total = round(sum(b - a for a, b in segments), 3)
    if total < bcfg["min_duration_s"] - EPS:
        return Rejected(ep=ep.ep, k=k, reason="too_short", proposal=proposal,
                        detail={"start": segments[0][0], "end": segments[-1][1], "duration_s": total})
    return Candidate(
        id=f"P{ep.ep:02d}-{k}", ep=ep.ep, type=kind,
        segments=[Segment(ep=ep.ep, start=a, end=b, start_block=_block_at_start(ep, a),
                          end_block=_block_at_end(ep, b)) for a, b in segments],
        hook_block=hook.id, cliff_block=cliff.id,
        start_block=proposal["start_block"], end_block=proposal["end_block"],
        beat_type=proposal.get("beat_type", "other"), hook_summary=proposal.get("hook_summary", ""),
        cliff_summary=proposal.get("cliff_summary", ""), reasoning=proposal.get("reasoning", ""),
        flags=flags, checks=validity_checks(ep, segments, t_hook, t_cliff_end, bcfg),
        hook_offset_s=round(t_hook - segments[0][0], 3), total_s=total,
    )


def dedupe(candidates: list[Candidate], iou_threshold: float) -> tuple[list[Candidate], list[dict]]:
    """Within an episode, drop a candidate whose span overlaps an earlier-listed one by IoU > threshold."""
    kept: list[Candidate] = []
    merged: list[dict] = []
    for cand in candidates:
        span = (cand.segments[0].start, cand.segments[-1].end)
        clash = next((k for k in kept if k.ep == cand.ep and
                      interval_iou(span, (k.segments[0].start, k.segments[-1].end)) > iou_threshold), None)
        if clash:
            merged.append({"dropped": cand.id, "kept": clash.id,
                           "iou": round(interval_iou(span, (clash.segments[0].start, clash.segments[-1].end)), 3)})
        else:
            kept.append(cand)
    return kept, merged
