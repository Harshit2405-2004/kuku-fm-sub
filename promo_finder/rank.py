"""Ranker: judge scores + code bonuses/penalties -> one final score, then a diversity pass (TECH_SPEC §4.6).

Pipeline position: stage 5, after judge.py and before the output writers. Pure code, no LLM: every
weight comes from config.yaml `rank`, so a ranking can be explained line by line. It also writes a short
code-generated posting rationale for each promo.
"""

from __future__ import annotations

from promo_finder.build import Candidate
from promo_finder.judge import DIMENSIONS, ClipScore
from promo_finder.parse import Episode

EPS = 1e-6


def scene_key(cand: Candidate, episodes: dict[int, Episode]) -> tuple[int, int]:
    """A promo's scene is the scene of its hook block; an arc counts under segment 1 (TECH_SPEC §4.6)."""
    ep = cand.segments[0].ep
    block = next((b for b in episodes[ep].blocks if b.id == cand.hook_block), None)
    return ep, block.scene if block else -1


def score_candidate(cand: Candidate, js: ClipScore, rcfg: dict) -> dict:
    """final = base + bonus − penalty, with each part kept so the number can be explained."""
    w, bonus_cfg, pen_cfg = rcfg["weights"], rcfg["bonus"], rcfg["penalty"]
    base = sum(w[d] * (getattr(js, d) - 1) / 4 for d in DIMENSIONS)   # 1–5 -> 0–1
    bonuses: dict[str, float] = {}
    # An early-episode promo drops a new viewer near the start of the show (TECH_SPEC §4.6 bonus).
    first_ep = min(s.ep for s in cand.segments)
    if first_ep <= bonus_cfg["early_ep_max"]:
        bonuses["early_episode"] = bonus_cfg["early_ep"]
    elif first_ep <= bonus_cfg["mid_ep_max"]:
        bonuses["mid_episode"] = bonus_cfg["mid_ep"]
    lo, hi = bonus_cfg["sweet_spot"]
    if lo - EPS <= cand.total_s <= hi + EPS:
        bonuses["sweet_spot"] = bonus_cfg["sweet_spot_bonus"]
    if cand.type == "arc":
        bonuses["arc"] = bonus_cfg["arc"]
    penalties = {f: pen_cfg[f] for f in sorted(set(cand.flags) | set(js.risk_flags)) if f in pen_cfg}
    final = base + sum(bonuses.values()) - sum(penalties.values())
    return {"base": round(base, 4), "bonuses": bonuses, "penalties": penalties, "final_score": round(final, 4)}


def diversify(rows: list[dict], dcfg: dict) -> tuple[list[dict], list[dict]]:
    """Greedy re-order: in the top `top_n` at most `max_per_episode` per episode, in the top `top_scene_n`
    at most `max_per_scene` per scene. A promo that would break a cap waits and the next one moves up.
    Returns (ordered rows, skip records)."""
    pool = list(rows)                     # already sorted by final_score, best first
    ordered: list[dict] = []
    skips: list[dict] = []
    skipped_ids: set[str] = set()
    while pool:
        pos = len(ordered)
        pick = None
        for row in pool:
            reason = _cap_broken(row, ordered, pos, dcfg)
            if reason is None:
                pick = row
                break
            if row["id"] not in skipped_ids:
                skipped_ids.add(row["id"])
                skips.append({"id": row["id"], "at_rank": pos + 1, "reason": reason,
                              "final_score": row["final_score"]})
        if pick is None:
            pick = pool[0]                # every remaining promo breaks a cap: caps can't all hold
        pool.remove(pick)
        ordered.append(pick)
    for row in ordered:
        if row["id"] in skipped_ids:
            next(s for s in skips if s["id"] == row["id"])["placed_at"] = ordered.index(row) + 1
    return ordered, skips


def _cap_broken(row: dict, ordered: list[dict], pos: int, dcfg: dict) -> str | None:
    if pos < dcfg["top_n"]:
        same_ep = sum(1 for r in ordered[:dcfg["top_n"]] if r["episode_key"] == row["episode_key"])
        if same_ep >= dcfg["max_per_episode"]:
            return f"already {same_ep} promos from episode {row['episode_key']} in the top {dcfg['top_n']}"
    if pos < dcfg["top_scene_n"]:
        same_scene = sum(1 for r in ordered[:dcfg["top_scene_n"]] if r["scene_key"] == row["scene_key"])
        if same_scene >= dcfg["max_per_scene"]:
            ep, scene = row["scene_key"]
            return f"already {same_scene} promo from episode {ep} scene {scene} in the top {dcfg['top_scene_n']}"
    return None


def posting_rationale(row: dict) -> str:
    """One plain sentence an editor can read: what is strong, what to watch."""
    s = row["scores"]
    strong = [f"{name} {s[d]}/5" for d, name in (("hook", "hook"), ("cliff", "cliffhanger"),
                                                  ("standalone", "stands alone")) if s[d] >= 4]
    weak = [f"{name} {s[d]}/5" for d, name in (("hook", "hook"), ("cliff", "cliffhanger"),
                                                ("standalone", "stands alone")) if s[d] <= 2]
    parts = [("Strong " + ", ".join(strong)) if strong else "No standout dimension"]
    if weak:
        parts.append("weak " + ", ".join(weak))
    if "early_episode" in row["bonuses"]:
        parts.append(f"from episode {row['episode_key']}, so new viewers land near the start")
    if "sweet_spot" in row["bonuses"]:
        parts.append(f"{row['total_s']:.0f} s is in the 30–45 s sweet spot")
    sentence = "; ".join(parts) + "."
    if "graphic_violence" in row["risk_flags"]:
        sentence += " Brand-safety check before posting: on-screen violence."
    other = [f for f in row["risk_flags"] if f != "graphic_violence"]
    if other:
        sentence += " Watch: " + ", ".join(other) + "."
    return sentence


def rank(cands: list[Candidate], scores: dict[str, ClipScore], episodes: dict[int, Episode],
         rcfg: dict) -> tuple[list[dict], list[dict], list[str]]:
    """Returns (ranked rows, diversity skips, ids with no judge score). Unscored promos are not ranked."""
    rows, unscored = [], []
    for cand in cands:
        js = scores.get(cand.id)
        if js is None:
            unscored.append(cand.id)
            continue
        parts = score_candidate(cand, js, rcfg)
        rows.append({**cand.model_dump(), **parts,
                     "scores": {d: getattr(js, d) for d in DIMENSIONS},
                     "hook_text": js.hook_text, "cliff_text": js.cliff_text, "why": js.why,
                     "judge_reasons": js.reasons, "risk_flags": list(js.risk_flags),
                     "episode_key": cand.segments[0].ep, "scene_key": scene_key(cand, episodes)})
    # Ties break on hook, then cliff, then id, so the order never depends on input order.
    rows.sort(key=lambda r: (-r["final_score"], -r["scores"]["hook"], -r["scores"]["cliff"], r["id"]))
    ordered, skips = diversify(rows, rcfg["diversity"])
    for i, row in enumerate(ordered, 1):
        row["rank"] = i
        row["posting_rationale"] = posting_rationale(row)
    return ordered, skips, unscored
