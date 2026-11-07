"""Cut-builder tests (TECH_SPEC §4.3, D-015). The numbers are the PROCESS_GUIDE Process 3 worked
examples: synthetic ep 3 for the single cut, and small hand-made fixtures for jump-cut / too-short.
"""

from pathlib import Path

import pytest

from promo_finder.build import (build_candidate, dedupe, interval_iou, snap_end, snap_start)
from promo_finder.config import load_config
from promo_finder.parse import Block, Episode, Scene, load_pack

ROOT = Path(__file__).resolve().parent.parent
BCFG = load_config(ROOT / "config.yaml")["build"]


def make_episode(spec, ep=7, duration=None):
    """spec: list of (type, start, end[, text]). CAMERA/ACTION/SOUND_FX/DIALOGUE; IDs in list order."""
    blocks = []
    for n, item in enumerate(spec, start=1):
        kind, start, end = item[:3]
        text = item[3] if len(item) > 3 else f"{kind.lower()} {n}"
        blocks.append(Block(id=f"E{ep:02d}-B{n:03d}", ep=ep, scene=1, type=kind,
                            speaker_raw="X" if kind == "DIALOGUE" else None,
                            speaker="X" if kind == "DIALOGUE" else None,
                            start=start, end=end, text=text))
    dur = duration or max(b.end for b in blocks)
    return Episode(ep=ep, source_file="fixture.txt", logline="", continuity="", duration=dur,
                   scenes=[Scene(ep=ep, num=1, heading="FIXTURE", start=0.0, end=dur)], blocks=blocks)


def proposal(ep, hook, cliff, start=None, end=None):
    return {"start_block": start or hook, "hook_block": hook, "cliff_block": cliff, "end_block": end or cliff,
            "beat_type": "twist", "hook_summary": "h", "cliff_summary": "c", "reasoning": "r"}


@pytest.fixture(scope="module")
def ep3(synth_dir_module):
    eps, _ = load_pack(synth_dir_module)
    return next(e for e in eps if e.ep == 3)


@pytest.fixture(scope="module")
def synth_dir_module():
    return ROOT / "samples" / "synthetic_show"


# --- PROCESS_GUIDE Process 3: the single-cut worked example on synthetic ep 3

def test_snap_start_worked_example(ep3):
    start, flags = snap_start(ep3, 13.0, BCFG)
    assert (start, flags) == (12.0, [])


def test_snap_end_worked_example(ep3):
    end, flags = snap_end(ep3, 46.2)
    assert (end, flags) == (47.0, [])


def test_single_cut_worked_example(ep3):
    cand = build_candidate(ep3, proposal(3, "E03-B011", "E03-B030"), 1, BCFG)
    assert cand.id == "P03-1"
    assert cand.type == "single"
    assert [(s.start, s.end) for s in cand.segments] == [(12.0, 47.0)]
    assert (cand.hook_offset_s, cand.total_s) == (1.0, 35.0)
    assert (cand.segments[0].start_block, cand.segments[0].end_block) == ("E03-B010", "E03-B029")
    assert all(cand.checks.values()), cand.checks
    assert cand.flags == []


# --- snapping rules

def test_snap_start_tie_picks_earlier_shot():
    ep = make_episode([("CAMERA", 0.0, 8.5), ("CAMERA", 8.5, 9.5), ("CAMERA", 9.5, 20.0), ("DIALOGUE", 10.0, 11.0)])
    start, flags = snap_start(ep, 10.0, BCFG)   # 8.5 and 9.5 are both 0.5 s from the 9.0 target
    assert (start, flags) == (8.5, [])


def test_snap_start_falls_back_to_containing_shot_within_3s():
    ep = make_episode([("CAMERA", 0.0, 7.2), ("CAMERA", 7.2, 20.0), ("DIALOGUE", 10.0, 11.0)])
    assert snap_start(ep, 10.0, BCFG) == (7.2, [])


def test_snap_start_midshot_when_no_shot_is_close_enough():
    ep = make_episode([("CAMERA", 0.0, 20.0), ("DIALOGUE", 10.0, 11.0)])
    assert snap_start(ep, 10.0, BCFG) == (10.0, ["midshot_start"])


def test_snap_end_cuts_at_cliff_when_a_line_would_leak():
    ep = make_episode([("CAMERA", 42.5, 47.0), ("DIALOGUE", 44.0, 46.2), ("DIALOGUE", 46.8, 47.5)])
    assert snap_end(ep, 46.2) == (46.2, ["midshot_end"])


def test_snap_end_on_exact_shot_boundary():
    ep = make_episode([("CAMERA", 40.0, 46.2), ("CAMERA", 46.2, 50.0), ("DIALOGUE", 44.0, 46.2)])
    assert snap_end(ep, 46.2) == (46.2, [])


# --- jump-cut (D-015): PROCESS_GUIDE numbers, 93 s hook-to-cliff, 94.5 s snapped -> 52 s

JUMPCUT_SHOTS = [0.0, 4.0, 9.0, 14.0, 19.5, 30.0, 45.0, 58.0, 60.5, 62.0, 80.0, 98.5, 102.0]


def jumpcut_episode(cliff=(95.0, 98.0)):
    spec = [("CAMERA", a, b) for a, b in zip(JUMPCUT_SHOTS, JUMPCUT_SHOTS[1:])]
    spec += [("DIALOGUE", 5.0, 7.0, "hook line"), ("DIALOGUE", 60.0, 61.0, "line across a cut"),
             ("DIALOGUE", cliff[0], cliff[1], "cliff line"), ("DIALOGUE", 99.0, 100.0, "answer")]
    return make_episode(spec)


def test_jumpcut_worked_example():
    ep = jumpcut_episode()
    hook, cliff = "E07-B013", "E07-B015"
    cand = build_candidate(ep, proposal(7, hook, cliff), 1, BCFG)
    assert cand.type == "jumpcut"
    assert [(s.start, s.end) for s in cand.segments] == [(4.0, 19.5), (62.0, 98.5)]
    assert cand.total_s == 52.0
    assert cand.hook_offset_s == 1.0
    assert "trimmed" in cand.flags
    assert all(cand.checks.values()), cand.checks


def test_jumpcut_rejected_when_cliff_line_cannot_fit():
    ep = jumpcut_episode(cliff=(55.0, 98.0))   # a 43 s cliff line can't fit the 39.5 s budget
    result = build_candidate(ep, proposal(7, "E07-B013", "E07-B015"), 1, BCFG)
    assert result.reason == "cliff_segment_too_long"


def test_jumpcut_s1_falls_back_to_last_boundary_before_limit():
    # No boundary in [start+12, start+25]; the last one between hook end and start+25 is used.
    spec = [("CAMERA", 4.0, 10.0), ("CAMERA", 10.0, 40.0), ("CAMERA", 40.0, 70.0), ("CAMERA", 70.0, 100.0),
            ("DIALOGUE", 5.0, 7.0), ("DIALOGUE", 95.0, 98.0)]
    cand = build_candidate(make_episode(spec), proposal(7, "E07-B005", "E07-B006"), 1, BCFG)
    assert [(s.start, s.end) for s in cand.segments] == [(4.0, 10.0), (70.0, 100.0)]   # 6 + 30 = 36 s


def test_jumpcut_s1_midshot_when_no_boundary_after_hook():
    spec = [("CAMERA", 4.0, 40.0), ("CAMERA", 40.0, 60.0), ("CAMERA", 60.0, 100.0),
            ("DIALOGUE", 5.0, 7.0), ("DIALOGUE", 95.0, 98.0)]
    cand = build_candidate(make_episode(spec), proposal(7, "E07-B004", "E07-B005"), 1, BCFG)
    assert [(s.start, s.end) for s in cand.segments] == [(4.0, 7.0), (60.0, 100.0)]    # 3 + 40 = 43 s
    assert "midshot_s1" in cand.flags


def test_jumpcut_that_ends_up_under_20s_is_rejected():
    spec = [("CAMERA", 4.0, 40.0), ("CAMERA", 40.0, 90.0), ("CAMERA", 90.0, 100.0),
            ("DIALOGUE", 5.0, 7.0), ("DIALOGUE", 95.0, 98.0)]
    result = build_candidate(make_episode(spec), proposal(7, "E07-B004", "E07-B005"), 1, BCFG)
    assert result.reason == "too_short"   # 3 s + 10 s: the only cut that fits leaves too little


# --- too short: PROCESS_GUIDE example, extended to 38.5 then rejected

def test_too_short_is_extended_then_rejected():
    spec = [("CAMERA", 10.0, 19.0), ("CAMERA", 19.0, 30.0), ("CAMERA", 30.0, 34.0), ("CAMERA", 34.0, 38.5),
            ("CAMERA", 38.5, 45.0), ("DIALOGUE", 20.0, 21.5), ("DIALOGUE", 31.0, 33.5), ("DIALOGUE", 39.0, 41.0)]
    result = build_candidate(make_episode(spec), proposal(7, "E07-B006", "E07-B007"), 1, BCFG)
    assert result.reason == "too_short"
    assert result.detail["duration_s"] == 19.5
    assert result.detail["end"] == 38.5


def test_too_short_is_extended_into_a_valid_clip():
    spec = [("CAMERA", 10.0, 19.0), ("CAMERA", 19.0, 30.0), ("CAMERA", 30.0, 34.0), ("CAMERA", 34.0, 38.5),
            ("CAMERA", 38.5, 41.0), ("DIALOGUE", 20.0, 21.5), ("DIALOGUE", 31.0, 33.5), ("DIALOGUE", 42.0, 43.0)]
    cand = build_candidate(make_episode(spec), proposal(7, "E07-B006", "E07-B007"), 1, BCFG)
    assert [(s.start, s.end) for s in cand.segments] == [(19.0, 41.0)]
    assert "extended" in cand.flags


# --- bad proposals are rejected, never crash

def test_unknown_block_is_rejected(ep3):
    assert build_candidate(ep3, proposal(3, "E03-B999", "E03-B030"), 1, BCFG).reason == "unknown_block"


def test_hook_after_cliff_is_rejected(ep3):
    assert build_candidate(ep3, proposal(3, "E03-B030", "E03-B011"), 1, BCFG).reason == "bad_order"


# --- dedupe and IoU

def test_interval_iou():
    assert interval_iou((12.0, 47.0), (10.0, 40.0)) == pytest.approx(28 / 37)
    assert interval_iou((0.0, 10.0), (20.0, 30.0)) == 0.0


def test_dedupe_keeps_first_listed(ep3):
    a = build_candidate(ep3, proposal(3, "E03-B011", "E03-B030"), 1, BCFG)
    b = build_candidate(ep3, proposal(3, "E03-B013", "E03-B030"), 2, BCFG)
    c = build_candidate(ep3, proposal(3, "E03-B037", "E03-B039"), 3, BCFG)
    kept, merged = dedupe([a, b, c], BCFG["dedupe_iou"])
    assert [k.id for k in kept] == ["P03-1", "P03-3"]
    assert merged[0]["dropped"] == "P03-2" and merged[0]["kept"] == "P03-1"
