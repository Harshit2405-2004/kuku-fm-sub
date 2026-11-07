"""Gold worksheet tools (EVAL_PLAN §1): synthetic show only, never the real pack or real labels."""

import csv
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))
import gold_from_worksheet as gfw  # noqa: E402
import make_gold_worksheet as mgw  # noqa: E402

from promo_finder.aliases import load_aliases  # noqa: E402
from promo_finder.parse import load_pack  # noqa: E402

TEMPLATE_PROMO = "- promo: start=B___ hook=B___ cliff=B___ end=B___ quality=_ note="


@pytest.fixture
def episodes(synth_dir):
    aliases, _ = load_aliases(ROOT / "config" / "aliases.example.yaml")
    eps, _ = load_pack(synth_dir, aliases)
    return eps


@pytest.fixture
def blank(episodes):
    return mgw.make_worksheet(episodes, [3, 1, 2])


def fill(worksheet: str, answers: dict[int, list[str]]) -> str:
    """Put answer lines under each '### My picks for Enn' header, the way Harshit would."""
    out = []
    for line in worksheet.splitlines():
        out.append(line)
        if line.startswith("### My picks for E"):
            out += answers.get(int(line[-2:]), [])
    return "\n".join(out)


# --- worksheet generator

def test_worksheet_lists_every_block_in_episode_order(blank, episodes):
    assert blank.index("## E01") < blank.index("## E02") < blank.index("## E03")
    for ep in episodes:
        for block in ep.blocks:
            assert f"\n{block.id.split('-')[1]} " in blank


def test_worksheet_line_formats(blank):
    lines = blank.splitlines()
    assert any(l.startswith("B002 00:01.0 ACT: ") for l in lines)
    assert any(l.startswith("B018 00:40.0 MARA") and ": " in l for l in lines)
    cams = [l for l in lines if " cam: " in l]
    assert cams and all(len(l.split(" cam: ", 1)[1]) <= mgw.CAMERA_MAX_CHARS for l in cams)
    assert any(l.startswith("--- SCENE 2 ") for l in lines)


def test_worksheet_has_rules_and_empty_answer_blocks(blank):
    assert blank.count("### My picks for E") == 3
    assert blank.count(TEMPLATE_PROMO) == 6
    assert "20–60 s" in blank and "arc: E01:B010-B030 + E42:B005-B020 quality=_ note=" in blank


def test_worksheet_rejects_unknown_episode(episodes):
    with pytest.raises(ValueError):
        mgw.make_worksheet(episodes, [1, 9])


# --- converter

def test_blank_worksheet_gives_no_rows_and_warns_per_episode(blank, episodes):
    result = gfw.parse_worksheet(blank, episodes)
    assert result.rows == [] and result.errors == []
    assert len(result.warnings) == 3


def test_filled_worksheet_to_rows(blank, episodes):
    filled = fill(blank, {
        1: ["- promo: start=B002 hook=B002 cliff=B009 end=B009 quality=1 note=too short on purpose"],
        2: ["- none quiet one"],
        3: ["- promo: start=B010 hook=B11 cliff=E03-B030 end=B029 quality=3 note=sold the house, who signed?",
            "- arc: E01:B002-B006 + E03:B011-B030 quality=2 note=two episodes"],
    })
    result = gfw.parse_worksheet(filled, episodes)
    assert result.errors == []
    by_id = {r["gold_id"]: r for r in result.rows}
    assert [r["episode"] for r in result.rows] == [1, 2, 3, 1]
    assert by_id["G01"]["segments"] == "E01 00:01.0-00:16.0"
    assert by_id["G02"] == {"gold_id": "G02", "episode": 2, "segments": "NONE", "hook_block": "",
                            "cliff_block": "", "quality": 0, "notes": "quiet one"}
    # The PROCESS_GUIDE example: 12.0–47.0, 35 s.
    assert by_id["G03"]["segments"] == "E03 00:12.0-00:47.0"
    assert (by_id["G03"]["hook_block"], by_id["G03"]["cliff_block"]) == ("E03-B011", "E03-B030")
    assert by_id["G03"]["notes"] == "sold the house, who signed?"
    assert by_id["G04"]["segments"] == "E01 00:01.0-00:14.0;E03 00:13.0-00:46.2"
    assert (by_id["G04"]["hook_block"], by_id["G04"]["cliff_block"]) == ("E01-B002", "E03-B030")
    # Only the 15 s promo is outside 20–60 s (the arc is 13 + 33.2 = 46.2 s).
    assert len(result.warnings) == 1 and "15.0 s" in result.warnings[0]
    assert result.per_episode == {1: {"promo": 1, "arc": 1, "none": 0}, 2: {"promo": 0, "arc": 0, "none": 1},
                                  3: {"promo": 1, "arc": 0, "none": 0}}


def test_arc_with_explicit_hook_and_cliff(blank, episodes):
    filled = fill(blank, {1: ["arc: E01:B002-B006 + E03:B011-B030 hook=E01:B004 cliff=E03:B030 quality=3 note="]})
    row = gfw.parse_worksheet(filled, episodes).rows[0]
    assert (row["hook_block"], row["cliff_block"]) == ("E01-B004", "E03-B030")


@pytest.mark.parametrize("line, expected", [
    ("- promo: start=B002 hook=B999 cliff=B009 end=B009 quality=2 note=", "does not exist"),
    ("- promo: start=B002 hook=B018 cliff=B009 end=B009 quality=2 note=", "order"),
    ("- promo: start=B002 hook=B002 cliff=B009 end=B009 quality=_ note=", "quality"),
    ("- promo: start=B002 hook=B002 cliff=B009 end=B009 quality=5 note=", "quality"),
    ("- promo: start=B002 hook=B___ cliff=B009 end=B009 quality=2 note=", "not a block ID"),
    ("- promo: start=B002 hook=E03-B011 cliff=B009 end=B009 quality=2 note=", "not in episode 1"),
    ("arc: E01:B020-B002 quality=2 note=", "ends before it starts"),
    ("arc: E01:B002-B006 hook=E02:B004 quality=2 note=", "not inside any segment"),
])
def test_errors(blank, episodes, line, expected):
    result = gfw.parse_worksheet(fill(blank, {1: [line]}), episodes)
    assert result.rows == [] and len(result.errors) == 1 and expected in result.errors[0]


def test_none_plus_picks_warns(blank, episodes):
    filled = fill(blank, {1: ["- none", "- promo: start=B002 hook=B002 cliff=B018 end=B018 quality=2 note="]})
    assert any("marked 'none'" in w for w in gfw.parse_worksheet(filled, episodes).warnings)


# --- CLI: writes the CSV only when there are no errors, never overwrites silently

def run_cli(*args):
    return subprocess.run([sys.executable, str(ROOT / "scripts" / "gold_from_worksheet.py"), *args],
                          capture_output=True, text=True, encoding="utf-8")


def test_cli_writes_csv_in_eval_plan_format(blank, synth_dir, tmp_path):
    sheet, out = tmp_path / "w.md", tmp_path / "gold.csv"
    sheet.write_text(fill(blank, {3: ["- promo: start=B010 hook=B011 cliff=B030 end=B029 quality=3 note=x, y"],
                                  2: ["- none"]}), encoding="utf-8")
    proc = run_cli("--worksheet", str(sheet), "--input", str(synth_dir), "--out", str(out))
    assert proc.returncode == 0, proc.stdout + proc.stderr
    assert "E03: promo 1" in proc.stdout and "WARN E01: no picks" in proc.stdout
    with out.open(encoding="utf-8") as f:
        rows = list(csv.DictReader(f))
    assert list(rows[0]) == gfw.CSV_COLUMNS
    assert rows[1] == {"gold_id": "G02", "episode": "3", "segments": "E03 00:12.0-00:47.0",
                       "hook_block": "E03-B011", "cliff_block": "E03-B030", "quality": "3", "notes": "x, y"}
    # A second run refuses to overwrite; --force allows it.
    assert run_cli("--worksheet", str(sheet), "--input", str(synth_dir), "--out", str(out)).returncode == 1
    assert run_cli("--worksheet", str(sheet), "--input", str(synth_dir), "--out", str(out), "--force").returncode == 0


def test_cli_writes_nothing_on_errors(blank, synth_dir, tmp_path):
    sheet, out = tmp_path / "w.md", tmp_path / "gold.csv"
    sheet.write_text(fill(blank, {1: ["- promo: start=B002 hook=B999 cliff=B009 end=B009 quality=2 note="]}),
                     encoding="utf-8")
    proc = run_cli("--worksheet", str(sheet), "--input", str(synth_dir), "--out", str(out))
    assert proc.returncode == 1 and "not written" in proc.stdout and not out.exists()


# --- reviewer's input checks (CP-2): malformed arc points, arc order, Note= case

@pytest.mark.parametrize("line, expected", [
    ("arc: E01:B002-B006 + E03:B011-B030 hook=E01:B1x2 quality=2 note=", "hook=E01:B1x2"),
    ("arc: E01:B002-B006 + E03:B011-B030 hook=B004 quality=2 note=", "hook=B004"),
    ("arc: E01:B002-B006 + E03:B011-B030 cliff=E03:B___ quality=2 note=", "cliff=E03:B___"),
])
def test_malformed_arc_point_is_an_error_not_a_silent_default(blank, episodes, line, expected):
    result = gfw.parse_worksheet(fill(blank, {1: [line]}), episodes)
    assert result.rows == [] and len(result.errors) == 1 and expected in result.errors[0]


def test_arc_point_with_trailing_comma_is_accepted(blank, episodes):
    line = "arc: E01:B002-B006 + E03:B011-B030 hook=E01:B004, cliff=E03:B030, quality=2 note="
    row = gfw.parse_worksheet(fill(blank, {1: [line]}), episodes).rows[0]
    assert (row["hook_block"], row["cliff_block"]) == ("E01-B004", "E03-B030")


def test_arc_segments_out_of_order_warn(blank, episodes):
    result = gfw.parse_worksheet(fill(blank, {1: ["arc: E03:B011-B030 + E01:B002-B006 quality=2 note="]}), episodes)
    assert result.errors == [] and len(result.rows) == 1
    assert any("not in episode/time order" in w for w in result.warnings)


def test_note_key_is_case_insensitive_and_its_text_is_never_parsed(blank, episodes):
    line = "- promo: start=B010 hook=B011 cliff=B030 end=B029 quality=3 Note= the hook=B5 moment"
    row = gfw.parse_worksheet(fill(blank, {3: [line]}), episodes).rows[0]
    assert row["hook_block"] == "E03-B011" and row["notes"] == "the hook=B5 moment"
