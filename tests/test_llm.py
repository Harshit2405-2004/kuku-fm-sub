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
