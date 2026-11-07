# Evaluation plan

The brief: "**Quality checking.** How you know the output is good, backed by real runs and honest failures." and "Check quality. Where does your tool pick badly?"

We can't measure the true goal (ad performance) offline, so we use **five proxies**. Each one catches a different kind of failure.

| # | Check | Catches | Who |
|---|---|---|---|
| 1 | Structural validity | Broken timestamps, wrong durations, hook not in first 3 s | Code, 100% of outputs |
| 2 | Gold-set recall | Missing the moments a human editor would obviously pick | Harshit labels; code scores |
| 3 | Blind precision@10 | Top-ranked promos that are actually bad | Harshit rates blind; code scores |
| 4 | Judge vs. human agreement | The LLM judge's taste differing from a human's | Code |
| 5 | Model agreement and stability | Results being noise (same model run twice; two model families) | Code |
| + | Failure gallery | *Why* it fails, with concrete cases | Harshit + Claude |

---

## 1. Gold set (Harshit, about 45–60 min, **before seeing any model output**)

**Why first:** if you label after seeing the tool's picks, you'll unconsciously agree with them (anchoring), and the recall number becomes meaningless.

**Calibrate first (15 min):** watch about 10 real microdrama ads (TikTok, or the Meta Ad Library: search "ReelShort" or "DramaBox"). Write in `gold/ad_observations.md`:
- 3 hook patterns you saw, e.g. "opens on a slap mid-air"
- how they end, e.g. "cut on a shocked face plus 'what happens next?'"
- typical length

This file is public-safe (it's about public ads), it feeds the proposer prompt, and you can cite it in the doc.

**Choose episodes:** about 10 episodes. Roughly 7 that look high-drama from the loglines and 3 that look quiet. The quiet ones test whether the tool correctly finds little or nothing. Candidate list in `private/INPUT_PACK_NOTES.md`. Pick a spread across the show (early, middle, late).

**Label:** read each chosen episode's script fully. For each promo you'd genuinely post, write a row in `gold/gold_labels.csv`:
```
gold_id,episode,segments,hook_block,cliff_block,quality,notes
G01,1,"E01 00:11.0-00:41.5",E01-B0xx,E01-B0yy,3,"<why, in your words>"
G02,3,"E03 01:02.0-01:40.0",...,...,2,"..."
G03,8,NONE,,,0,"quiet episode, nothing promo-worthy"
```
- `segments`: `E<ep> MM:SS.s-MM:SS.s`, separated by `;` for multi-segment.
- `quality`: 3 = would post first, 2 = solid, 1 = usable.
- Include 1–2 cross-episode arcs if you see them.
- Aim for **12–20 gold promos**.
- A parsed `episodes.json` with block IDs is available after T1 (CP-1). Use a printed compact view per episode (`python -m promo_finder.compact --ep 3`) to label against block IDs.

## 2. Metrics (implemented in `promo_finder/metrics.py` and `evaluate.py`)

**Temporal IoU (multi-segment aware):** convert each promo into a set of `(episode, start, end)` intervals.
`IoU = total overlap seconds / total union seconds`, summed over all intervals and only counting overlaps within the same episode.

**Match rule:** a tool promo *matches* a gold promo if IoU ≥ 0.5. Also report a lenient match: IoU ≥ 0.3, **or** both the hook block and cliff block fall inside the tool promo.

| Metric | Definition | Target (set in advance) |
|---|---|---|
| Validity rate | % of output promos passing all `build.py` checks | 100% (by construction) |
| Gold recall (any) | % of gold promos matched by *any* candidate | ≥ 70% |
| Gold recall@20 | % matched within the final top 20 | ≥ 50% |
| Weighted recall | Recall weighted by gold `quality` | report |
| Quiet-episode false positives | Candidates proposed on episodes labelled NONE that rank in the top 20 | report (lower is better) |
| Precision@10 | (Section 3) | ≥ 6/10 "would post" |
| Judge–human agreement | Spearman ρ between judge score and Harshit's 1–3 rating on the rated set | report; ρ > 0.4 means the judge is useful |
| Self-stability | Jaccard of top-10 (IoU-matched) between two identical runs with the cache off | report |
| Cross-model agreement | Jaccard of top-10 between model A and model B | report |
| Cost and time | Tokens, calls, wall time per stage; cost/show at free and paid reference prices | report |

**Report targets honestly, including misses.** A missed target plus an explanation is better than a hidden one.

## 3. Blind precision@10 (Harshit, about 20 min, after the full run)
- `evaluate.py --make-blind-sheet` writes `gold/precision_ratings.csv`. It lists the top 15 promos **in shuffled order, without scores or ranks**, showing only timestamps and excerpts.
- Harshit rates each one: `2` = would post, `1` = maybe, `0` = no, plus a short note.
- `evaluate.py` then un-shuffles the sheet and computes precision@10 (count of 2s in the true top 10) and the judge–human Spearman correlation.

## 4. Failure gallery (at least 3–5 cases)
For each case: promo ID, what's wrong, which stage failed, root cause, and the fix you'd make. Use this taxonomy:

| Code | Failure | Likely stage |
|---|---|---|
| F1 | Needs context: a stranger can't follow who is who | proposer / judge |
| F2 | Cliff resolved inside the clip | builder (end snap) / proposer |
| F3 | Visual hook missed (the script only implies it) | proposer |
| F4 | Overrates a long speech that plays slow | judge |
| F5 | Near-duplicate promos from the same scene | builder dedupe / diversity |
| F6 | Bad cut: mid-shot or mid-line | builder |
| F7 | Arc promo that doesn't cohere across the cut | arcs / judge |
| F8 | Brand-safety risk (graphic violence) ranked high | ranker (flag only) |
| F9 | Script ≠ final video: timestamp drift (can't detect offline) | n/a; the system's limit |
| F10 | Gold promo missed entirely | proposer recall |

Also check the opposite direction: at least one case where **the tool found something good that Harshit missed in gold labelling**. It's an honest data point and makes a good interview story.

## 5. Two-model comparison
- Run A: default free config (e.g. a Gemini Flash proposer with a Groq judge).
- Run B: swap the proposer to another family, or swap the judge. **Change one thing at a time** so the difference is attributable.
- Report the metrics side by side. The point isn't to crown a winner. It shows (1) that swapping works, which the brief asks for, and (2) how much results depend on the model, which argues for the human in the loop and for testing Kuku's stronger API.

## 6. `eval_report.md` template (generated, then Harshit adds commentary)
```
# Eval — run <id>  (models: proposer=…, judge=…; prompts: proposer_v?, judge_v?)
## Summary table (metric | value | target | met?)
## Validity
## Gold recall (list each gold promo: matched? best IoU, tool rank)
## Precision@10 (blind ratings)
## Judge vs human
## Stability / model agreement
## Cost & time (per stage; per show; extrapolated to 150 and 1,000 shows/month)
## Failure gallery (filled in by hand)
## What I'd change next
```

## 7. Honesty rules
- Numbers come only from saved runs. Cite the run ID.
- Never tune prompts *on the gold labels* and then report recall on the same labels without saying so. If you iterate the prompt using gold episodes, hold out 3 gold episodes as a test set **chosen before iterating**, and report results on those separately.
