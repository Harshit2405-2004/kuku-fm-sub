"""CLI: run the whole pipeline on a screenplay pack and write outputs/<run_id>/.

Examples:
  python run.py --input input/<pack> --config config.yaml --run-name runA
  python run.py --input samples/synthetic_show --mock
  python run.py --input input/<pack> --model openai/<their-model> --api-base https://... --api-key-env KUKU_KEY
"""

from __future__ import annotations

import argparse
import logging
import sys

from dotenv import load_dotenv

from promo_finder.config import apply_overrides, load_config
from promo_finder.pipeline import run_pipeline


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Find ranked 20–60 s promo clips in a microdrama screenplay pack.")
    p.add_argument("--input", required=True, help="folder of episode .txt files (or a .zip)")
    p.add_argument("--config", default="config.yaml")
    p.add_argument("--run-name", default="run")
    p.add_argument("--out", default="outputs", help="where run folders go")
    p.add_argument("--aliases", default="config/aliases.yaml", help="speaker alias file (optional)")
    p.add_argument("--episodes", help="comma-separated episode numbers to run, e.g. 1,3,8 (default: all)")
    p.add_argument("--mock", action="store_true", help="canned replies, no API key needed")
    p.add_argument("--no-cache", action="store_true")
    p.add_argument("--model", help="model for every stage (LiteLLM name, e.g. openai/<name>)")
    p.add_argument("--proposer-model")
    p.add_argument("--arc-model")
    p.add_argument("--judge-model")
    p.add_argument("--api-base", help="OpenAI-compatible endpoint URL for the overridden stages")
    p.add_argument("--api-key-env", help="name of the env var holding that endpoint's key")
    p.add_argument("--run-dir", help="continue in this existing run folder (finished episodes come from the cache)")
    p.add_argument("--episode-proposer", action="append", default=[], metavar="EPISODES=MODEL",
                   help="proposer model for some episodes only, e.g. '3,17-23=groq/openai/gpt-oss-20b' or '3=gemini/<model>|GEMINI_API_KEY' (repeatable)")
    return p.parse_args(argv)


def parse_episode_proposers(specs: list[str], base: dict) -> dict[int, dict]:
    """'3,17-23=model' → {3: {...}, 17: {...}, ...}. The api_base / key env stay the base proposer's."""
    out: dict[int, dict] = {}
    for spec in specs:
        eps, _, model = spec.partition("=")
        model, _, key_env = model.partition("|")      # optional "|KEY_ENV_NAME" for another provider
        if not model:
            raise SystemExit(f"--episode-proposer needs EPISODES=MODEL, got {spec!r}")
        for part in eps.split(","):
            lo, _, hi = part.partition("-")
            for n in range(int(lo), int(hi or lo) + 1):
                out[n] = {"model": model, **({"api_key_env": key_env} if key_env else {})}
    return out


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    load_dotenv()
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
    logging.getLogger("LiteLLM").setLevel(logging.WARNING)
    logging.getLogger("httpx").setLevel(logging.WARNING)
    cfg = apply_overrides(load_config(args.config), model=args.model, proposer_model=args.proposer_model,
                          arc_model=args.arc_model, judge_model=args.judge_model, api_base=args.api_base,
                          api_key_env=args.api_key_env, no_cache=args.no_cache, mock=args.mock)
    episodes = [int(x) for x in args.episodes.split(",")] if args.episodes else None
    cfg["episode_proposers"] = parse_episode_proposers(args.episode_proposer, cfg["models"]["proposer"])
    run_dir = run_pipeline(args.input, cfg, args.run_name, out_root=args.out, aliases_path=args.aliases,
                           episodes_filter=episodes, reuse_dir=args.run_dir)
    print(f"done: {run_dir}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
