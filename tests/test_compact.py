"""Compact view tests (TECH_SPEC §4.1): the exact text the LLM sees, built from the synthetic show."""

from pathlib import Path

import pytest

from promo_finder.aliases import load_aliases
from promo_finder.compact import compact_episode, estimate_tokens, format_tc
from promo_finder.parse import load_pack

EXAMPLE = Path(__file__).resolve().parent.parent / "config" / "aliases.example.yaml"


@pytest.fixture
def episodes(synth_dir):
    aliases, _ = load_aliases(EXAMPLE)
    eps, _ = load_pack(synth_dir, aliases)
    return {ep.ep: ep for ep in eps}


@pytest.mark.parametrize("seconds, expected", [
    (0.0, "00:00.0"),
    (13.0, "00:13.0"),
    (14.8, "00:14.8"),
    (112.0, "01:52.0"),
    (59.96, "01:00.0"),   # rounds up across the minute, never "00:60.0"
    (3723.25, "62:03.3"),   # half rounds up
])
def test_format_tc(seconds, expected):
    assert format_tc(seconds) == expected


def test_dialogue_line_matches_spec_format(episodes):
    lines = compact_episode(episodes[3]).splitlines()
    assert '[E03-B011 00:13.0–00:14.8] MARA (Stunned, Quiet): "You sold the house?"' in lines


def test_camera_line(episodes):
    lines = compact_episode(episodes[3]).splitlines()
    assert "[E03-B010 00:12.0–00:15.5] CAM: Close-up: Mara freezes at the door, an envelope in her hand." in lines


def test_action_and_sfx_prefixes(episodes):
    text = compact_episode(episodes[1])
    assert "[E01-B002 00:01.0–00:04.0] ACT: Mara pushes through the door" in text
    assert "[E01-B003 00:01.5–00:02.5] SFX: Thunder rolls." in text


def test_alias_and_flags_shown(episodes):
    lines = compact_episode(episodes[1]).splitlines()
    assert '[E01-B012 00:21.0–00:23.0] ELLIS [O.S.]: "Give the girl her locket."' in lines
    assert '[E01-B013 00:24.0–00:25.5] VERA (Startled) [O.S.]: "Who said that?"' in lines


def test_header_and_scene_markers(episodes):
    lines = compact_episode(episodes[3]).splitlines()
    assert lines[0] == "EPISODE 3 · duration 01:52.0"
    assert lines[1].startswith("LOGLINE: Mara learns her aunt sold the family house")
    assert lines[2].startswith("CONTINUITY: Same night as episode 2.")
    assert "## SCENE 2 · EXT. HARBOR – NIGHT · 00:52.0–01:52.0" in lines


def test_one_line_per_block(episodes):
    lines = compact_episode(episodes[3]).splitlines()
    assert sum(1 for line in lines if line.startswith("[E03-B")) == 41


def test_cast_line_only_when_cast_given(episodes):
    _, cast = load_aliases(EXAMPLE)
    with_cast = compact_episode(episodes[1], cast)
    assert "CAST: Mara (young woman fighting her aunt for her inheritance); " in with_cast
    assert "CAST:" not in compact_episode(episodes[1])


def test_estimate_tokens():
    assert estimate_tokens("abcd" * 10) == 10
    assert estimate_tokens("") == 0


# --- shorter CAMERA lines for the proposer (D-031)

def test_camera_text_truncated_only_when_asked(episodes):
    full = compact_episode(episodes[3]).splitlines()
    short = compact_episode(episodes[3], camera_max_chars=20).splitlines()
    assert len(full) == len(short)
    for f, s in zip(full, short):
        if " CAM: " in f:
            text = s.split(" CAM: ", 1)[1]
            assert len(text) <= 20
            if len(f.split(" CAM: ", 1)[1]) > 20:
                assert text.endswith("…")
        else:
            assert f == s   # dialogue, action and SFX lines are never shortened


def test_shorten_keeps_short_text_and_marks_cuts():
    from promo_finder.compact import shorten
    assert shorten("Close-up.", 70) == "Close-up."
    assert shorten("a" * 80, 70) == "a" * 69 + "…"
    assert shorten("a" * 80, None) == "a" * 80
