"""Load config.yaml and apply CLI overrides (model swap, endpoint, mock, cache).

Pipeline position: read once by run.py / app.py and passed down to every stage. This is the only
place model choices come from (hard rule 2), so swapping in Kuku's API is a flag, not a code change.
"""

from __future__ import annotations

import copy
from pathlib import Path

import yaml

STAGES = ("proposer", "arc", "judge")


def load_config(path: Path | str) -> dict:
    cfg = yaml.safe_load(Path(path).read_text(encoding="utf-8")) or {}
    cfg.setdefault("mock", False)
    cfg.setdefault("no_cache", False)
    return cfg


def apply_overrides(cfg: dict, model: str | None = None, proposer_model: str | None = None,
                    arc_model: str | None = None, judge_model: str | None = None,
                    api_base: str | None = None, api_key_env: str | None = None,
                    no_cache: bool = False, mock: bool = False) -> dict:
    """Return a copy of cfg with CLI flags applied.

    --model sets every stage; a stage flag (--judge-model, ...) beats it for that stage.
    --api-base / --api-key-env go with the stages whose model was overridden (so "upgrade only the
    judge" leaves the free proposer untouched), or to every stage if no model flag was given.
    """
    cfg = copy.deepcopy(cfg)
    stage_flags = {"proposer": proposer_model, "arc": arc_model, "judge": judge_model}
    overridden = []
    for stage in STAGES:
        new_model = stage_flags[stage] or model
        if new_model:
            cfg["models"][stage]["model"] = new_model
            overridden.append(stage)
    endpoint_stages = overridden or list(STAGES)
    for stage in endpoint_stages:
        if api_base:
            cfg["models"][stage]["api_base"] = api_base
        if api_key_env:
            cfg["models"][stage]["api_key_env"] = api_key_env
    cfg["mock"] = bool(mock or cfg.get("mock"))
    cfg["no_cache"] = bool(no_cache or cfg.get("no_cache"))
    return cfg
