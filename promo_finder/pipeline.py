"""The whole run, stage by stage: parse → propose → build → judge → rank → write outputs.

Pipeline position: the glue. run.py (CLI) and app.py (Streamlit) both call `run_pipeline`. Each stage
saves its results as soon as it finishes, so a crash late in a long run still leaves the earlier files,
and the LLM cache makes a rerun of the finished stages free.
"""

from __future__ import annotations

import copy
import json
import logging
import subprocess
import time
from pathlib import Path
from typing import Callable

from promo_finder import report
from promo_finder.aliases import load_aliases
from promo_finder.arcs import propose_arcs
from promo_finder.build import Candidate, build_candidate, dedupe
from promo_finder.judge import judge_candidates
from promo_finder.llm import load_prompt, summarize_usage
from promo_finder.parse import load_pack, pack_stats
from promo_finder.propose import propose_episode
from promo_finder.rank import rank

log = logging.getLogger(__name__)


def make_run_id(run_name: str, now: float | None = None) -> str:
    return time.strftime("%Y%m%d-%H%M", time.localtime(now)) + f"-{run_name}"


def _git_commit() -> str | None:
    try:
        out = subprocess.run(["git", "rev-parse", "--short", "HEAD"], capture_output=True, text=True, timeout=10)
        return out.stdout.strip() or None
    except (OSError, subprocess.SubprocessError):
        return None


def _proposer_cfg_for(cfg: dict, ep: int) -> dict:
    """cfg with the proposer replaced for episodes listed in cfg['episode_proposers'] (a mid-run host switch)."""
    override = (cfg.get("episode_proposers") or {}).get(ep)
    if not override:
        return cfg
    new = copy.deepcopy(cfg)
    new["models"]["proposer"].update(override)
    return new


def _config_snapshot(cfg: dict) -> dict:
    """The config as run, minus run-time bookkeeping. It holds env var NAMES only, never key values."""
    return {k: v for k, v in cfg.items() if not k.startswith("_")}


def run_pipeline(input_path: Path | str, cfg: dict, run_name: str, out_root: Path | str = "outputs",
                 aliases_path: Path | str | None = "config/aliases.yaml", episodes_filter: list[int] | None = None,
                 completion_fn: Callable | None = None, progress: Callable[[str, int, int], None] | None = None,
                 reuse_dir: Path | str | None = None) -> Path:
    """Run every stage and return the run directory. Errors in one episode or batch are logged and the run goes on.

    reuse_dir: continue in an existing run folder (finished episodes come from the LLM cache, files are rewritten).
    """
    started = time.time()
    if reuse_dir:
        run_dir = Path(reuse_dir)
        run_id = run_dir.name
        run_dir.mkdir(parents=True, exist_ok=True)
    else:
        run_id = make_run_id(run_name, started)
        run_dir = Path(out_root) / run_id
        n = 2
        while run_dir.exists():          # two runs with the same name in one minute
            run_dir = Path(out_root) / f"{run_id}-{n}"
            n += 1
        run_id = run_dir.name
        run_dir.mkdir(parents=True)
    handler = logging.FileHandler(run_dir / "run.log", encoding="utf-8", mode="a")
    handler.setFormatter(logging.Formatter("%(asctime)s %(levelname)s %(name)s: %(message)s"))
    logging.getLogger().addHandler(handler)
    if logging.getLogger().level > logging.INFO:
        logging.getLogger().setLevel(logging.INFO)
    try:
        return _run(Path(input_path), cfg, run_id, run_dir, aliases_path, episodes_filter, completion_fn,
                    progress or (lambda stage, done, total: None), started)
    finally:
        logging.getLogger().removeHandler(handler)
        handler.close()


def _run(input_path, cfg, run_id, run_dir, aliases_path, episodes_filter, completion_fn, progress, started) -> Path:
    errors: list[dict] = []
    timings: dict[str, float] = {}
    usage: list[dict] = []
    log.info("run %s: input %s, mock=%s", run_id, input_path.name, cfg.get("mock"))

    # 1. Parse
    t = time.time()
    aliases, cast = load_aliases(aliases_path)
    all_episodes, parse_warnings = load_pack(input_path, aliases)
    episodes = {e.ep: e for e in all_episodes}
    todo = sorted(n for n in episodes if not episodes_filter or n in episodes_filter)
    report.write_json(run_dir / "episodes.json", [e.model_dump() for e in all_episodes])
    timings["parse"] = round(time.time() - t, 2)
    log.info("parsed %d episodes (%d warnings); running %d", len(episodes), len(parse_warnings), len(todo))

    # 2. Propose + 3. Build, one episode at a time
    t = time.time()
    candidates: list[Candidate] = []
    rejected: list[dict] = []
    dropped: list[dict] = []
    proposed_per_episode: dict[int, int] = {}
    episode_models: dict[int, str] = {}      # which model served each episode (manifest)
    for i, n in enumerate(todo, 1):
        ep_cfg = _proposer_cfg_for(cfg, n)
        episode_models[n] = ep_cfg["models"]["proposer"]["model"]
        try:
            props, drop = propose_episode(episodes[n], cast, ep_cfg, usage, raw_dir=run_dir / "proposals_raw",
                                          completion_fn=completion_fn)
        except Exception as error:
            log.error("E%02d: proposer failed: %s", n, error)
            errors.append({"stage": "proposer", "episode": n, "error": f"{type(error).__name__}: {error}"[:300]})
            progress("propose", i, len(todo))
            continue
        dropped += drop
        proposed_per_episode[n] = len(props.candidates) + len(drop)
        built = []
        for k, proposal in enumerate(props.candidates, 1):
            result = build_candidate(episodes[n], proposal.model_dump(), k, cfg["build"])
            if isinstance(result, Candidate):
                built.append(result)
            else:
                rejected.append(result.model_dump())
        kept, merged = dedupe(built, cfg["build"]["dedupe_iou"])
        candidates += kept
        rejected += [{"ep": n, "reason": "duplicate", **m} for m in merged]
        log.info("E%02d: %d proposed, %d built, %d kept (%d/%d episodes, %.0f s)", n, proposed_per_episode[n],
                 len(built), len(kept), i, len(todo), time.time() - t)
        progress("propose", i, len(todo))
    report.write_json(run_dir / "candidates.json", [c.model_dump() for c in candidates])
    report.write_json(run_dir / "rejected.json", {"rejected": rejected, "dropped_by_proposer": dropped})
    timings["propose_build"] = round(time.time() - t, 2)

    # 3b. Cross-episode arcs (TECH_SPEC §4.4). Appended after the singles, so the singles' judge
    # batches stay identical to a run without arcs and come from the cache.
    arcs_status = "disabled"
    if (cfg.get("arcs") or {}).get("enabled"):
        t = time.time()
        try:
            arcs, arc_rejected = propose_arcs(candidates, episodes, cfg, usage, raw_path=run_dir / "arcs_raw.json",
                                              completion_fn=completion_fn)
            candidates += arcs
            rejected += [{**r, "reason": f"arc_{r['reason']}"} for r in arc_rejected]
            arcs_status = f"{len(arcs)} built, {len(arc_rejected)} rejected"
        except Exception as error:
            log.error("arcs failed: %s", error)
            errors.append({"stage": "arc", "error": f"{type(error).__name__}: {error}"[:300]})
            arcs_status = "failed"
        report.write_json(run_dir / "candidates.json", [c.model_dump() for c in candidates])
        report.write_json(run_dir / "rejected.json", {"rejected": rejected, "dropped_by_proposer": dropped})
        timings["arcs"] = round(time.time() - t, 2)

    # 4. Judge
    t = time.time()
    scores, judge_errors = judge_candidates(candidates, episodes, cfg, usage, raw_dir=run_dir / "judge_raw",
                                            completion_fn=completion_fn)
    errors += [{"stage": "judge", **e} for e in judge_errors]
    report.write_json(run_dir / "scored.json", {c.id: {**c.model_dump(), "judge": scores[c.id].model_dump()}
                                                for c in candidates if c.id in scores})
    timings["judge"] = round(time.time() - t, 2)
    progress("judge", 1, 1)

    # 5. Rank
    ranked, skips, unscored = rank(candidates, scores, episodes, cfg["rank"])
    report.write_json(run_dir / "ranked.json", {"ranked": ranked, "diversity_skips": skips, "unscored": unscored})

    # 6. Outputs
    report.write_promos(run_dir, ranked)
    report.write_review(run_dir, ranked, skips, episodes, run_id, cfg["rank"]["diversity"]["top_n"])
    summary = summarize_usage(usage)
    manifest = {
        "run_id": run_id,
        "timestamp": time.strftime("%Y-%m-%dT%H:%M:%S%z", time.localtime(started)),
        "git_commit": _git_commit(),
        "mock": bool(cfg.get("mock")),
        "models": {stage: ("mock" if cfg.get("mock") else c["model"]) for stage, c in cfg["models"].items()},
        "prompt_versions": {name: load_prompt(name)[0] for name in ("proposer", "arc", "judge")},
        "arcs": arcs_status,
        "episodes_parsed": len(episodes),
        "episodes_run": todo,
        "proposer_model_by_episode": {f"E{n:02d}": m for n, m in episode_models.items()},
        "parse_stats": pack_stats(all_episodes),
        "parse_warnings": len(parse_warnings),
        "counts": {"proposed": sum(proposed_per_episode.values()), "dropped_by_proposer": len(dropped),
                   "built": len(candidates), "rejected": len(rejected), "scored": len(scores),
                   "ranked": len(ranked), "unscored": len(unscored), "diversity_skips": len(skips),
                   "episodes_with_candidates": len({c.ep for c in candidates})},
        "usage": summary,
        "cost_usd": report.stage_costs(summary, cfg.get("prices", {})),
        "timings_s": {**timings, "total": round(time.time() - started, 2)},
        "errors": errors,
        "config": _config_snapshot(cfg),
    }
    report.write_json(run_dir / "manifest.json", manifest)
    log.info("run %s done: %d ranked, %d errors, %.0f s", run_id, len(ranked), len(errors), time.time() - started)
    return run_dir
