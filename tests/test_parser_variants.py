"""Format-variant tests: protects the live interview run on a new pack (TECH_SPEC §10).

Each test mutates a synthetic episode's text and checks the parser still produces the right data,
or a warning instead of a crash.
"""

import re
import zipfile

import pytest

from promo_finder.parse import load_pack, parse_episode_text

EP1_FILE = "episode-001-Episode 9001.txt"


def parse(text, source=EP1_FILE):
    return parse_episode_text(text, source)


def to_hhmmss(match):
    return f"00:{match.group(1)}"


def test_hh_mm_ss_timestamps(synth_text):
    text = re.sub(r"(\d\d:\d\d\.\d\d)", to_hhmmss, synth_text(3))
    ep, warnings = parse(text, "episode-003-x.txt")
    b = next(b for b in ep.blocks if b.id == "E03-B011")
    assert (b.start, b.end) == (13.0, 14.8)
    assert ep.duration == 112.0
    assert warnings == []


@pytest.mark.parametrize("decimals", [1, 2, 3])
def test_one_to_three_decimals(synth_text, decimals):
    def fmt(m):
        seconds = float(m.group(2))
        return f"{m.group(1)}:{seconds:0{3 + decimals}.{decimals}f}"
    text = re.sub(r"(\d\d):(\d\d\.\d\d)", fmt, synth_text(3))
    ep, _ = parse(text, "episode-003-x.txt")
    b = next(b for b in ep.blocks if b.id == "E03-B011")
    assert (b.start, b.end) == (13.0, 14.8)


def test_crlf_line_endings(synth_text):
    ep, warnings = parse(synth_text(1).replace("\n", "\r\n"))
    assert len(ep.blocks) == 20
    assert ep.blocks[1].text.endswith("clutching a silver locket to her chest.")
    assert warnings == []


def test_extra_blank_lines_between_blocks(synth_text):
    ep, warnings = parse(synth_text(1).replace("\n\n", "\n\n\n\n"))
    assert len(ep.blocks) == 20
    assert warnings == []


def test_no_sound_fx_at_all(synth_text):
    text = re.sub(r"\*\*SOUND FX:\*\*\nStart:[^\n]*\n[^\n]*\n\n", "", synth_text(1))
    ep, warnings = parse(text)
    assert len(ep.blocks) == 18
    assert not any(b.type == "SOUND_FX" for b in ep.blocks)
    assert warnings == []


def test_unknown_label_becomes_dialogue_with_warning(synth_text):
    extra = "**TITLE CARD:**\nStart: (00:58.00) | End: (00:59.50)\nTO BE CONTINUED\n\n"
    text = synth_text(1).replace("--- SCRIPT END ---", extra + "--- SCRIPT END ---")
    ep, warnings = parse(text)
    last = ep.blocks[-1]
    assert (last.id, last.type, last.speaker_raw, last.text) == ("E01-B021", "DIALOGUE", "TITLE CARD", "TO BE CONTINUED")
    assert any("E01-B021" in w and "unquoted" in w for w in warnings)


def test_missing_time_line_skips_block_with_warning(synth_text):
    text = synth_text(1).replace("Start: (00:04.00) | End: (00:09.00)\n", "", 1)
    ep, warnings = parse(text)
    assert len(ep.blocks) == 19
    # IDs stay contiguous so downstream code can trust them.
    assert [b.id for b in ep.blocks] == [f"E01-B{n:03d}" for n in range(1, 20)]
    assert any("missing times" in w for w in warnings)


def test_end_before_start_warns(synth_text):
    text = synth_text(1).replace("Start: (00:05.00) | End: (00:07.00)", "Start: (00:07.00) | End: (00:05.00)")
    _, warnings = parse(text)
    assert any("E01-B005" in w and "end < start" in w for w in warnings)


def test_block_outside_scene_range_warns(synth_text):
    text = synth_text(1).replace("Start: (00:21.00) | End: (00:23.00)", "Start: (00:41.00) | End: (00:43.00)")
    _, warnings = parse(text)
    assert any("E01-B012" in w and "outside scene" in w for w in warnings)


def test_episode_with_no_dialogue_warns(synth_text):
    text = re.sub(r"\*\*(MARA|VERA|THE STRANGER)[^*]*:\*\*", "**ACTION:**", synth_text(1))
    _, warnings = parse(text)
    assert any("no dialogue" in w for w in warnings)


def test_episode_number_falls_back_to_filename(synth_text):
    text = synth_text(1).replace("EPISODE NUMBER: Episode 1\n", "")
    ep, _ = parse(text, "episode-017-Episode 123.txt")
    assert ep.ep == 17
    assert ep.blocks[0].id == "E17-B001"


def test_lowercase_header_keys(synth_text):
    text = synth_text(1).replace("EPISODE LOGLINE:", "Episode logline:").replace("Scene start:", "scene START:")
    ep, warnings = parse(text)
    assert ep.logline.startswith("Soaked and desperate")
    assert ep.scenes[0].start == 0.0
    assert warnings == []


def test_scene_start_and_end_on_one_line(synth_text):
    text = synth_text(1).replace("Scene start: 00:00.00\nScene end: 00:30.00", "Scene start: 00:00.00   Scene end: 00:30.00")
    ep, warnings = parse(text)
    assert (ep.scenes[0].start, ep.scenes[0].end) == (0.0, 30.0)
    assert warnings == []


def test_zip_with_nested_folder(tmp_path, synth_dir):
    archive = tmp_path / "pack.zip"
    with zipfile.ZipFile(archive, "w") as zf:
        for path in sorted(synth_dir.glob("*.txt"), reverse=True):  # written out of order on purpose
            zf.write(path, f"Some Show/{path.name}")
    eps, warnings = load_pack(archive)
    assert [ep.ep for ep in eps] == [1, 2, 3]
    assert warnings == []


def test_episodes_sorted_by_number_not_filename(tmp_path, synth_text):
    (tmp_path / "b.txt").write_text(synth_text(1), encoding="utf-8")
    (tmp_path / "a.txt").write_text(synth_text(2), encoding="utf-8")
    eps, _ = load_pack(tmp_path)
    assert [ep.ep for ep in eps] == [1, 2]


def test_empty_folder_raises_clear_error(tmp_path):
    with pytest.raises(ValueError, match="no episode .txt files"):
        load_pack(tmp_path)
