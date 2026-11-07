"""CLI: score a finished run against the gold labels and the blind precision sheet (EVAL_PLAN §2, §3).

Examples:
  python evaluate.py --run outputs/<run_id> --gold gold/gold_labels.csv
  python evaluate.py --run outputs/<run_id> --make-blind-sheet
  python evaluate.py --run outputs/<run_id> --gold gold/gold_labels.csv --ratings gold/precision_ratings.csv \
      --compare outputs/<other_run>

Writes eval_metrics.json and eval_report.md into the run folder (git-ignored). Gold labels are confidential:
the console output and the report only carry counts, gold IDs and numbers, never the label text.
"""

from __future__ import annotations

import argparse
import csv
import json
import random
import sys
from pathlib import Path

from promo_finder import metrics
from promo_finder.build import Candidate
from promo_finder.compact import format_tc
from promo_finder.judge import excerpt
from promo_finder.parse import Episode

TOP_N = 20
BLIND_N = 15


def _load(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


def promo_intervals(row: dict) -> list[metrics.Interval]:
    return [(s["ep"], s["start"], s["end"]) for s in row["segments"]]


def read_gold(path: Path) -> list[dict]:
    with open(path, encoding="utf-8", newline="") as f:
        return list(csv.DictReader(f))


def block_times(episodes: list[dict]) -> dict[str, metrics.Interval]:
    return {b["id"]: (e["ep"], b["start"], b["end"]) for e in episodes for b in e["blocks"]}


def processed_episodes(manifest: dict) -> set[int]:
    """Episodes the proposer actually returned for: in episodes_run and not in a proposer error."""
    failed = {e.get("episode") for e in manifest.get("errors", []) if e.get("stage") == "proposer"}
    return {n for n in manifest.get("episodes_run", []) if n not in failed}


def evaluate_run(run_dir: Path, gold_path: Path | None, ratings_path: Path | None = None,
                 compare_dir: Path | None = None, build_cfg: dict | None = None) -> dict:
    """All metrics for one run as a plain dict (also what eval_metrics.json holds)."""
    manifest = _load(run_dir / "manifest.json")
    ranked = _load(run_dir / "ranked.json")["ranked"]
    candidates = _load(run_dir / "candidates.json")
    episodes = _load(run_dir / "episodes.json")
    times = block_times(episodes)
    bcfg = build_cfg or {"min_duration_s": 20.0, "max_duration_s": 60.0, "hook_max_offset_s": 3.0}
    out: dict = {"run_id": manifest["run_id"], "models": manifest.get("models"),
                 "prompt_versions": manifest.get("prompt_versions")}

    ok = [bcfg["min_duration_s"] <= r["total_s"] <= bcfg["max_duration_s"] and r["hook_offset_s"] <= bcfg["hook_max_offset_s"]
          for r in ranked]
    out["validity"] = {"promos": len(ranked), "valid": sum(ok), "rate": (sum(ok) / len(ok)) if ok else None}
    done = processed_episodes(manifest)
    out["episodes"] = {"parsed": manifest.get("episodes_parsed"), "processed": len(done),
                       "not_processed": sorted(set(manifest.get("episodes_run", [])) - done)}

    if gold_path and gold_path.exists():
        gold = read_gold(gold_path)
        out["gold"] = _gold_metrics(gold, ranked, candidates, times, done)
    if ratings_path and ratings_path.exists():
        out["precision"] = _precision_metrics(run_dir, ranked, ratings_path)
    if compare_dir:
        other = _load(compare_dir / "ranked.json")["ranked"]
        a = [promo_intervals(r) for r in ranked[:10]]
        b = [promo_intervals(r) for r in other[:10]]
        out["cross_run"] = {"other_run": compare_dir.name, "top10_jaccard_iou50": metrics.jaccard_matched(a, b)}
    out["cost_time"] = {"usage": manifest.get("usage"), "cost_usd": manifest.get("cost_usd"),
                        "timings_s": manifest.get("timings_s")}
    return out


def _gold_metrics(gold: list[dict], ranked: list[dict], candidates: list[dict], times: dict, done: set[int]) -> dict:
    top = ranked[:TOP_N]
    quiet_eps = {int(g["episode"]) for g in gold if g["segments"].strip().upper().startswith("NONE")}
    rows = []
    for g in gold:
        if g["segments"].strip().upper().startswith("NONE"):
            continue
        ep = int(g["episode"])
        gi = metrics.parse_gold_segments(g["segments"])
        hook, cliff = times.get(g["hook_block"]), times.get(g["cliff_block"])
        weight = float(g["quality"] or 1)

        def best(pool: list[dict]):
            found = None
            for i, c in enumerate(pool, 1):
                iv = promo_intervals(c)
                level = metrics.match_level(iv, gi, hook, cliff)
                v = metrics.iou(iv, gi)
                if level and (found is None or v > found["iou"]):
                    found = {"level": level, "iou": round(v, 3), "pos": i}
            return found

        any_m, top_m = best(candidates), best(top)
        rows.append({"gold_id": g["gold_id"], "episode": ep, "weight": weight, "processed": ep in done,
                     "match_any": any_m, "match_top20": top_m,
                     "arc": len(gi) > 1 and len({s[0] for s in gi}) > 1})
    scored = [r for r in rows if r["processed"]]

    def rec(key: str, level_ok) -> dict:
        flags = [bool(r[key] and level_ok(r[key]["level"])) for r in scored]
        w = [r["weight"] for r in scored]
        return {"matched": sum(flags), "of": len(flags), "recall": metrics.recall(flags),
                "weighted": metrics.recall(flags, w)}

    strict = lambda lv: lv == "strict"
    lenient = lambda lv: True
    fp = [r for r in top if r["episode_key"] in quiet_eps]
    return {"gold_promos": len(rows), "in_processed_episodes": len(scored), "quiet_episodes": len(quiet_eps),
            "quiet_episodes_processed": len(quiet_eps & done),
            "recall_any_strict": rec("match_any", strict), "recall_any_lenient": rec("match_any", lenient),
            "recall_top20_strict": rec("match_top20", strict), "recall_top20_lenient": rec("match_top20", lenient),
            "quiet_false_positives_top20": len(fp), "per_gold": rows}


def _precision_metrics(run_dir: Path, ranked: list[dict], ratings_path: Path) -> dict:
    key_path = ratings_path.with_name("precision_key.csv")
    key = {r["sheet_id"]: r for r in read_gold(key_path)}
    rating = {}
    for r in read_gold(ratings_path):
        if str(r.get("rating", "")).strip() != "":
            rating[key[r["sheet_id"]]["promo_id"]] = int(r["rating"])
    by_id = {r["id"]: r for r in ranked}
    in_order = [rating[r["id"]] for r in ranked[:10] if r["id"] in rating]
    good, n = metrics.precision_at_k(in_order, 10)
    ids = [i for i in rating if i in by_id]
    rho = metrics.spearman([by_id[i]["base"] for i in ids], [rating[i] for i in ids])
    return {"rated": len(rating), "top10_rated": n, "top10_would_post": good, "judge_vs_human_spearman": rho}


# ---------- blind sheet ----------

def make_blind_sheet(run_dir: Path, out_dir: Path, seed: int = 7) -> tuple[Path, Path]:
    """Top 15 in shuffled order: timestamps and the script excerpt only. No score, rank or ID on the sheet;
    the key (sheet_id -> promo_id, rank) goes in a separate file."""
    ranked = _load(run_dir / "ranked.json")["ranked"][:BLIND_N]
    episodes = {e["ep"]: Episode.model_validate(e) for e in _load(run_dir / "episodes.json")}
    order = list(range(len(ranked)))
    random.Random(seed).shuffle(order)
    sheet, key = [], []
    for n, idx in enumerate(order, 1):
        r = ranked[idx]
        cand = Candidate.model_validate({k: v for k, v in r.items() if k in Candidate.model_fields})
        body = excerpt(cand, episodes).split("\n", 1)[1].replace(">> ", "")
        stamps = "; ".join(f"E{s['ep']:02d} {format_tc(s['start'])}-{format_tc(s['end'])}" for s in r["segments"])
        sid = f"S{n:02d}"
        sheet.append({"sheet_id": sid, "timestamps": stamps, "length_s": f"{r['total_s']:.1f}", "excerpt": body,
                      "rating": "", "note": ""})
        key.append({"sheet_id": sid, "promo_id": r["id"], "rank": r["rank"], "run_id": run_dir.name})
    out_dir.mkdir(parents=True, exist_ok=True)
    sheet_path, key_path = out_dir / "precision_ratings.csv", out_dir / "precision_key.csv"
    for path, rows in ((sheet_path, sheet), (key_path, key)):
        with open(path, "w", encoding="utf-8", newline="") as f:
            w = csv.DictWriter(f, fieldnames=list(rows[0]))
            w.writeheader()
            w.writerows(rows)
    return sheet_path, key_path


# ---------- report ----------

def _pct(x) -> str:
    return "n/a" if x is None else f"{x:.0%}"


def write_report(run_dir: Path, res: dict) -> None:
    lines = [f"# Eval: run {res['run_id']}", "",
             f"Models: {res.get('models')} · prompts: {res.get('prompt_versions')}", "",
             "## Summary", "", "| metric | value | target |", "|---|---|---|"]
    v = res["validity"]
    lines.append(f"| Validity rate | {v['valid']}/{v['promos']} ({_pct(v['rate'])}) | 100% |")
    e = res["episodes"]
    lines.append(f"| Episodes processed | {e['processed']}/{e['parsed']} (not processed: {e['not_processed'] or 'none'}) | all |")
    g = res.get("gold")
    if g:
        for name, key, target in (("Gold recall, any candidate (strict IoU≥0.5)", "recall_any_strict", "≥ 70%"),
                                  ("Gold recall, any candidate (lenient)", "recall_any_lenient", "≥ 70%"),
                                  ("Gold recall@20 (strict)", "recall_top20_strict", "≥ 50%"),
                                  ("Gold recall@20 (lenient)", "recall_top20_lenient", "≥ 50%")):
            m = g[key]
            lines.append(f"| {name} | {m['matched']}/{m['of']} ({_pct(m['recall'])}; quality-weighted {_pct(m['weighted'])}) | {target} |")
        lines.append(f"| Quiet-episode false positives in top 20 | {g['quiet_false_positives_top20']} "
                     f"(quiet episodes processed: {g['quiet_episodes_processed']}/{g['quiet_episodes']}) | lower is better |")
    p = res.get("precision")
    if p:
        lines.append(f"| Precision@10 (blind) | {p['top10_would_post']}/{p['top10_rated']} would post | ≥ 6/10 |")
        lines.append(f"| Judge vs human Spearman | {p['judge_vs_human_spearman']} | > 0.4 useful |")
    c = res.get("cross_run")
    if c:
        lines.append(f"| Top-10 Jaccard vs {c['other_run']} | {c['top10_jaccard_iou50']} | report |")
    if g:
        lines += ["", "## Gold recall per gold promo (IDs and numbers only)", "",
                  "| gold | episode | processed | any: level / IoU | top 20: level / IoU / position |", "|---|---|---|---|---|"]
        for r in g["per_gold"]:
            a, t = r["match_any"], r["match_top20"]
            lines.append(f"| {r['gold_id']} | E{r['episode']:02d} | {r['processed']} | "
                         f"{(a['level'] + ' / ' + str(a['iou'])) if a else 'missed'} | "
                         f"{(t['level'] + ' / ' + str(t['iou']) + ' / #' + str(t['pos'])) if t else 'not in top 20'} |")
    lines += ["", "## Cost and time", "", "```", json.dumps(res["cost_time"], indent=1), "```", "",
              "Targets are set in docs/EVAL_PLAN.md §2. Misses are reported as they are."]
    (run_dir / "eval_report.md").write_text("\n".join(lines) + "\n", encoding="utf-8")


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description="Evaluate a run against gold labels (counts only on the console).")
    p.add_argument("--run", required=True, type=Path)
    p.add_argument("--gold", type=Path, default=Path("gold/gold_labels.csv"))
    p.add_argument("--ratings", type=Path, help="filled gold/precision_ratings.csv (key file sits next to it)")
    p.add_argument("--compare", type=Path, help="another run folder, for top-10 agreement")
    p.add_argument("--make-blind-sheet", action="store_true")
    p.add_argument("--out-dir", type=Path, default=Path("gold"), help="where the blind sheet and key go")
    args = p.parse_args(argv)
    if args.make_blind_sheet:
        sheet, key = make_blind_sheet(args.run, args.out_dir)
        print(f"blind sheet: {sheet} ({BLIND_N} rows, shuffled, no scores or ranks); key: {key}")
        return 0
    res = evaluate_run(args.run, args.gold, args.ratings, args.compare)
    (args.run / "eval_metrics.json").write_text(json.dumps(res, indent=1), encoding="utf-8")
    write_report(args.run, res)
    v, e, g = res["validity"], res["episodes"], res.get("gold")
    print(f"run {res['run_id']}: valid {v['valid']}/{v['promos']} · episodes processed {e['processed']}/{e['parsed']}")
    if g:
        for key in ("recall_any_strict", "recall_any_lenient", "recall_top20_strict", "recall_top20_lenient"):
            print(f"  {key}: {g[key]['matched']}/{g[key]['of']}")
        print(f"  gold promos {g['gold_promos']} (in processed episodes {g['in_processed_episodes']}) · "
              f"quiet false positives in top 20: {g['quiet_false_positives_top20']}")
    print(f"wrote {args.run / 'eval_report.md'}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
