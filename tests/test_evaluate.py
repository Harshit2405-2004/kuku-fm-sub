"""evaluate.py on the synthetic show (mock run): recall, quiet false positives, blind sheet, precision, report."""
import csv
import json
from pathlib import Path

import pytest

from evaluate import evaluate_run, main, make_blind_sheet, write_report
from promo_finder.compact import format_tc
from promo_finder.config import load_config
from promo_finder.pipeline import run_pipeline

ROOT = Path(__file__).resolve().parent.parent


@pytest.fixture(scope="module")
def run_dir(tmp_path_factory) -> Path:
    cfg = load_config(ROOT / "config.yaml")
    cfg["mock"] = True
    return run_pipeline(ROOT / "samples/synthetic_show", cfg, "evaltest", out_root=tmp_path_factory.mktemp("out"),
                        aliases_path=ROOT / "config/aliases.example.yaml")


def write_gold(path: Path, run_dir: Path, quiet_ep: int | None = None) -> None:
    top = json.loads((run_dir / "ranked.json").read_text(encoding="utf-8"))["ranked"][0]
    seg = ";".join(f"E{s['ep']:02d} {format_tc(s['start'])}-{format_tc(s['end'])}" for s in top["segments"])
    rows = [["G01", top["episode_key"], seg, top["hook_block"], top["cliff_block"], "3", "synthetic"]]
    if quiet_ep is not None:
        rows.append(["G02", quiet_ep, "NONE", "", "", "0", "quiet"])
    with open(path, "w", encoding="utf-8", newline="") as f:
        w = csv.writer(f)
        w.writerow(["gold_id", "episode", "segments", "hook_block", "cliff_block", "quality", "notes"])
        w.writerows(rows)


def test_gold_recall_and_quiet_false_positive(run_dir, tmp_path):
    top = json.loads((run_dir / "ranked.json").read_text(encoding="utf-8"))["ranked"][0]
    gold = tmp_path / "gold.csv"
    write_gold(gold, run_dir, quiet_ep=top["episode_key"])
    res = evaluate_run(run_dir, gold)
    g = res["gold"]
    assert g["recall_any_strict"] == {"matched": 1, "of": 1, "recall": 1.0, "weighted": 1.0}
    assert g["recall_top20_strict"]["matched"] == 1
    assert g["quiet_false_positives_top20"] >= 1          # the top promo sits in the episode labelled quiet
    assert res["validity"]["rate"] == 1.0


def test_unprocessed_episode_is_not_counted_against_recall(run_dir, tmp_path):
    gold = tmp_path / "gold.csv"
    write_gold(gold, run_dir)
    manifest = json.loads((run_dir / "manifest.json").read_text(encoding="utf-8"))
    ep = json.loads((run_dir / "ranked.json").read_text(encoding="utf-8"))["ranked"][0]["episode_key"]
    manifest["errors"].append({"stage": "proposer", "episode": ep, "error": "quota"})
    copy = tmp_path / "run"
    copy.mkdir()
    for f in ("ranked.json", "candidates.json", "episodes.json"):
        (copy / f).write_text((run_dir / f).read_text(encoding="utf-8"), encoding="utf-8")
    (copy / "manifest.json").write_text(json.dumps(manifest), encoding="utf-8")
    g = evaluate_run(copy, gold)["gold"]
    assert g["in_processed_episodes"] == 0 and g["recall_any_strict"]["recall"] is None


def test_blind_sheet_has_no_scores_or_ranks_and_key_maps_back(run_dir, tmp_path):
    sheet, key = make_blind_sheet(run_dir, tmp_path)
    rows = list(csv.DictReader(open(sheet, encoding="utf-8")))
    assert 1 <= len(rows) <= 15
    assert set(rows[0]) == {"sheet_id", "timestamps", "length_s", "excerpt", "rating", "note"}
    text = sheet.read_text(encoding="utf-8")
    assert "final_score" not in text and "judge" not in text.lower() and ">>" not in text
    keys = list(csv.DictReader(open(key, encoding="utf-8")))
    assert sorted(k["promo_id"] for k in keys) == sorted(
        r["id"] for r in json.loads((run_dir / "ranked.json").read_text(encoding="utf-8"))["ranked"][:15])
    again, _ = make_blind_sheet(run_dir, tmp_path / "again")
    assert again.read_text(encoding="utf-8") == text       # fixed seed: same shuffle


def test_precision_and_report_from_filled_ratings(run_dir, tmp_path):
    sheet, key = make_blind_sheet(run_dir, tmp_path)
    rows = list(csv.DictReader(open(sheet, encoding="utf-8")))
    for i, r in enumerate(rows):
        r["rating"] = "2" if i % 2 == 0 else "0"
    with open(sheet, "w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0]))
        w.writeheader()
        w.writerows(rows)
    res = evaluate_run(run_dir, None, sheet)
    assert res["precision"]["rated"] == len(rows)
    write_report(run_dir, res)
    assert "Precision@10" in (run_dir / "eval_report.md").read_text(encoding="utf-8")


def test_cli_prints_counts_only(run_dir, tmp_path, capsys):
    gold = tmp_path / "gold.csv"
    write_gold(gold, run_dir)
    assert main(["--run", str(run_dir), "--gold", str(gold)]) == 0
    out = capsys.readouterr().out
    assert "recall_any_strict: 1/1" in out and "synthetic" not in out and "E01-B" not in out
