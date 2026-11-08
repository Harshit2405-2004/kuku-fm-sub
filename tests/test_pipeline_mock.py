"""End-to-end in mock mode on the synthetic show (TECH_SPEC §10): every output file exists with a valid
schema, times come from block IDs, and the CLI works. No network, no API key.
"""

import csv
import json
from pathlib import Path

import pytest

import run as cli
from promo_finder.build import Candidate
from promo_finder.compact import format_tc
from promo_finder.config import apply_overrides, load_config
from promo_finder.parse import load_pack
from promo_finder.pipeline import run_pipeline
from promo_finder.report import CSV_COLUMNS

ROOT = Path(__file__).resolve().parent.parent
SYNTH = ROOT / "samples" / "synthetic_show"
ALIASES = ROOT / "config" / "aliases.example.yaml"
FILES = ["manifest.json", "episodes.json", "candidates.json", "rejected.json", "scored.json", "ranked.json",
         "promos.csv", "promos.json", "review.md", "run.log"]


@pytest.fixture(scope="module")
def run_dir(tmp_path_factory):
    cfg = apply_overrides(load_config(ROOT / "config.yaml"), mock=True)
    cfg["cache_dir"] = str(tmp_path_factory.mktemp("cache"))
    return run_pipeline(SYNTH, cfg, "mocktest", out_root=tmp_path_factory.mktemp("out"), aliases_path=ALIASES)


def test_all_output_files_exist(run_dir):
    for name in FILES:
        assert (run_dir / name).exists(), name
    assert any((run_dir / "proposals_raw").iterdir())
    assert any((run_dir / "judge_raw").iterdir())


def test_run_id_format(run_dir):
    date, hhmm, name = run_dir.name.split("-", 2)
    assert len(date) == 8 and len(hhmm) == 4 and name == "mocktest"


def test_manifest_schema(run_dir):
    m = json.loads((run_dir / "manifest.json").read_text(encoding="utf-8"))
    for key in ("run_id", "timestamp", "git_commit", "models", "prompt_versions", "episodes_parsed", "counts",
                "usage", "cost_usd", "timings_s", "errors", "config"):
        assert key in m, key
    assert m["mock"] is True and m["episodes_parsed"] == 3 and m["errors"] == []
    assert m["prompt_versions"] == {"proposer": "proposer_v4b", "arc": "arc_v1", "judge": "judge_v1"}
    assert m["counts"]["ranked"] >= 1 and m["counts"]["unscored"] == 0
    assert set(m["usage"]) == {"proposer", "arc", "judge"}
    assert '"api_key":' not in json.dumps(m["config"])   # env var NAMES only, never key values


def test_promos_json_times_come_from_blocks(run_dir):
    promos = json.loads((run_dir / "promos.json").read_text(encoding="utf-8"))
    episodes = {e.ep: e for e in load_pack(SYNTH)[0]}
    assert [p["rank"] for p in promos] == list(range(1, len(promos) + 1))
    for p in promos:
        assert 20 - 1e-6 <= p["total_sec"] <= 60 + 1e-6
        for seg in p["segments"]:
            blocks = {b.id: b for b in episodes[seg["episode"]].blocks}
            assert seg["start_block"] in blocks and seg["end_block"] in blocks
            assert seg["start_tc"] == format_tc(seg["start"]) and seg["end_tc"] == format_tc(seg["end"])
        assert set(p["scores"]) == {"hook", "cliff", "standalone", "trope_pull", "pacing"}
        assert p["posting_rationale"]


def test_promos_csv_columns_match_json(run_dir):
    with open(run_dir / "promos.csv", encoding="utf-8") as f:
        rows = list(csv.DictReader(f))
    promos = json.loads((run_dir / "promos.json").read_text(encoding="utf-8"))
    assert list(rows[0].keys()) == CSV_COLUMNS and len(rows) == len(promos)
    assert rows[0]["segments"].startswith(f"E{promos[0]['segments'][0]['episode']:02d} ")


def test_candidates_round_trip_and_review_has_excerpts(run_dir):
    cands = json.loads((run_dir / "candidates.json").read_text(encoding="utf-8"))
    assert all(Candidate(**c) for c in cands)
    review = (run_dir / "review.md").read_text(encoding="utf-8")
    assert review.startswith("# Promo shortlist:") and "```" in review and ">> [E" in review


def test_cli_mock_run(tmp_path):
    code = cli.main(["--input", str(SYNTH), "--mock", "--run-name", "cli", "--out", str(tmp_path),
                     "--aliases", str(ALIASES), "--episodes", "3"])
    assert code == 0
    (run_dir,) = tmp_path.iterdir()
    m = json.loads((run_dir / "manifest.json").read_text(encoding="utf-8"))
    assert m["episodes_run"] == [3]
