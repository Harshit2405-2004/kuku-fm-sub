"""Judge tests (TECH_SPEC §4.5): the excerpt is exactly what the viewer sees, the first 3 s are marked,
the brief's definition is quoted verbatim, batches and retries behave, and think text is ignored. No network.
"""

import json
import re
from pathlib import Path
from types import SimpleNamespace

import pytest

from promo_finder.aliases import load_aliases
from promo_finder.build import Candidate, Segment, build_candidate
from promo_finder.config import load_config
from promo_finder.judge import build_messages, excerpt, judge_candidates
from promo_finder.llm import extract_json, load_prompt
from promo_finder.parse import load_pack

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
    cfg["models"]["judge"].update({"model": "openai/fake", "api_key_env": None})
    return cfg


@pytest.fixture(scope="module")
def clip(episodes):
    proposal = {"reasoning": "r", "start_block": "E03-B010", "hook_block": "E03-B011", "cliff_block": "E03-B030",
                "end_block": "E03-B029", "beat_type": "betrayal_reveal", "hook_summary": "h", "cliff_summary": "c"}
    cand = build_candidate(episodes[3], proposal, 1, load_config(ROOT / "config.yaml")["build"])
    assert isinstance(cand, Candidate)
    return cand


def score(cid, hook=4):
    return {"id": cid, "hook_text": "h", "cliff_text": "c", "reasons": "r", "hook": hook, "cliff": 4,
            "standalone": 3, "trope_pull": 3, "pacing": 3, "why": "w", "risk_flags": []}


def reply(text):
    return SimpleNamespace(choices=[SimpleNamespace(message=SimpleNamespace(content=text), finish_reason="stop")],
                           usage=SimpleNamespace(prompt_tokens=10, completion_tokens=5))


class Fake:
    def __init__(self, *replies):
        self.replies, self.calls = list(replies), []

    def __call__(self, **kwargs):
        self.calls.append(kwargs)
        r = self.replies.pop(0)
        if isinstance(r, Exception):
            raise r
        return r


def test_both_prompts_quote_the_brief_definition_verbatim():
    compliance = (ROOT / "docs" / "BRIEF_COMPLIANCE.md").read_text(encoding="utf-8")
    definition = re.search(r"^> (A promo is .+)$", compliance, re.MULTILINE).group(1).strip()
    for name in ("proposer", "judge"):
        _, sections = load_prompt(name)
        assert definition in sections["system"], name


def test_judge_prompt_scores_hook_strength_not_presence():
    version, sections = load_prompt("judge")
    assert version == "judge_v1"
    system = sections["system"]
    assert "STRONG" in system and "not just that a line exists" in system
    assert "A vow is NOT a cliff" in system
    assert "viewer does NOT see" in system


def test_excerpt_is_the_viewer_lines_with_first_3s_marked(episodes, clip):
    text = excerpt(clip, episodes)
    lines = text.splitlines()
    assert lines[0].startswith(f"CLIP {clip.id} · single · ")
    blocks = [l for l in lines[1:]]
    seg = clip.segments[0]
    inside = [b for b in episodes[3].blocks if seg.start - 1e-6 <= b.start < seg.end - 1e-6]
    assert len(blocks) == len(inside)
    marked = [l for l in blocks if l.startswith(">> ")]
    assert marked and all(l.startswith(">> ") for l in blocks[:len(marked)])
    assert any("E03-B011" in l for l in marked)        # the hook is inside the first 3 s
    assert "E03-B030" in blocks[-1] or any("E03-B030" in l for l in blocks)
    assert "E03-B031" not in text                         # the answer after the cliff is not shown


def test_excerpt_marks_jump_cuts(episodes, clip):
    seg = clip.segments[0]
    mid = seg.start + 10
    two = clip.model_copy(update={"type": "jumpcut", "segments": [
        Segment(ep=3, start=seg.start, end=mid, start_block=seg.start_block, end_block=seg.start_block),
        Segment(ep=3, start=mid + 5, end=seg.end, start_block=seg.end_block, end_block=seg.end_block)]})
    assert excerpt(two, episodes).count("--- CUT ---") == 1


def test_messages_have_logline_as_editor_context_and_fill_placeholders(episodes, clip):
    messages = build_messages([clip], episodes)
    user = messages[1]["content"]
    assert "{clips}" not in user and "{count}" not in user
    assert "Editor context, viewer does NOT see this. Episode 3 logline:" in user


def test_batches_of_three_and_raw_saved(episodes, clip, cfg, tmp_path):
    cands = [clip.model_copy(update={"id": f"P03-{i}"}) for i in range(1, 5)]
    fake = Fake(reply(json.dumps({"scores": [score(f"P03-{i}") for i in (1, 2, 3)]})),
                reply(json.dumps({"scores": [score("P03-4")]})))
    scores, errors = judge_candidates(cands, episodes, cfg, [], raw_dir=tmp_path / "judge_raw", completion_fn=fake)
    assert len(fake.calls) == 2 and set(scores) == {"P03-1", "P03-2", "P03-3", "P03-4"} and errors == []
    assert sorted(p.name for p in (tmp_path / "judge_raw").iterdir()) == ["batch_001.json", "batch_002.json"]


def test_skipped_clip_is_retried_alone_and_unknown_ids_ignored(episodes, clip, cfg):
    cands = [clip.model_copy(update={"id": f"P03-{i}"}) for i in (1, 2)]
    fake = Fake(reply(json.dumps({"scores": [score("P03-1"), score("P99-9")]})),
                reply(json.dumps({"scores": [score("P03-2", hook=2)]})))
    scores, errors = judge_candidates(cands, episodes, cfg, [], completion_fn=fake)
    assert set(scores) == {"P03-1", "P03-2"} and scores["P03-2"].hook == 2 and errors == []
    assert "CLIP P03-2" in fake.calls[1]["messages"][1]["content"]
    assert "CLIP P03-1" not in fake.calls[1]["messages"][1]["content"]


def test_unscored_clip_is_reported_not_guessed(episodes, clip, cfg):
    fake = Fake(reply(json.dumps({"scores": []})), reply(json.dumps({"scores": []})))
    scores, errors = judge_candidates([clip], episodes, cfg, [], completion_fn=fake)
    assert scores == {} and errors == [{"id": clip.id, "error": "unscored after a single-clip retry"}]


def test_out_of_range_score_is_a_validation_error_then_repaired(episodes, clip, cfg):
    bad = score(clip.id); bad["hook"] = 7
    fake = Fake(reply(json.dumps({"scores": [bad]})), reply(json.dumps({"scores": [score(clip.id)]})))
    scores, _ = judge_candidates([clip], episodes, cfg, [], completion_fn=fake)
    assert scores[clip.id].hook == 4 and len(fake.calls) == 2


def test_think_text_with_braces_is_ignored():
    text = '<think>maybe {"scores": []} or not</think>\n{"scores": [1]}'
    assert json.loads(extract_json(text)) == {"scores": [1]}
    assert json.loads(extract_json('{"a": 1}')) == {"a": 1}


def test_mock_judge_scores_every_clip(episodes, clip, cfg):
    cfg["mock"] = True
    cands = [clip.model_copy(update={"id": f"P03-{i}"}) for i in (1, 2)]
    scores, errors = judge_candidates(cands, episodes, cfg, [])
    assert set(scores) == {"P03-1", "P03-2"} and errors == []
    assert scores["P03-1"].hook == 4    # the marked opening line is a question
