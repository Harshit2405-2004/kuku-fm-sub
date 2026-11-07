"""Output writers: everything a run leaves in outputs/<run_id>/ (TECH_SPEC §7).

Pipeline position: the last stage, after rank.py. Turns ranked rows into promos.csv / promos.json for
tools, review.md for an editor, and manifest.json for whoever has to explain or rerun the run.
Times are only ever computed here from segment seconds; nothing is read back from model text.
"""

from __future__ import annotations

import csv
import json
from pathlib import Path

from promo_finder.build import Candidate
from promo_finder.compact import format_tc
from promo_finder.judge import DIMENSIONS, excerpt
from promo_finder.parse import Episode

CSV_COLUMNS = ["rank", "promo_id", "type", "total_sec", "segments", "hook_text", "cliff_text", "why",
               *DIMENSIONS, "final_score", "flags", "posting_rationale"]


def write_json(path: Path, data) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=1, ensure_ascii=False), encoding="utf-8")


def segments_text(segments: list[dict]) -> str:
    """`E01 00:11.0–00:41.5; E42 …`, the editor's cut list."""
    return "; ".join(f"E{s['ep']:02d} {format_tc(s['start'])}–{format_tc(s['end'])}" for s in segments)


def promo_record(row: dict) -> dict:
    return {
        "rank": row["rank"], "promo_id": row["id"], "type": row["type"], "total_sec": row["total_s"],
        "segments": [{"episode": s["ep"], "start": s["start"], "end": s["end"],
                      "start_tc": format_tc(s["start"]), "end_tc": format_tc(s["end"]),
                      "start_block": s["start_block"], "end_block": s["end_block"]} for s in row["segments"]],
        "hook_block": row["hook_block"], "cliff_block": row["cliff_block"], "hook_offset_s": row["hook_offset_s"],
        "beat_type": row["beat_type"], "hook_text": row["hook_text"], "cliff_text": row["cliff_text"],
        "why": row["why"], "scores": row["scores"], "base": row["base"], "bonuses": row["bonuses"],
        "penalties": row["penalties"], "final_score": row["final_score"],
        "flags": sorted(set(row["flags"]) | set(row["risk_flags"])), "checks": row["checks"],
        "posting_rationale": row["posting_rationale"],
    }


def write_promos(run_dir: Path, ranked: list[dict]) -> None:
    records = [promo_record(r) for r in ranked]
    write_json(run_dir / "promos.json", records)
    with open(run_dir / "promos.csv", "w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=CSV_COLUMNS)
        writer.writeheader()
        for rec, row in zip(records, ranked):
            writer.writerow({"rank": rec["rank"], "promo_id": rec["promo_id"], "type": rec["type"],
                             "total_sec": f"{rec['total_sec']:.1f}", "segments": segments_text(row["segments"]),
                             "hook_text": rec["hook_text"], "cliff_text": rec["cliff_text"], "why": rec["why"],
                             **rec["scores"], "final_score": f"{rec['final_score']:.3f}",
                             "flags": ";".join(rec["flags"]), "posting_rationale": rec["posting_rationale"]})


def write_review(run_dir: Path, ranked: list[dict], skips: list[dict], episodes: dict[int, Episode],
                 run_id: str, top_n: int = 20) -> None:
    """Editor-facing: posting order first, then each promo with its cut list and the script excerpt."""
    lines = [f"# Promo shortlist: {run_id}", "",
             f"{len(ranked)} ranked promos. Post in rank order; the top {min(top_n, len(ranked))} respect the "
             "diversity caps (max 2 per episode in the top 20, max 1 per scene in the top 10).", ""]
    if skips:
        lines += ["Moved down by the diversity pass: " +
                  ", ".join(f"{s['id']} (to #{s.get('placed_at', '?')})" for s in skips), ""]
    lines += ["| # | Promo | Cut | Length | Hook → Cliff | Score | Flags |", "|---|---|---|---|---|---|---|"]
    for r in ranked:
        hook_cliff = f"{r['hook_text']} → {r['cliff_text']}".replace("|", "/")
        flags = ", ".join(sorted(set(r["flags"]) | set(r["risk_flags"]))) or "-"
        lines.append(f"| {r['rank']} | {r['id']} | {segments_text(r['segments'])} | {r['total_s']:.1f} s | "
                     f"{hook_cliff} | {r['final_score']:.3f} | {flags} |")
    lines.append("")
    for r in ranked:
        cand = Candidate(**{k: r[k] for k in Candidate.model_fields})
        lines += [f"## #{r['rank']} {r['id']} · {r['type']} · {r['total_s']:.1f} s · {segments_text(r['segments'])}", "",
                  f"- **Hook** ({r['hook_offset_s']:.1f} s in): {r['hook_text']}",
                  f"- **Cliff:** {r['cliff_text']}",
                  f"- **Why:** {r['why']}",
                  f"- **Scores:** " + ", ".join(f"{d} {r['scores'][d]}" for d in DIMENSIONS) +
                  f" · final {r['final_score']:.3f} (base {r['base']:.3f}, bonus {r['bonuses'] or '-'}, "
                  f"penalty {r['penalties'] or '-'})",
                  f"- **Posting note:** {r['posting_rationale']}",
                  "", "```", excerpt(cand, episodes), "```", ""]
    (run_dir / "review.md").write_text("\n".join(lines), encoding="utf-8")


def stage_costs(usage_summary: dict, prices: dict) -> dict:
    """USD per stage from config prices (per 1M tokens). Unknown price or mixed models -> null, never a guess."""
    costs = {}
    for stage, s in usage_summary.items():
        models = [m for m in s["models"] if m != "mock"]
        if not models:
            costs[stage] = 0.0
        elif len(models) > 1 or models[0] not in prices:
            costs[stage] = None
        else:
            price = prices[models[0]]
            costs[stage] = round((s["prompt_tokens"] * (price.get("input") or 0)
                                  + s["completion_tokens"] * (price.get("output") or 0)) / 1e6, 4)
    return costs
