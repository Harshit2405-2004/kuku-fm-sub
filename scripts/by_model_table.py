"""Per-proposer-model table for a finished run: episodes, proposals, built, ranked, mean judge scores.

Used for the run A report (gpt-oss-120b on 18 episodes vs gpt-oss-20b on 32). The two groups are different
episodes, so the table is indicative, not a controlled comparison. Reads only saved run files; counts and means.
"""

from __future__ import annotations

import argparse
import json
from collections import defaultdict
from pathlib import Path


def load(run: Path, name: str):
    return json.loads((run / name).read_text(encoding="utf-8"))


def table(run: Path) -> str:
    manifest = load(run, "manifest.json")
    by_ep = {int(k[1:]): v for k, v in manifest.get("proposer_model_by_episode", {}).items()}
    failed = {e.get("episode") for e in manifest["errors"] if e.get("stage") == "proposer"}
    candidates = [c for c in load(run, "candidates.json") if c["type"] != "arc"]
    rejected = [r for r in load(run, "rejected.json")["rejected"] if not str(r.get("reason", "")).startswith("arc_")]
    dropped = load(run, "rejected.json")["dropped_by_proposer"]
    ranked = load(run, "ranked.json")["ranked"]
    groups: dict[str, dict] = defaultdict(lambda: {"eps": set(), "failed": set(), "built": 0, "rej": 0, "drop": 0, "ranked": []})
    for ep, model in by_ep.items():
        g = groups[model]
        (g["failed"] if ep in failed else g["eps"]).add(ep)
    for c in candidates:
        groups[by_ep[c["ep"]]]["built"] += 1
    for r in rejected:
        if r.get("ep") in by_ep:
            groups[by_ep[r["ep"]]]["rej"] += 1
    for d in dropped:
        if d.get("ep") in by_ep:
            groups[by_ep[d["ep"]]]["drop"] += 1
    for r in ranked:
        if r["type"] != "arc":
            groups[by_ep[r["episode_key"]]]["ranked"].append(r)
    mean = lambda rows, k: f"{sum(r['scores'][k] for r in rows) / len(rows):.2f}" if rows else "n/a"
    lines = ["| proposer model | episodes processed | not processed | proposals | built | singles ranked | mean hook | mean cliff | mean standalone |",
             "|---|---|---|---|---|---|---|---|---|"]
    for model, g in sorted(groups.items()):
        # proposals = clips that reached the builder (built + rejected by the builder/dedupe) + proposer drops
        proposals = g["built"] + g["rej"] + g["drop"]
        rows = g["ranked"]
        lines.append(f"| {model} | {len(g['eps'])} | {len(g['failed'])} | {proposals} | {g['built']} | {len(rows)} | "
                     f"{mean(rows, 'hook')} | {mean(rows, 'cliff')} | {mean(rows, 'standalone')} |")
    lines += ["", "Different episodes, so it's indicative, not a controlled comparison. Arc promos are excluded "
              "(they pair clips from both groups). Proposals = built + rejected (builder checks, duplicates) + proposer drops."]
    return "\n".join(lines)


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--run", required=True, type=Path)
    print(table(ap.parse_args().run))
