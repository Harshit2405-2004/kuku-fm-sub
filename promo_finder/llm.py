"""The single path for every LLM call: LiteLLM + per-stage config + cache + retries + JSON validation.

Pipeline position: propose.py, arcs.py and judge.py call `call_llm(stage, ...)`; the stage name picks
the model from config (D-005), so any LiteLLM model or OpenAI-compatible endpoint works per stage.
Models only ever return JSON matching a Pydantic schema of block IDs and judgements, never times (D-002).
"""

from __future__ import annotations

import json
import logging
import os
import re
import time
from typing import Callable

from pydantic import BaseModel, ValidationError

from promo_finder import mock
from promo_finder.cache import cache_get, cache_key, cache_put

log = logging.getLogger(__name__)

# HTTP statuses worth retrying: rate limit, timeout, and server-side errors.
RETRYABLE_STATUS = {408, 429, 500, 502, 503, 504}


class LLMOutputError(Exception):
    """The model's reply still didn't match the schema after the repair retry."""


def extract_json(text: str | None) -> str:
    """Pull the JSON object out of a reply that may have ``` fences or prose around it."""
    if not text:
        return ""
    fenced = re.search(r"```(?:json)?\s*(.*?)```", text, re.DOTALL)
    if fenced:
        text = fenced.group(1)
    start, end = text.find("{"), text.rfind("}")
    return text[start:end + 1] if start != -1 and end > start else text.strip()


def _status(error: Exception) -> int | None:
    return getattr(error, "status_code", None)


def _completion_kwargs(stage_cfg: dict, messages: list[dict], schema: type[BaseModel]) -> dict:
    kwargs = {"model": stage_cfg["model"], "messages": messages,
              "temperature": stage_cfg.get("temperature", 0), "max_tokens": stage_cfg.get("max_tokens", 4000)}
    if stage_cfg.get("api_base"):
        kwargs["api_base"] = stage_cfg["api_base"]
    key_env = stage_cfg.get("api_key_env")
    if key_env:
        key = os.environ.get(key_env)
        if not key:
            raise RuntimeError(f"environment variable {key_env} is not set (needed for model {stage_cfg['model']})")
        kwargs["api_key"] = key
    # Ask for schema-constrained JSON where the provider supports it, plain JSON mode otherwise.
    import litellm
    try:
        supports_schema = litellm.supports_response_schema(model=stage_cfg["model"])
    except Exception:
        supports_schema = False
    kwargs["response_format"] = schema if supports_schema else {"type": "json_object"}
    return kwargs


def _call_with_retries(completion_fn: Callable, kwargs: dict, retries: dict, sleep: Callable):
    """Exponential backoff on 429/5xx. If an endpoint rejects response_format, retry once without it."""
    max_attempts = retries.get("max_attempts", 5)
    base = retries.get("backoff_base_s", 2)
    for attempt in range(1, max_attempts + 1):
        try:
            return completion_fn(**kwargs)
        except Exception as error:
            status = _status(error)
            if status == 400 and "response_format" in kwargs and "response_format" in str(error):
                log.warning("%s rejected response_format; retrying without it", kwargs["model"])
                kwargs = {k: v for k, v in kwargs.items() if k != "response_format"}
                continue
            if status not in RETRYABLE_STATUS or attempt == max_attempts:
                raise
            wait = base * 2 ** (attempt - 1)
            log.warning("%s: HTTP %s, retry %d/%d in %ss", kwargs["model"], status, attempt, max_attempts - 1, wait)
            sleep(wait)
    raise RuntimeError("unreachable")


def call_llm(stage: str, messages: list[dict], schema: type[BaseModel], cfg: dict, prompt_version: str,
             usage: list[dict], completion_fn: Callable | None = None,
             sleep: Callable = time.sleep) -> tuple[BaseModel, str]:
    """Run one stage call. Returns (validated object, raw reply text) and appends usage records.

    Order: mock → cache → API (with retries) → validate → one repair retry → cache the valid reply.
    """
    stage_cfg = cfg["models"][stage]
    model = "mock" if cfg.get("mock") else stage_cfg["model"]
    key = cache_key(model, prompt_version, messages, schema.__name__)
    record = {"stage": stage, "model": model, "prompt_version": prompt_version,
              "prompt_tokens": 0, "completion_tokens": 0, "latency_s": 0.0, "cache_hit": False}

    if cfg.get("mock"):
        raw = mock.respond(stage, messages)
        usage.append(record)
        return schema.model_validate_json(raw), raw

    if not cfg.get("no_cache"):
        cached = cache_get(cfg.get("cache_dir", ".cache/llm"), key)
        if cached is not None:
            usage.append({**record, "cache_hit": True, "prompt_tokens": cached["prompt_tokens"],
                          "completion_tokens": cached["completion_tokens"]})
            return schema.model_validate_json(extract_json(cached["raw"])), cached["raw"]

    if completion_fn is None:
        import litellm
        completion_fn = litellm.completion
    retries = cfg.get("retries", {})
    attempt_messages = list(messages)
    repairs_left = retries.get("json_repair_attempts", 1)
    while True:
        kwargs = _completion_kwargs(stage_cfg, attempt_messages, schema)
        started = time.time()
        response = _call_with_retries(completion_fn, kwargs, retries, sleep)
        raw = response.choices[0].message.content or ""
        prompt_tokens = getattr(response.usage, "prompt_tokens", 0) or 0
        completion_tokens = getattr(response.usage, "completion_tokens", 0) or 0
        usage.append({**record, "prompt_tokens": prompt_tokens, "completion_tokens": completion_tokens,
                      "latency_s": round(time.time() - started, 2)})
        try:
            parsed = schema.model_validate_json(extract_json(raw))
        except (ValidationError, ValueError) as error:
            if repairs_left <= 0:
                raise LLMOutputError(f"{stage}: reply did not match {schema.__name__}: {error}") from error
            repairs_left -= 1
            log.warning("%s: invalid JSON from %s, asking for a repair", stage, model)
            attempt_messages = attempt_messages + [
                {"role": "assistant", "content": raw},
                {"role": "user", "content": f"That reply was not valid JSON for the required schema. Error:\n{error}\n"
                                            "Reply with the corrected JSON object only."},
            ]
            continue
        if not cfg.get("no_cache"):
            cache_put(cfg.get("cache_dir", ".cache/llm"), key,
                      {"model": model, "prompt_version": prompt_version, "raw": raw,
                       "prompt_tokens": prompt_tokens, "completion_tokens": completion_tokens})
        return parsed, raw


def summarize_usage(usage: list[dict]) -> dict:
    """Per-stage totals for the run manifest (NFR7)."""
    summary: dict[str, dict] = {}
    for r in usage:
        s = summary.setdefault(r["stage"], {"calls": 0, "cache_hits": 0, "prompt_tokens": 0,
                                            "completion_tokens": 0, "latency_s": 0.0, "models": []})
        s["calls"] += 1
        s["cache_hits"] += int(r["cache_hit"])
        s["prompt_tokens"] += r["prompt_tokens"]
        s["completion_tokens"] += r["completion_tokens"]
        s["latency_s"] = round(s["latency_s"] + r["latency_s"], 2)
        if r["model"] not in s["models"]:
            s["models"].append(r["model"])
    return summary
