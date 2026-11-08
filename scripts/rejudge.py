"""Judge ALL built candidates of an existing run with one judge model, rank them, write a NEW run folder.

For the recall sprint: run A's judge ran out of daily quota (26 clips unscored). This re-scores every built
candidate with a single judge (the source run folder is only read), then reports recall@20 (dev vs held-out)
and where the human-rated blind clips land. Counts and ratings only; no script text or gold content is printed.
  python scripts/rejudge.py --source outputs/<run> --judge gemini/<model> --key-env GEMINI_API_KEY
"""

from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path

from dotenv import load_dotenv

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
sys.path.insert(0, str(Path(__file__).resolve().parent))
from evaluate import block_times, read_gold  # noqa: E402
from promo_finder.build import Candidate  # noqa: E402
from promo_finder.config import apply_overrides, load_config  # noqa: E402
from promo_finder.judge import judge_candidates  # noqa: E402
from promo_finder.llm import summarize_usage  # noqa: E402
from promo_finder.parse import Episode  # noqa: E402
from promo_finder.rank import rank  # noqa: E402
from recall_pool import fmt, gold_recall  # noqa: E402


def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument("--source", required=True)
    p.add_argument("--judge", required=True)
    p.add_argument("--key-env", required=True)
    p.add_argument("--name", default="rejudge")
    args = p.parse_args()
    load_dotenv()
    src = Path(args.source)
    cfg = apply_overrides(load_config("config.yaml"), judge_model=args.judge, api_key_env=args.key_env)
    raw_eps = json.loads((src / "episodes.json").read_text(encoding="utf-8"))
    episodes = {e["ep"]: Episode.model_validate(e) for e in raw_eps}
    cands = [Candidate.model_validate(c) for c in json.loads((src / "candidates.json").read_text(encoding="utf-8"))]
    run_dir = Path("outputs") / (time.strftime("%Y%m%d-%H%M") + "-" + args.name)
    run_dir.mkdir(parents=True)
    usage: list[dict] = []
    started = time.time()
    scores, errors = judge_candidates(cands, episodes, cfg, usage, raw_dir=run_dir / "judge_raw")
    ranked, skips, unscored = rank(cands, scores, episodes, cfg["rank"])
    (run_dir / "ranked.json").write_text(json.dumps({"ranked": ranked, "unscored": unscored}, ensure_ascii=False), encoding="utf-8")
    (run_dir / "candidates.json").write_text((src / "candidates.json").read_text(encoding="utf-8"), encoding="utf-8")
    (run_dir / "episodes.json").write_text((src / "episodes.json").read_text(encoding="utf-8"), encoding="utf-8")
    manifest = {"run_id": run_dir.name, "stage": "judge+rank only", "source_run": src.name, "judge": args.judge,
                "candidates": len(cands), "scored": len(scores), "ranked": len(ranked), "unscored": len(unscored),
                "errors": errors, "usage": summarize_usage(usage), "seconds": round(time.time() - started, 1)}
    (run_dir / "manifest.json").write_text(json.dumps(manifest, indent=1), encoding="utf-8")
    print(run_dir, f"candidates {len(cands)} scored {len(scores)} ranked {len(ranked)} unscored {len(unscored)} errors {len(errors)}")
    if not ranked:
        return
    times = block_times(raw_eps)
    gold = read_gold(Path("gold/gold_labels.csv"))
    print("recall@20 (any ranked top 20):", fmt(gold_recall(ranked[:20], times, gold)))
    print("recall over all ranked:", fmt(gold_recall(ranked, times, gold)))
    key = {r["sheet_id"]: r["promo_id"] for r in read_gold(Path("gold/precision_key.csv"))}
    rated = {key[r["sheet_id"]]: int(r["rating"]) for r in read_gold(Path("gold/precision_ratings.csv")) if r["rating"] != ""}
    pos = {r["id"]: r["rank"] for r in ranked}
    in15 = sorted((pos[i], rated[i]) for i in rated if i in pos and pos[i] <= 15)
    print(f"rated clips in new top 15: {len(in15)}/15; (rank, rating): {in15}")
    print("top-10 ratings among rated:", [rt for _, rt in in15 if _ <= 10])


if __name__ == "__main__":
    main()
