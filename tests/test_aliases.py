"""Alias map tests (TECH_SPEC §3.4, §11): synthetic example file only."""

import logging
from pathlib import Path

from promo_finder.aliases import canonical_speaker, load_aliases
from promo_finder.parse import load_pack, pack_stats

EXAMPLE = Path(__file__).resolve().parent.parent / "config" / "aliases.example.yaml"


def test_load_example_aliases():
    aliases, cast = load_aliases(EXAMPLE)
    assert aliases["THE STRANGER"] == "Ellis"
    assert aliases["AUNT VERA"] == "Vera"
    assert cast["Ellis"].startswith("scarred stranger")


def test_keys_are_upper_cased(tmp_path):
    path = tmp_path / "a.yaml"
    path.write_text("aliases:\n  the stranger: Ellis\n", encoding="utf-8")
    aliases, cast = load_aliases(path)
    assert aliases == {"THE STRANGER": "Ellis"}
    assert cast == {}


def test_missing_file_gives_empty_maps_and_warns(tmp_path, caplog):
    with caplog.at_level(logging.WARNING):
        aliases, cast = load_aliases(tmp_path / "nope.yaml")
    assert (aliases, cast) == ({}, {})
    assert "no alias file" in caplog.text


def test_none_path_gives_empty_maps():
    assert load_aliases(None) == ({}, {})


def test_canonical_speaker_lookup_is_case_insensitive():
    assert canonical_speaker("The Stranger ", {"THE STRANGER": "Ellis"}) == "Ellis"


def test_canonical_speaker_falls_back_to_title_case():
    assert canonical_speaker("OLD FISHERMAN", {"MARA": "Mara"}) == "Old Fisherman"
    assert canonical_speaker("OLD FISHERMAN", None) == "Old Fisherman"


def test_pack_stats_on_synthetic_show(synth_dir):
    aliases, _ = load_aliases(EXAMPLE)
    eps, _ = load_pack(synth_dir, aliases)
    stats = pack_stats(eps)
    assert stats["episodes"] == 3
    assert stats["blocks"] == 74
    assert stats["blocks_by_type"] == {"CAMERA": 32, "ACTION": 10, "SOUND_FX": 8, "DIALOGUE": 24}
    assert (stats["duration_min"], stats["duration_max"], stats["duration_total"]) == (50.0, 112.0, 222.0)
    assert stats["scenes"] == 6
    # Raw label counts, and the canonical speakers they collapse to with the alias map.
    assert stats["raw_speakers"]["THE STRANGER"] == 2
    assert stats["speakers"]["Ellis"] == 5
    assert set(stats["speakers"]) == {"Mara", "Vera", "Ellis"}
