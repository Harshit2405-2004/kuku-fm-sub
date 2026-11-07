"""LLM layer tests with a fake completion function: no network, no keys (TECH_SPEC §5)."""

import json
from types import SimpleNamespace

import pytest
from pydantic import BaseModel

from promo_finder.cache import cache_key
from promo_finder.llm import LLMOutputError, call_llm, summarize_usage


class Answer(BaseModel):
    block_id: str
    reason: str


GOOD = json.dumps({"block_id": "E03-B011", "reason": "hook"})


def response(content, prompt_tokens=100, completion_tokens=20):
    return SimpleNamespace(
        choices=[SimpleNamespace(message=SimpleNamespace(content=content), finish_reason="stop")],
        usage=SimpleNamespace(prompt_tokens=prompt_tokens, completion_tokens=completion_tokens),
    )


class FakeCompletion:
    """Returns queued items in order; an Exception item is raised instead of returned."""

    def __init__(self, *items):
        self.items = list(items)
        self.calls = []

    def __call__(self, **kwargs):
        self.calls.append(kwargs)
        item = self.items.pop(0)
        if isinstance(item, Exception):
            raise item
        return item


class HTTPError(Exception):
    def __init__(self, status_code, message="error"):
        super().__init__(message)
        self.status_code = status_code


@pytest.fixture
def cfg(tmp_path, monkeypatch):
    monkeypatch.setenv("FAKE_KEY", "sk-secret-value")
    return {
        "models": {"proposer": {"model": "openai/fake-model", "api_base": "https://example.test/v1",
                                "api_key_env": "FAKE_KEY", "temperature": 0, "max_tokens": 500}},
        "retries": {"max_attempts": 3, "backoff_base_s": 2, "json_repair_attempts": 1},
        "cache_dir": str(tmp_path / "cache"),
        "no_cache": False,
        "mock": False,
    }


MESSAGES = [{"role": "user", "content": "pick the hook"}]


def run(cfg, fake, usage=None, version="test_v1", sleeps=None):
    usage = [] if usage is None else usage
    sleeps = [] if sleeps is None else sleeps
    return call_llm("proposer", MESSAGES, Answer, cfg, version, usage,
                    completion_fn=fake, sleep=sleeps.append), usage, sleeps


def test_valid_response_is_parsed_and_usage_recorded(cfg):
    fake = FakeCompletion(response(GOOD))
    (parsed, raw), usage, _ = run(cfg, fake)
    assert parsed == Answer(block_id="E03-B011", reason="hook")
    assert raw == GOOD
    assert usage[0]["stage"] == "proposer"
    assert (usage[0]["prompt_tokens"], usage[0]["completion_tokens"], usage[0]["cache_hit"]) == (100, 20, False)
    call = fake.calls[0]
    assert (call["model"], call["temperature"], call["api_base"]) == ("openai/fake-model", 0, "https://example.test/v1")
    assert call["api_key"] == "sk-secret-value"


def test_second_identical_call_is_a_free_cache_hit(cfg):
    run(cfg, FakeCompletion(response(GOOD)))
    fake = FakeCompletion()   # would fail if called
    (parsed, _), usage, _ = run(cfg, fake)
    assert parsed.block_id == "E03-B011"
    assert fake.calls == []
    assert usage[0]["cache_hit"] is True


def test_prompt_version_change_misses_cache(cfg):
    run(cfg, FakeCompletion(response(GOOD)))
    fake = FakeCompletion(response(GOOD))
    run(cfg, fake, version="test_v2")
    assert len(fake.calls) == 1


def test_cache_key_depends_on_model_version_messages_schema():
    base = cache_key("m", "v1", MESSAGES, "Answer")
    assert base != cache_key("m2", "v1", MESSAGES, "Answer")
    assert base != cache_key("m", "v2", MESSAGES, "Answer")
    assert base != cache_key("m", "v1", [{"role": "user", "content": "x"}], "Answer")
    assert base != cache_key("m", "v1", MESSAGES, "Other")
    assert base == cache_key("m", "v1", [dict(MESSAGES[0])], "Answer")


def test_no_cache_flag_always_calls(cfg):
    cfg["no_cache"] = True
    run(cfg, FakeCompletion(response(GOOD)))
    fake = FakeCompletion(response(GOOD))
    run(cfg, fake)
    assert len(fake.calls) == 1


def test_invalid_json_gets_one_repair_retry_with_the_error(cfg):
    fake = FakeCompletion(response('{"block_id": "E03-B011"}'), response(GOOD))
    (parsed, _), usage, _ = run(cfg, fake)
    assert parsed.reason == "hook"
    repair_messages = fake.calls[1]["messages"]
    assert repair_messages[-1]["role"] == "user"
    assert "reason" in repair_messages[-1]["content"]          # the validation error names the field
    assert repair_messages[-2] == {"role": "assistant", "content": '{"block_id": "E03-B011"}'}
    assert len(usage) == 2


def test_invalid_twice_raises(cfg):
    fake = FakeCompletion(response("not json"), response("still not json"))
    with pytest.raises(LLMOutputError):
        run(cfg, fake)


def test_fenced_json_with_prose_is_extracted(cfg):
    fake = FakeCompletion(response("Sure! Here it is:\n```json\n" + GOOD + "\n```\nHope that helps."))
    (parsed, _), _, _ = run(cfg, fake)
    assert parsed.block_id == "E03-B011"


def test_rate_limit_backs_off_exponentially(cfg):
    fake = FakeCompletion(HTTPError(429), HTTPError(503), response(GOOD))
    (parsed, _), _, sleeps = run(cfg, fake)
    assert parsed.block_id == "E03-B011"
    assert sleeps == [2, 4]


def test_persistent_rate_limit_raises_after_max_attempts(cfg):
    fake = FakeCompletion(HTTPError(429), HTTPError(429), HTTPError(429))
    with pytest.raises(HTTPError):
        run(cfg, fake)
    assert len(fake.calls) == 3


def test_non_retryable_error_is_not_retried(cfg):
    fake = FakeCompletion(HTTPError(401, "bad key"))
    with pytest.raises(HTTPError):
        run(cfg, fake)
    assert len(fake.calls) == 1


def test_endpoint_rejecting_response_format_is_retried_without_it(cfg):
    fake = FakeCompletion(HTTPError(400, "response_format is not supported"), response(GOOD))
    (parsed, _), _, _ = run(cfg, fake)
    assert parsed.block_id == "E03-B011"
    assert "response_format" in fake.calls[0]
    assert "response_format" not in fake.calls[1]


def test_key_value_never_stored(cfg, tmp_path):
    _, usage, _ = run(cfg, FakeCompletion(response(GOOD)))
    assert "sk-secret-value" not in json.dumps(usage)
    for path in (tmp_path / "cache").rglob("*.json"):
        assert "sk-secret-value" not in path.read_text(encoding="utf-8")


def test_missing_key_env_var_gives_clear_error(cfg, monkeypatch):
    monkeypatch.delenv("FAKE_KEY")
    with pytest.raises(RuntimeError, match="FAKE_KEY"):
        run(cfg, FakeCompletion(response(GOOD)))


def test_summarize_usage_per_stage():
    usage = [
        {"stage": "proposer", "model": "m", "prompt_tokens": 100, "completion_tokens": 10, "latency_s": 1.0, "cache_hit": False},
        {"stage": "proposer", "model": "m", "prompt_tokens": 50, "completion_tokens": 5, "latency_s": 0.0, "cache_hit": True},
        {"stage": "judge", "model": "j", "prompt_tokens": 7, "completion_tokens": 3, "latency_s": 2.0, "cache_hit": False},
    ]
    s = summarize_usage(usage)
    assert s["proposer"] == {"calls": 2, "cache_hits": 1, "prompt_tokens": 150, "completion_tokens": 15,
                             "latency_s": 1.0, "models": ["m"]}
    assert s["judge"]["calls"] == 1


# --- reasoning_effort (D-027): an optional per-stage config key, passed straight to LiteLLM

def test_reasoning_effort_passed_only_when_configured(cfg):
    fake = FakeCompletion(response(GOOD))
    run(cfg, fake)
    assert "reasoning_effort" not in fake.calls[0]
    cfg["models"]["proposer"]["reasoning_effort"] = "low"
    fake = FakeCompletion(response(GOOD))
    run(cfg, fake, version="test_v2")
    assert fake.calls[0]["reasoning_effort"] == "low"


def test_reasoning_effort_is_part_of_the_cache_key(cfg):
    run(cfg, FakeCompletion(response(GOOD)))
    cfg["models"]["proposer"]["reasoning_effort"] = "low"
    fake = FakeCompletion(response(GOOD))
    (_, _), usage, _ = run(cfg, fake)
    assert len(fake.calls) == 1 and usage[0]["cache_hit"] is False


def test_cache_key_unchanged_when_reasoning_effort_unset():
    # Existing cache entries (made before D-027) must stay valid.
    assert cache_key("m", "v1", MESSAGES, "Answer") == cache_key("m", "v1", MESSAGES, "Answer", reasoning_effort=None)
    assert cache_key("m", "v1", MESSAGES, "Answer") != cache_key("m", "v1", MESSAGES, "Answer", reasoning_effort="low")


def test_endpoint_rejecting_reasoning_effort_is_retried_without_it(cfg):
    cfg["models"]["proposer"]["reasoning_effort"] = "low"
    fake = FakeCompletion(HTTPError(400, "Unsupported parameter: reasoning_effort"), response(GOOD))
    (parsed, _), _, _ = run(cfg, fake)
    assert parsed.block_id == "E03-B011"
    assert "reasoning_effort" in fake.calls[0]
    assert "reasoning_effort" not in fake.calls[1]


# --- retry-after (D-030): wait as long as the provider says, not a fixed backoff

class RateLimited(HTTPError):
    def __init__(self, headers=None, message="rate limited"):
        super().__init__(429, message)
        self.litellm_response_headers = headers or {}


@pytest.mark.parametrize("headers, message, expected", [
    ({"retry-after": "7"}, "", 7.5),                                   # plain seconds, + 0.5 s margin
    ({"x-ratelimit-reset-tokens": "7.66s"}, "", 8.16),                 # Groq TPM window
    ({"x-ratelimit-reset-tokens": "1m2.5s"}, "", 63.0),
    ({"x-ratelimit-reset-tokens": "712ms"}, "", 1.212),
    ({}, "Rate limit reached. Please try again in 12.3s. Need more tokens?", 12.8),  # Groq body text
    ({"retry-after": "3", "x-ratelimit-reset-tokens": "20s"}, "", 20.5),  # the longest hint wins
])
def test_retry_after_hints_are_honoured(cfg, headers, message, expected):
    fake = FakeCompletion(RateLimited(headers, message), response(GOOD))
    (parsed, _), _, sleeps = run(cfg, fake)
    assert parsed.block_id == "E03-B011"
    assert sleeps == [pytest.approx(expected)]


def test_retry_after_longer_than_the_cap_fails_fast(cfg):
    # A daily quota (Gemini: "retryDelay": "64822s") will not clear within a run: stop, don't sleep for hours.
    cfg["retries"]["max_wait_s"] = 90
    fake = FakeCompletion(RateLimited({}, '{"retryDelay": "64822s"}'), response(GOOD))
    with pytest.raises(HTTPError):
        run(cfg, fake)
    assert len(fake.calls) == 1


def test_no_hint_falls_back_to_exponential_backoff(cfg):
    fake = FakeCompletion(RateLimited({}, "slow down"), response(GOOD))
    (_, _), _, sleeps = run(cfg, fake)
    assert sleeps == [2]


def test_provider_side_json_failure_is_retried(cfg):
    # Groq returns 400 json_validate_failed when the model ran out of tokens before writing JSON;
    # it is a generation failure, not a bad request, so another attempt can succeed.
    err = HTTPError(400, '{"error":{"message":"Failed to validate JSON.","code":"json_validate_failed","failed_generation":""}}')
    fake = FakeCompletion(err, response(GOOD))
    (parsed, _), _, sleeps = run(cfg, fake)
    assert parsed.block_id == "E03-B011" and len(fake.calls) == 2 and sleeps == [2]
