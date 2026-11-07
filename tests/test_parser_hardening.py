"""Regression tests for the CP-1 review findings: bad input must give warnings, never crashes or
silent drops. Every test mutates a synthetic-show episode (fictional), never the real pack.
"""

from promo_finder.compact import format_tc
from promo_finder.parse import load_pack, pack_stats, parse_episode_text, parse_speaker_label

EP1 = "episode-001-Episode 9001.txt"


def parse(text, source=EP1):
    return parse_episode_text(text, source)


def nonblank_count(text):
    return sum(1 for line in text.splitlines() if line.strip())


# --- malformed timestamps: warning + skip, never a crash

def test_malformed_block_time_skips_block_with_warning(synth_text):
    text = synth_text(1).replace("Start: (00:05.00) | End: (00:07.00)", "Start: (5.00) | End: (00:07.00)")
    ep, warnings = parse(text)
    assert len(ep.blocks) == 19
    assert [b.id for b in ep.blocks] == [f"E01-B{n:03d}" for n in range(1, 20)]
    assert any("bad time" in w for w in warnings)


def test_malformed_scene_time_warns_and_falls_back_to_blocks(synth_text):
    text = synth_text(1).replace("Scene end: 00:30.00", "Scene end: 0O:3O.00")
    ep, warnings = parse(text)
    assert ep.scenes[0].end == 30.0   # last block of scene 1 ends at 30.0
    assert any("bad time" in w for w in warnings)


# --- unknown formats: warning, never a silent drop

def test_bold_label_with_colon_outside_is_a_block(synth_text):
    text = synth_text(1).replace("**VERA (Cold):**", "**VERA (Cold)**:")
    ep, warnings = parse(text)
    assert len(ep.blocks) == 20
    assert ep.blocks[4].speaker_raw == "VERA"
    assert warnings == []


def test_blank_line_inside_text_reports_unassigned_line(synth_text):
    text = synth_text(1).replace("soaked to the bone,\nclutching", "soaked to the bone,\n\nclutching")
    ep, warnings = parse(text)
    assert ep.lines_unassigned == 1
    assert any("unassigned line" in w and "clutching" in w for w in warnings)


def test_stray_line_between_blocks_is_reported(synth_text):
    text = synth_text(1).replace("Thunder rolls.\n\n", "Thunder rolls.\n\nDIRECTOR NOTE: tighten this\n\n")
    ep, warnings = parse(text)
    assert len(ep.blocks) == 20
    assert ep.lines_unassigned == 1
    assert any("DIRECTOR NOTE" in w for w in warnings)


def test_missing_script_start_marker_still_parses(synth_text):
    ep, warnings = parse(synth_text(1).replace("--- SCRIPT START ---\n", ""))
    assert len(ep.blocks) == 20
    assert ep.logline.startswith("Soaked and desperate")
    assert any("no script start marker" in w for w in warnings)


def test_unknown_header_key_is_not_appended_to_logline(synth_text):
    text = synth_text(1).replace("CONTINUITY NOTES:", "WRITTEN BY: Someone\nCONTINUITY NOTES:")
    ep, warnings = parse(text)
    assert "WRITTEN BY" not in ep.logline
    assert any("unknown header" in w for w in warnings)


def test_duplicate_scene_number_warns_once(synth_text):
    text = synth_text(1).replace("SCENE 02", "SCENE 01")
    _, warnings = parse(text)
    assert sum("duplicate scene" in w for w in warnings) == 1


# --- coverage: every non-empty line is accounted for

def test_coverage_is_complete_on_clean_synthetic_episodes(synth_dir, synth_text):
    eps, _ = load_pack(synth_dir)
    for ep in eps:
        assert ep.lines_total == nonblank_count(synth_text(ep.ep))
        assert ep.lines_unassigned == 0
    stats = pack_stats(eps)
    assert stats["lines_unassigned"] == 0
    assert stats["lines_total"] == sum(nonblank_count(synth_text(n)) for n in (1, 2, 3))


# --- duration = max(block end, last scene end): each side must be able to win

def test_duration_uses_scene_end_when_it_is_later(synth_text):
    ep, _ = parse(synth_text(1).replace("Scene end: 01:00.00", "Scene end: 01:05.00"))
    assert ep.duration == 65.0


def test_duration_uses_block_end_when_it_is_later(synth_text):
    text = synth_text(1).replace("Start: (00:46.00) | End: (01:00.00)", "Start: (00:46.00) | End: (01:00.05)")
    ep, _ = parse(text)
    assert ep.duration == 60.05


# --- nits from the review

def test_flag_spelling_variants_are_recognised():
    assert parse_speaker_label("ELLIS (O.S)") == ("ELLIS", None, ["O.S."])
    assert parse_speaker_label("ELLIS (CONT’D)") == ("ELLIS", None, ["CONT'D"])
    assert parse_speaker_label("ELLIS (Off-screen, Angry)") == ("ELLIS", "Angry", ["O.S."])


def test_multiline_quoted_dialogue_joins_cleanly(synth_text):
    text = synth_text(1).replace('"Who are you?"', '"Who are you?"\n"Why help me?"')
    ep, _ = parse(text)
    assert next(b for b in ep.blocks if b.id == "E01-B018").text == "Who are you? Why help me?"


def test_format_tc_rounds_half_up():
    assert format_tc(0.25) == "00:00.3"
    assert format_tc(1.25) == "00:01.3"
    assert format_tc(0.35) == "00:00.4"
