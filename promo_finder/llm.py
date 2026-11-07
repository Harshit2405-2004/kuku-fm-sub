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
from pathlib import Path
from typing import Callable

from pydantic import BaseModel, ValidationError

from promo_finder import mock
from promo_finder.cache import cache_get, cache_key, cache_put

log = logging.getLogger(__name__)

# HTTP statuses worth retrying: rate limit, timeout, and server-side errors.
RETRYABLE_STATUS = {408, 429, 500, 502, 503, 504}
# 400s that are really generation failures (Groq: the model ran out of tokens or broke the schema
# while decoding), so a second attempt can succeed (D-030).
RETRYABLE_400_MARKERS = ("json_validate_failed", "Failed to generate JSON", "Failed to validate JSON")


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


# Margin added to a provider's wait hint, so we don't retry a few ms before the window resets.
RETRY_MARGIN_S = 0.5
_DURATION_PART = re.compile(r"(\d+(?:\.\d+)?)(ms|h|m|s)")


def parse_duration(text: str) -> float | None:
    """'7' / '7.66s' / '712ms' / '1m2.5s' / '64822s' -> seconds; None if unreadable."""
    text = str(text).strip().strip('"')
    if re.fullmatch(r"\d+(?:\.\d+)?", text):
        return float(text)
    parts = _DURATION_PART.findall(text)
    if not parts or "".join(n + u for n, u in parts) != text.replace(" ", ""):
        return None
    scale = {"ms": 0.001, "s": 1, "m": 60, "h": 3600}
    return sum(float(n) * scale[u] for n, u in parts)


def _error_headers(error: Exception) -> dict[str, str]:
    """Response headers from a LiteLLM exception (or its httpx response), lower-cased."""
    for raw in (getattr(error, "litellm_response_headers", None),
                getattr(getattr(error, "response", None), "headers", None),
                getattr(error, "headers", None)):
        if raw:
            try:
                return {str(k).lower(): str(v) for k, v in dict(raw).items()}
            except (TypeError, ValueError):
                continue
    return {}


def retry_after_s(error: Exception) -> float | None:
    """The provider's own 'wait this long' hint on a 429, or None if it gave none (D-030).

    Sources, longest wins: the Retry-After header; Groq's x-ratelimit-reset-tokens (the per-minute
    token window), and x-ratelimit-reset-requests only when no requests are left; and the error text
    ("try again in 12.3s", Gemini's "retryDelay": "64822s").
    """
    headers = _error_headers(error)
    hints = []
    if "retry-after" in headers:
        hints.append(parse_duration(headers["retry-after"]))
    if "x-ratelimit-reset-tokens" in headers:
        hints.append(parse_duration(headers["x-ratelimit-reset-tokens"]))
    if headers.get("x-ratelimit-remaining-requests") == "0" and "x-ratelimit-reset-requests" in headers:
        hints.append(parse_duration(headers["x-ratelimit-reset-requests"]))
    text = str(error)
    for pattern in (r"try again in\s+([0-9.]+(?:ms|s|m|h)?(?:[0-9.]+(?:ms|s))?)", r'retryDelay"?\s*:\s*"([^"]+)"'):
        match = re.search(pattern, text, re.IGNORECASE)
        if match:
            hints.append(parse_duration(match.group(1)))
    hints = [h for h in hints if h is not None]
    return max(hints) + RETRY_MARGIN_S if hints else None


# Request settings that change the reply, so they go into the cache key (D-034).
CACHE_SETTINGS = ("api_base", "temperature", "max_tokens", "reasoning_effort")
# response_format fallbacks when an endpoint rejects one: schema -> plain JSON mode -> nothing.
JSON_MODE = {"type": "json_object"}


def _completion_kwargs(stage_cfg: dict, messages: list[dict], schema: type[BaseModel],
                       rejected: set[str] | None = None) -> dict:
    """Request arguments for one call, minus anything this model already rejected in this run."""
    rejected = rejected or set()
    kwargs = {"model": stage_cfg["model"], "messages": messages,
              "temperature": stage_cfg.get("temperature", 0), "max_tokens": stage_cfg.get("max_tokens", 4000)}
    if stage_cfg.get("api_base"):
        kwargs["api_base"] = stage_cfg["api_base"]
    # Optional thinking budget ("minimal"/"low"/"medium"/"high"). LiteLLM maps this one OpenAI-style
    # name to each provider's own control (Gemini 3: thinkingLevel), so it is config-only (D-027).
    if stage_cfg.get("reasoning_effort") and "reasoning_effort" not in rejected:
        kwargs["reasoning_effort"] = stage_cfg["reasoning_effort"]
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
    if supports_schema and "response_format:schema" not in rejected:
        kwargs["response_format"] = schema
    elif "response_format:json_object" not in rejected:
        kwargs["response_format"] = JSON_MODE
    return kwargs


def _rejected_param(error: Exception, kwargs: dict) -> str | None:
    """Which optional setting a 400 rejects, as a key for the per-run 'rejected' set; None if none."""
    text = str(error)
    if "reasoning_effort" in kwargs and "reasoning_effort" in text:
        return "reasoning_effort"
    if "response_format" in kwargs and "response_format" in text:
        return "response_format:json_object" if kwargs["response_format"] == JSON_MODE else "response_format:schema"
    return None


def _retry_wait(error: Exception, status: int | None, attempt: int, retries: dict) -> float | None:
    """Seconds to wait before the next attempt, or None if this error shouldn't be retried."""
    generation_failure = status == 400 and any(m in str(error) for m in RETRYABLE_400_MARKERS)
    if status not in RETRYABLE_STATUS and not generation_failure:
        return None
    # Wait as long as the provider says (a 60 s token window outlasts a 2-4-8-16 s backoff);
    # if it says hours (a daily quota), waiting can't help: don't retry.
    hint = retry_after_s(error) if status == 429 else None
    if hint is not None and hint > retries.get("max_wait_s", 120):
        log.error("provider asks to wait %.0f s (> max_wait_s); giving up", hint)
        return None
    return hint if hint is not None else retries.get("backoff_base_s", 2) * 2 ** (attempt - 1)


def _call_with_retries(completion_fn: Callable, stage_cfg: dict, messages: list[dict], schema: type[BaseModel],
                       retries: dict, sleep: Callable, rejected: set[str]):
    """One API call with retries (D-030, D-034).

    Two separate budgets: `max_attempts` counts real failures (429, 5xx, generation-failure 400s);
    dropping a setting the endpoint rejects is free, and there are only three to drop, so the loop
    always ends with either a reply or the provider's real error.
    Generation failures are checked first: their error text can quote "response_format".
    """
    max_attempts = retries.get("max_attempts", 5)
    attempt = 0
    while True:
        kwargs = _completion_kwargs(stage_cfg, messages, schema, rejected)
        try:
            return completion_fn(**kwargs)
        except Exception as error:
            status = _status(error)
            generation_failure = status == 400 and any(m in str(error) for m in RETRYABLE_400_MARKERS)
            dropped = None if generation_failure or status != 400 else _rejected_param(error, kwargs)
            if dropped and dropped not in rejected:
                # Remembered for the rest of the run, so later calls to this model skip it at once.
                log.warning("%s rejected %s; dropping it for this run", kwargs["model"], dropped)
                rejected.add(dropped)
                continue
            attempt += 1
            wait = _retry_wait(error, status, attempt, retries)
            if wait is None or attempt >= max_attempts:
                raise
            log.warning("%s: HTTP %s, retry %d/%d in %.1fs", kwargs["model"], status, attempt, max_attempts - 1, wait)
            sleep(wait)


def call_llm(stage: str, messages: list[dict], schema: type[BaseModel], cfg: dict, prompt_version: str,
             usage: list[dict], completion_fn: Callable | None = None,
             sleep: Callable = time.sleep) -> tuple[BaseModel, str]:
    """Run one stage call. Returns (validated object, raw reply text) and appends usage records.

    Order: mock → cache → API (with retries) → validate → one repair retry → cache the valid reply.
    """
    stage_cfg = cfg["models"][stage]
    model = "mock" if cfg.get("mock") else stage_cfg["model"]
    settings = None if cfg.get("mock") else {k: stage_cfg.get(k) for k in CACHE_SETTINGS}
    key = cache_key(model, prompt_version, messages, schema.__name__, settings)
    record = {"stage": stage, "model": model, "prompt_version": prompt_version,
              "reasoning_effort": None if cfg.get("mock") else stage_cfg.get("reasoning_effort"),
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
    # Settings this model's endpoint rejected earlier in the run (kept in the run's config dict,
    # not a module global, so each run and each test starts clean).
    rejected = cfg.setdefault("_rejected_params", {}).setdefault(stage_cfg["model"], set())
    attempt_messages = list(messages)
    repairs_left = retries.get("json_repair_attempts", 1)
    while True:
        started = time.time()
        response = _call_with_retries(completion_fn, stage_cfg, attempt_messages, schema, retries, sleep, rejected)
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


PROMPTS_DIR = Path(__file__).resolve().parent / "prompts"


def load_prompt(name: str) -> tuple[str, dict[str, str]]:
    """Read prompts/<name>.md -> (version, {"system": ..., "user": ...}).

    The version comes from the `<!-- version: x -->` header and goes into the cache key and
    the manifest, so editing a prompt without bumping it would serve stale cached replies.
    """
    text = (PROMPTS_DIR / f"{name}.md").read_text(encoding="utf-8")
    version = re.search(r"<!--\s*version:\s*(\S+)\s*-->", text)
    if not version:
        raise ValueError(f"prompt {name}.md has no version header")
    body = re.sub(r"<!--.*?-->\n?", "", text, flags=re.DOTALL)
    parts = re.split(r"^## (SYSTEM|USER)\s*$", body, flags=re.MULTILINE)
    sections = {parts[i].lower(): parts[i + 1].strip() for i in range(1, len(parts) - 1, 2)}
    return version.group(1), sections
