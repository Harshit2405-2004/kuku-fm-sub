"""On-disk cache for LLM responses, so reruns are free and reproducible (hard rule 8, D-011).

Pipeline position: used only by llm.call_llm. The key is a hash of (model, prompt version,
messages, schema name): change any of them and the call is made fresh.
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path


def cache_key(model: str, prompt_version: str, messages: list[dict], schema_name: str) -> str:
    payload = json.dumps([model, prompt_version, messages, schema_name], sort_keys=True, ensure_ascii=False)
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def cache_get(cache_dir: Path | str, key: str) -> dict | None:
    path = Path(cache_dir) / f"{key}.json"
    if not path.exists():
        return None
    return json.loads(path.read_text(encoding="utf-8"))


def cache_put(cache_dir: Path | str, key: str, record: dict) -> None:
    path = Path(cache_dir) / f"{key}.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    # Write to a temp file then rename, so a crash mid-write never leaves a half-written cache entry.
    tmp = path.with_suffix(".tmp")
    tmp.write_text(json.dumps(record, ensure_ascii=False, indent=1), encoding="utf-8")
    tmp.replace(path)
