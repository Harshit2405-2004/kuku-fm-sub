# Submission package

## 1. Form fields
| Field | Value |
|---|---|
| Email / Name / Roll No / College email | yours |
| Solution Document Drive Link | PDF of 2 pages or fewer. Drive sharing: *Anyone with the link → Viewer* |
| Prototype link | Streamlit app URL. The GitHub link goes in the doc and the README. |
| Raw Outputs | Drive folder: `run-A/`, `run-B/` (unedited `outputs/<run_id>/`), `eval/` |
| Walkthrough video | Loom or unlisted YouTube. The form marks it with `*`, so treat it as required. |

Before submitting, open **every** link in an incognito window.

## 2. Solution doc (max 2 pages)
The brief wants to know: which problem and why · assumptions · how it works · how it scales to every show · how you know it's good, including where it fails. Communication should be "clear, specific and short".

**Header line:** Name · Roll No · Branch · **Problem 1: Find the Promos** · Links (app, repo, raw outputs, video)

| § | Section | ~Words | Content |
|---|---|---|---|
| 1 | Why this problem | 60 | Marketing is ₹1,105 Cr (78% of FY26 costs); shows ship weekly; an editor watches every episode. Promos are the ads. |
| 2 | Assumptions | 90 | 5–6 bullets from PRD §6 |
| 3 | How it works | 200 | Diagram (one line of boxes); **AI / code / human split table**; "the LLM never writes timestamps"; promo types (single / jump-cut / arc) |
| 4 | Results | 150 | Top 5 promos (episode, segment timecodes, hook → cliff, why), plus the posting-order logic in 2 lines |
| 5 | How I know it's good | 180 | Metrics table (validity, gold recall, precision@10, judge–human ρ, model agreement) with **real numbers and run IDs** |
| 6 | Where it fails | 120 | 3 failure cases, each with cause and fix |
| 7 | Scale and cost | 100 | Measured tokens, time and calls per show → cost at free and paid prices → per month at 150 and 1,000 shows. How Kuku's stronger API plugs in (one flag, per stage). |
| 8 | AI tools used | 80 | Table: tool → role. **One place AI got it wrong**, with how it was caught. |
| 9 | Next | 60 | Feedback loop from ad CTR/CPI; video alignment; adoption metric |

About 1,050 words plus 2 small tables fits on 2 pages at 10–10.5 pt. Cut adjectives, not numbers.

**Draft workflow:** Claude Code writes `private/solution_doc_draft.md` from real results only. **You rewrite it yourself.** The brief says "Can AI write my solution doc? It can help, but the decisions should be yours. We'll talk through them in your interview." Then export to PDF from Google Docs, or use the `pdf` document skill.

## 3. Walkthrough video script (≤ 3:00, your voice, screen recording)
| Time | Show | Say |
|---|---|---|
| 0:00–0:20 | Brief / one slide | "Editors hand-pick promos from every episode; marketing is ~78% of Kuku's costs. I built a tool that reads the scripts and returns ranked, cut-ready promos." |
| 0:20–0:50 | Diagram | "LLM proposes moments as line IDs; code turns them into timestamps, snaps to shots, enforces 20–60 s and hook-in-3 s; a second model judges; code ranks." |
| 0:50–1:40 | **Live run** in the app (upload the pack, or use a cached run) | Show the table, expand the #1 promo, read the hook and cliff, show the timecodes |
| 1:40–2:20 | eval_report.md | "Found X of Y of my hand-picked promos; 7/10 of the top 10 I'd post; here's where it fails…" (one failure) |
| 2:20–2:45 | config.yaml / CLI | "Swapping in your model is one flag." Show `--model … --api-base …` |
| 2:45–3:00 | — | Cost per show, and the one thing you'd do next |

## 4. Final pre-submit checklist
- [ ] PDF ≤ 2 pages; the header has branch and problem; all numbers match a run ID
- [ ] App opens in incognito; synthetic sample runs; real upload runs (or a clear note about quota)
- [ ] Repo opens; README quickstart works from a fresh clone (`--mock`)
- [ ] `scripts/leak_check.py` passes; no script text, names or outputs in the repo
- [ ] Raw outputs folder is unedited and contains both runs
- [ ] Video ≤ 3:00, in your voice, shows a run
- [ ] Submitted from your own account, before the deadline; confirmation screenshotted
