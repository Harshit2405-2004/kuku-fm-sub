"""Parser tests on the synthetic show: exact counts, times and fields (TECH_SPEC §3, §10)."""

from collections import Counter

import pytest

from promo_finder.parse import load_pack, parse_speaker_label, parse_time


@pytest.fixture
def episodes(synth_dir):
    eps, _warnings = load_pack(synth_dir)
    return {ep.ep: ep for ep in eps}


def block(ep, block_id):
    return next(b for b in ep.blocks if b.id == block_id)


def test_loads_three_episodes_in_order(synth_dir):
    eps, warnings = load_pack(synth_dir)
    assert [ep.ep for ep in eps] == [1, 2, 3]
    assert warnings == []


@pytest.mark.parametrize("ep_num, expected", [
    (1, {"CAMERA": 8, "ACTION": 3, "SOUND_FX": 2, "DIALOGUE": 7}),
    (2, {"CAMERA": 6, "ACTION": 2, "SOUND_FX": 1, "DIALOGUE": 4}),
    (3, {"CAMERA": 18, "ACTION": 5, "SOUND_FX": 5, "DIALOGUE": 13}),
])
def test_block_counts_by_type(episodes, ep_num, expected):
    assert Counter(b.type for b in episodes[ep_num].blocks) == expected


def test_block_ids_are_sequential_in_file_order(episodes):
    ids = [b.id for b in episodes[3].blocks]
    assert ids[0] == "E03-B001"
    assert ids[-1] == "E03-B041"
    assert ids == [f"E03-B{n:03d}" for n in range(1, 42)]


def test_process_guide_worked_example_blocks(episodes):
    # PROCESS_GUIDE Process 1: the hook line of the worked example.
    b = block(episodes[3], "E03-B011")
    assert (b.ep, b.scene, b.type) == (3, 1, "DIALOGUE")
    assert (b.speaker_raw, b.emotion, b.flags) == ("MARA", "Stunned, Quiet", [])
    assert (b.start, b.end) == (13.0, 14.8)
    assert b.text == "You sold the house?"   # surrounding quotes stripped

    cam = block(episodes[3], "E03-B010")
    assert (cam.type, cam.start, cam.end, cam.speaker_raw) == ("CAMERA", 12.0, 15.5, None)
    assert (block(episodes[3], "E03-B029").start, block(episodes[3], "E03-B029").end) == (42.5, 47.0)
    assert block(episodes[3], "E03-B030").text == "Then who signed the deed?"
    assert block(episodes[3], "E03-B031").start == 47.4


def test_header_fields(episodes):
    ep = episodes[2]
    assert ep.logline.startswith("At the docks Ellis tells Mara")
    assert ep.continuity.startswith("Picks up the next morning.")
    assert ep.source_file == "episode-002-Episode 9002.txt"


def test_capitalised_scene_headers_parse(episodes):
    scenes = episodes[2].scenes
    assert [(s.num, s.heading, s.start, s.end) for s in scenes] == [
        (1, "EXT. HARBOR DOCKS – DAY", 0.0, 25.0),
        (2, "INT. VERA'S OFFICE – DAY", 25.0, 50.0),
    ]


def test_blocks_know_their_scene(episodes):
    assert block(episodes[1], "E01-B013").scene == 1
    assert block(episodes[1], "E01-B014").scene == 2


def test_os_flag_and_emotion(episodes):
    b = block(episodes[1], "E01-B012")
    assert (b.speaker_raw, b.emotion, b.flags) == ("THE STRANGER", None, ["O.S."])


def test_flag_inside_emotion_parens(episodes):
    b = block(episodes[1], "E01-B013")
    assert (b.speaker_raw, b.emotion, b.flags) == ("VERA", "Startled", ["O.S."])


def test_separate_flag_and_emotion_parens(episodes):
    b = block(episodes[2], "E02-B013")
    assert (b.speaker_raw, b.emotion, b.flags) == ("MARA", "Cold", ["O.S."])


def test_multiline_text_is_joined_with_a_space(episodes):
    assert block(episodes[1], "E01-B002").text == (
        "Mara pushes through the door, soaked to the bone, clutching a silver locket to her chest."
    )


def test_duration_is_max_of_block_end_and_scene_end(episodes):
    assert episodes[1].duration == 60.0
    assert episodes[3].duration == 112.0


def test_without_aliases_speaker_is_title_cased_raw(episodes):
    assert block(episodes[1], "E01-B012").speaker == "The Stranger"
    assert block(episodes[1], "E01-B001").speaker is None


def test_aliases_map_speaker_to_canonical(synth_dir):
    eps, _ = load_pack(synth_dir, aliases={"THE STRANGER": "Ellis"})
    assert block(eps[0], "E01-B012").speaker == "Ellis"


@pytest.mark.parametrize("label, expected", [
    ("MARA (Confused, Breathless)", ("MARA", "Confused, Breathless", [])),
    ("MARA (O.S.) (Emotion)", ("MARA", "Emotion", ["O.S."])),
    ("VERA (Harsh, O.S.)", ("VERA", "Harsh", ["O.S."])),
    ("VERA (O.S. / Low, Threatening)", ("VERA", "Low, Threatening", ["O.S."])),
    ("NARRATOR (V.O.)", ("NARRATOR", None, ["V.O."])),
    ("ELLIS", ("ELLIS", None, [])),
    ("ELLIS (Continuing)", ("ELLIS", "Continuing", [])),
])
def test_parse_speaker_label(label, expected):
    assert parse_speaker_label(label) == expected


@pytest.mark.parametrize("text, seconds", [
    ("00:13.50", 13.5),
    ("02:18.00", 138.0),
    ("1:05.5", 65.5),
    ("00:00:13.50", 13.5),
    ("01:02:03.125", 3723.125),
    ("00:07", 7.0),
])
def test_parse_time(text, seconds):
    assert parse_time(text) == pytest.approx(seconds)
