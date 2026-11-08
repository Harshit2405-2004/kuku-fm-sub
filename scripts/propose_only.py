"""Run only the proposer + build stages (no arcs, no judge) into a new run folder, for prompt comparisons.

Writes candidates.json, rejected.json, episodes.json and manifest.json in outputs/<run_id>/ so that
scripts/recall_pool.py can score it. Reuses the pipeline's own propose/build/dedupe functions, so candidates
are built exactly as in a normal run. Example:
  python scripts/propose_only.py --prompt proposer_v4 --run-name v4 --episodes 1,3,8 --model gemini/<m> --key-env GEMINI_API_KEY
"""

from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path

from dotenv import load_dotenv

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from promo_finder.aliases import load_aliases  # noqa: E402
from promo_finder.build import Candidate, build_candidate, dedupe  # noqa: E402
from promo_finder.config import apply_overrides, load_config  # noqa: E402
from promo_finder.llm import load_prompt, summarize_usage  # noqa: E402
from promo_finder.parse import load_pack  # noqa: E402
from promo_finder.pipeline import make_run_id  # noqa: E402
from promo_finder.propose import propose_episode  # noqa: E402


def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument("--input", default="input/pack")
    p.add_argument("--prompt", default="proposer")
    p.add_argument("--run-name", required=True)
    p.add_argument("--episodes", required=True)
    p.add_argument("--model", required=True)
    p.add_argument("--key-env", required=True)
    args = p.parse_args()
    load_dotenv()
    cfg = apply_overrides(load_config("config.yaml"), proposer_model=args.model, api_key_env=args.key_env)
    aliases, cast = load_aliases("config/aliases.yaml")
    eps = {e.ep: e for e in load_pack(Path(args.input), aliases)[0]}
    todo = [int(x) for x in args.episodes.split(",")]
    run_dir = Path("outputs") / make_run_id(args.run_name, time.time())
    run_dir.mkdir(parents=True)
    usage, errors, cands, rejected, proposed = [], [], [], [], 0
    started = time.time()
    for n in todo:
        try:
            props, drop = propose_episode(eps[n], cast, cfg, usage, raw_dir=run_dir / "proposals_raw", prompt_name=args.prompt)
        except Exception as error:
            errors.append({"episode": n, "error": f"{type(error).__name__}: {error}"[:300]})
            continue
        proposed += len(props.candidates) + len(drop)
        built = []
        for k, proposal in enumerate(props.candidates, 1):
            r = build_candidate(eps[n], proposal.model_dump(), k, cfg["build"])
            if isinstance(r, Candidate):
                built.append(r)
            else:
                rejected.append(r.model_dump())
        kept, merged = dedupe(built, cfg["build"]["dedupe_iou"])
        cands += kept
        rejected += [{"ep": n, "reason": "duplicate", **m} for m in merged]
    (run_dir / "candidates.json").write_text(json.dumps([c.model_dump() for c in cands], ensure_ascii=False), encoding="utf-8")
    (run_dir / "rejected.json").write_text(json.dumps({"rejected": rejected}, ensure_ascii=False), encoding="utf-8")
    (run_dir / "episodes.json").write_text(json.dumps([e.model_dump() for e in eps.values()], ensure_ascii=False), encoding="utf-8")
    manifest = {"run_id": run_dir.name, "stage": "proposer+build only", "prompt": load_prompt(args.prompt)[0],
                "model": args.model, "episodes_run": todo, "proposed": proposed, "built": len(cands),
                "rejected": len(rejected), "errors": errors, "usage": summarize_usage(usage),
                "seconds": round(time.time() - started, 1)}
    (run_dir / "manifest.json").write_text(json.dumps(manifest, indent=1), encoding="utf-8")
    print(run_dir, {k: manifest[k] for k in ("prompt", "proposed", "built", "rejected")}, "errors", len(errors))


if __name__ == "__main__":
    main()
