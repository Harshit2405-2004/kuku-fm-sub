"""Arc tests (TECH_SPEC §4.4): IDs-only pairing, shot-snapped parts, 20–60 s, hook in segment 1, rejections."""

import json
from pathlib import Path
from types import SimpleNamespace

import pytest

from promo_finder.aliases import load_aliases
from promo_finder.arcs import ArcPick, build_arc, build_messages, propose_arcs
from promo_finder.build import Candidate, build_candidate
from promo_finder.config import load_config
from promo_finder.llm import load_prompt
from promo_finder.mock import mock_proposer
from promo_finder.parse import load_pack
from promo_finder.propose import build_messages as proposer_messages

ROOT = Path(__file__).resolve().parent.parent


@pytest.fixture(scope="module")
def episodes():
    aliases, _ = load_aliases(ROOT / "config" / "aliases.example.yaml")
    eps, _ = load_pack(ROOT / "samples" / "synthetic_show", aliases)
    return {e.ep: e for e in eps}


@pytest.fixture(scope="module")
def bcfg():
    return load_config(ROOT / "config.yaml")["build"]


@pytest.fixture(scope="module")
def singles(episodes, bcfg):
    out = []
    for n, ep in episodes.items():
        for k, p in enumerate(mock_proposer(proposer_messages(ep, None))["candidates"], 1):
            c = build_candidate(ep, p, k, bcfg)
            if isinstance(c, Candidate):
                out.append(c)
    assert len({c.ep for c in out}) >= 2
    return out


def pick(opener, closer):
    return ArcPick(reasoning="r", opener=opener, closer=closer, hook_summary="h", cliff_summary="c")


def test_built_arc_is_valid(episodes, bcfg, singles):
    a, b = singles[0], singles[-1]
    arc = build_arc(1, pick(a.id, b.id), {c.id: c for c in singles}, episodes, bcfg)
    assert isinstance(arc, Candidate), arc
    assert arc.id == "ARC-1" and arc.type == "arc" and [s.ep for s in arc.segments] == [a.ep, b.ep]
    assert bcfg["min_duration_s"] <= arc.total_s <= bcfg["max_duration_s"]
    assert arc.segments[0].start == a.segments[0].start            # opens exactly where the opener opens
    assert arc.segments[-1].end == b.segments[-1].end              # ends exactly on the closer's cliff cut
    assert all(s.end - s.start >= bcfg["arc_min_segment_s"] for s in arc.segments)
    assert arc.checks["hook_within_3s"] and arc.checks["ends_on_shot"]
    # The arc inherits the opener's start; a mid-shot opener stays flagged rather than silently "fixed".
    assert arc.checks["starts_on_shot"] == a.checks["starts_on_shot"]
    assert ("midshot_start" in arc.flags) == ("midshot_start" in a.flags)
    assert arc.hook_block == a.hook_block and arc.cliff_block == b.cliff_block


def test_unknown_and_same_episode_picks_are_rejected(episodes, bcfg, singles):
    by_id = {c.id: c for c in singles}
    assert build_arc(1, pick("P99-1", singles[0].id), by_id, episodes, bcfg)["reason"] == "unknown_candidate"
    same = singles[0]
    assert build_arc(2, pick(same.id, same.id), by_id, episodes, bcfg)["reason"] == "same_episode"


def test_prompt_lists_only_ids_and_summaries(episodes, singles):
    version, sections = load_prompt("arc")
    assert version == "arc_v1"
    user = build_messages(singles, episodes)[1]["content"]
    assert "{loglines}" not in user and "{candidates}" not in user
    assert f"{singles[0].id} | episode {singles[0].ep} |" in user
    assert "-B" not in user.split("Candidates")[1]          # no block IDs for the model to copy


def test_single_episode_input_makes_no_call(episodes, singles):
    one = [c for c in singles if c.ep == singles[0].ep]
    def boom(**kwargs):
        raise AssertionError("no call expected")
    assert propose_arcs(one, episodes, {"models": {}}, [], completion_fn=boom) == ([], [])


def test_propose_arcs_with_a_fake_model(episodes, bcfg, singles, tmp_path):
    cfg = load_config(ROOT / "config.yaml")
    cfg["cache_dir"] = str(tmp_path / "cache")
    cfg["models"]["arc"].update({"model": "openai/fake", "api_key_env": None})
    body = {"arcs": [pick(singles[0].id, singles[-1].id).model_dump(), pick("nope", singles[0].id).model_dump()]}
    reply = SimpleNamespace(choices=[SimpleNamespace(message=SimpleNamespace(content=json.dumps(body)), finish_reason="stop")],
                            usage=SimpleNamespace(prompt_tokens=1, completion_tokens=1))
    arcs, rejected = propose_arcs(singles, episodes, cfg, [], raw_path=tmp_path / "arcs_raw.json",
                                  completion_fn=lambda **kw: reply)
    assert [a.id for a in arcs] == ["ARC-1"] and [r["reason"] for r in rejected] == ["unknown_candidate"]
    assert json.loads((tmp_path / "arcs_raw.json").read_text(encoding="utf-8")) == body
