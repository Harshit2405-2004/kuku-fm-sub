"""Proposer tests (TECH_SPEC §4.2): IDs-only schema, validation, one repair retry, raw replies
saved unedited, and mock mode end to end through the builder. No network.
"""

import json
from pathlib import Path
from types import SimpleNamespace

import pytest

from promo_finder.aliases import load_aliases
from promo_finder.build import Candidate, build_candidate
from promo_finder.config import load_config
from promo_finder.llm import load_prompt
from promo_finder.parse import load_pack
from promo_finder.propose import EpisodeProposals, build_messages, propose_episode, validate_proposals

ROOT = Path(__file__).resolve().parent.parent


@pytest.fixture(scope="module")
def episodes():
    aliases, _ = load_aliases(ROOT / "config" / "aliases.example.yaml")
    eps, _ = load_pack(ROOT / "samples" / "synthetic_show", aliases)
    return {e.ep: e for e in eps}


@pytest.fixture
def cfg(tmp_path):
    cfg = load_config(ROOT / "config.yaml")
    cfg["cache_dir"] = str(tmp_path / "cache")
    cfg["models"]["proposer"].update({"model": "openai/fake", "api_key_env": None})
    return cfg


def cand(start="E03-B010", hook="E03-B011", cliff="E03-B030", end="E03-B029"):
    return {"reasoning": "r", "start_block": start, "hook_block": hook, "cliff_block": cliff,
            "end_block": end, "beat_type": "betrayal_reveal", "hook_summary": "h", "cliff_summary": "c"}


def reply(obj):
    return SimpleNamespace(choices=[SimpleNamespace(message=SimpleNamespace(content=json.dumps(obj)), finish_reason="stop")],
                           usage=SimpleNamespace(prompt_tokens=10, completion_tokens=5))


class Fake:
    def __init__(self, *replies):
        self.replies, self.calls = list(replies), []

    def __call__(self, **kwargs):
        self.calls.append(kwargs)
        return self.replies.pop(0)


def test_prompt_has_version_and_no_unfilled_placeholders(episodes):
    version, _ = load_prompt("proposer")
    assert version == "proposer_v1"
    messages = build_messages(episodes[3], None)
    assert [m["role"] for m in messages] == ["system", "user"]
    assert "[E03-B011 00:13.0–00:14.8]" in messages[1]["content"]
    assert "{compact}" not in messages[1]["content"] and "{episode}" not in messages[1]["content"]


def test_validate_accepts_good_candidate(episodes):
    props = EpisodeProposals(episode=3, candidates=[cand()])
    assert validate_proposals(episodes[3], props) == {}


@pytest.mark.parametrize("bad, reason", [
    (cand(hook="E03-B999"), "unknown block"),
    (cand(hook="E02-B004"), "unknown block"),       # another episode's ID
    (cand(hook="E03-B031", cliff="E03-B030"), "order"),
])
def test_validate_catches_bad_candidates(episodes, bad, reason):
    props = EpisodeProposals(episode=3, candidates=[cand(), bad])
    errors = validate_proposals(episodes[3], props)
    assert list(errors) == [1]
    assert reason in errors[1]


def test_validate_catches_wrong_episode_number(episodes):
    errors = validate_proposals(episodes[3], EpisodeProposals(episode=4, candidates=[cand()]))
    assert "episode" in errors[-1]


def test_beat_type_must_be_in_enum():
    with pytest.raises(ValueError):
        EpisodeProposals.model_validate({"episode": 3, "candidates": [{**cand(), "beat_type": "dance_off"}]})


def test_bad_candidate_gets_one_repair_then_succeeds(episodes, cfg, tmp_path):
    fake = Fake(reply({"episode": 3, "candidates": [cand(hook="E03-B999")]}),
                reply({"episode": 3, "candidates": [cand()]}))
    props, dropped = propose_episode(episodes[3], None, cfg, [], raw_dir=tmp_path / "raw", completion_fn=fake)
    assert [c.hook_block for c in props.candidates] == ["E03-B011"]
    assert dropped == []
    assert "E03-B999" in fake.calls[1]["messages"][-1]["content"]        # the error was sent back
    assert json.loads((tmp_path / "raw" / "E03.json").read_text(encoding="utf-8"))["candidates"][0]["hook_block"] == "E03-B999"
    assert (tmp_path / "raw" / "E03.repair.json").exists()               # both raw replies kept, unedited


def test_still_bad_after_repair_is_dropped_and_logged(episodes, cfg, tmp_path):
    bad = cand(hook="E03-B999")
    fake = Fake(reply({"episode": 3, "candidates": [cand(), bad]}), reply({"episode": 3, "candidates": [cand(), bad]}))
    props, dropped = propose_episode(episodes[3], None, cfg, [], raw_dir=tmp_path, completion_fn=fake)
    assert len(props.candidates) == 1
    assert dropped[0]["index"] == 1 and "unknown block" in dropped[0]["error"]


def test_zero_candidates_is_valid(episodes, cfg, tmp_path):
    fake = Fake(reply({"episode": 3, "candidates": []}))
    props, dropped = propose_episode(episodes[3], None, cfg, [], raw_dir=tmp_path, completion_fn=fake)
    assert (props.candidates, dropped, len(fake.calls)) == ([], [], 1)


def test_mock_mode_proposes_buildable_clips_for_every_synthetic_episode(episodes, cfg, tmp_path):
    cfg["mock"] = True
    for ep in episodes.values():
        props, dropped = propose_episode(ep, None, cfg, [], raw_dir=tmp_path)
        assert props.candidates and not dropped, ep.ep
        built = build_candidate(ep, props.candidates[0].model_dump(), 1, cfg["build"])
        assert isinstance(built, Candidate), built
        assert built.checks["dur_ok"] and built.checks["hook_within_3s"]


def test_mock_is_deterministic(episodes, cfg, tmp_path):
    cfg["mock"] = True
    a, _ = propose_episode(episodes[3], None, cfg, [], raw_dir=tmp_path)
    b, _ = propose_episode(episodes[3], None, cfg, [], raw_dir=tmp_path)
    assert a == b
