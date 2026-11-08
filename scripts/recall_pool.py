"""Recall of candidate pools against the gold set, split into dev and held-out episodes (counts only).

Used by the recall sprint: pool candidates from several run folders (or only the ranked ones) and score them
with the same matching rule as evaluate.py (metrics.match_level, never changed). Nothing from the gold file is
printed except counts. Usage:
  python scripts/recall_pool.py "label=outputs/runA[:ranked]+outputs/runB" ...
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from evaluate import block_times, promo_intervals, read_gold  # noqa: E402
from promo_finder import metrics  # noqa: E402

HOLDOUT = {3, 27, 45}
GOLD = Path("gold/gold_labels.csv")


def load_pool(spec: str) -> list[dict]:
    """'outputs/runA:ranked+outputs/runB' -> candidate dicts (built candidates, or ranked ones with ':ranked')."""
    pool = []
    for part in spec.split("+"):
        path, _, kind = part.partition(":")
        name = "ranked.json" if kind == "ranked" else "candidates.json"
        data = json.loads((Path(path) / name).read_text(encoding="utf-8"))
        pool += data["ranked"] if kind == "ranked" else data
    return pool


def gold_recall(pool: list[dict], times: dict, gold: list[dict]) -> dict:
    out = {"dev": {"strict": 0, "lenient": 0, "of": 0}, "held": {"strict": 0, "lenient": 0, "of": 0}}
    for g in gold:
        if g["segments"].strip().upper().startswith("NONE"):
            continue
        side = "held" if int(g["episode"]) in HOLDOUT else "dev"
        gi = metrics.parse_gold_segments(g["segments"])
        hook, cliff = times.get(g["hook_block"]), times.get(g["cliff_block"])
        levels = {metrics.match_level(promo_intervals(c), gi, hook, cliff) for c in pool}
        out[side]["of"] += 1
        out[side]["strict"] += "strict" in levels
        out[side]["lenient"] += bool(levels - {None})
    return out


def fmt(r: dict) -> str:
    return (f"dev {r['dev']['strict']}/{r['dev']['of']} strict, {r['dev']['lenient']}/{r['dev']['of']} lenient | "
            f"held-out {r['held']['strict']}/{r['held']['of']} strict, {r['held']['lenient']}/{r['held']['of']} lenient")


def main(specs: list[str]) -> None:
    gold = read_gold(GOLD)
    for spec in specs:
        label, _, runs = spec.partition("=")
        first = runs.split("+")[0].partition(":")[0]
        times = block_times(json.loads((Path(first) / "episodes.json").read_text(encoding="utf-8")))
        pool = load_pool(runs)
        print(f"{label} ({len(pool)} candidates): {fmt(gold_recall(pool, times, gold))}")


if __name__ == "__main__":
    main(sys.argv[1:])
