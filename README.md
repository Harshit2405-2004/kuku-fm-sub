# Kuku Promo Finder

> **Recall experiment build: improved candidate recall (precision not re-measured).** Default proposer = `proposer_v4b`. This build's app: https://kuku-fm-sub-recall.streamlit.app/ · Baseline app (proposer_v3): https://kuku-fm-sub.streamlit.app/ · Sprint results: see `decisions.md` D-045+.

**Find ready-to-cut promo clips in a microdrama script, automatically.**
Give it a show's timestamped episode scripts; it returns a **ranked shortlist of 20–60 s promos**, each with the episode, the exact start/end time of every segment, the hook, the cliffhanger, scores, risk flags and one line on why it works.

Built for the **Kuku AI Generalist take-home, Problem 1: Find the Promos**.

| | |
|---|---|
| **Live app** | https://kuku-fm-sub.streamlit.app/ (mock mode needs no API key) |
| **Recall-experiment app** | https://kuku-fm-sub-recall.streamlit.app/ (branch `recall-sprint`) |
| **Try locally in 1 minute** | `python run.py --input samples/synthetic_show --mock` |

> **For Kuku reviewers: start here**
> - **Results (run A, all 50 episodes):** 30/30 clips valid (20–60 s, hook ≤ 3 s, shot-aligned) · **blind human precision@10: 6/10** · gold recall 3/13 strict, 6/13 lenient (target missed, analysed below) · judge–human Spearman 0.25 → a human stays in the loop.
> - **Design in one line:** the LLM picks *line IDs*; code computes every timestamp, so invented times are impossible by construction.
> - **Swap in your model:** `python run.py --input <pack> --model openai/<model> --api-base <url> --api-key-env KEY`
> - **How I worked with AI:** [`decisions.md`](decisions.md) (every choice + alternatives) · [`ai_log.md`](ai_log.md) (where AI got it wrong, and which check caught it) · [`report.md`](report.md) (task-by-task build log) · [`docs/PROCESS_GUIDE.md`](docs/PROCESS_GUIDE.md) (worked example of every step).
> - The input pack is confidential: no script content is in this repo (enforced by `scripts/leak_check.py`). Raw outputs are shared via the submission form.

---

## Contents
1. [The problem](#1-the-problem)
2. [What a promo is](#2-what-a-promo-is)
3. [How it works](#3-how-it-works)
4. [Quickstart](#4-quickstart)
5. [Using the app](#5-using-the-app)
6. [Command-line usage](#6-command-line-usage)
7. [Swap the model](#7-swap-the-model)
8. [Configuration](#8-configuration)
9. [Outputs](#9-outputs)
10. [Evaluation and results](#10-evaluation-and-results)
11. [Recall experiment](#11-recall-experiment-recall-sprint-branch)
12. [Project structure](#12-project-structure)
13. [Testing](#13-testing)
14. [Key design decisions](#14-key-design-decisions)
15. [How AI was used](#15-how-ai-was-used)
16. [Limitations](#16-limitations)
17. [Scale and cost](#17-scale-and-cost)
18. [Confidentiality](#18-confidentiality)
19. [Next steps](#19-next-steps)

---

## 1. The problem
Kuku releases new microdrama shows every week, and its users are mostly acquired through paid ads, which are promo clips cut from the shows. Marketing was ~78% of Kuku's FY26 costs. Today an editor **watches every episode and picks promo moments by hand**. This tool reads the scripts instead and hands the editor a ranked, cut-ready shortlist.

## 2. What a promo is
From the brief: a 20–60 s clip that
- **opens on a hook**: something in the first 3 seconds that makes a scrolling viewer stop (a slap, a reveal, a shocking line);
- **ends on a cliffhanger**: it cuts at an unresolved moment;
- **makes sense on its own** to someone who has never seen the show.

It can be one continuous stretch (`single`), two stretches from one episode with the slow middle cut out (`jumpcut`), or moments joined across episodes (`arc`).

## 3. How it works

```
episode scripts (.txt / .zip)
   │
   ▼  1. PARSE (code)       every line/shot/action → a block with an ID (E24-B032) + start/end time
   ▼  2. PROPOSE (LLM)      per episode: "a promo starts at this hook block and ends at this cliff block" (IDs only)
   ▼  3. BUILD (code)       IDs → times · snap to camera-shot boundaries · enforce 20–60 s and hook ≤ 3 s
   │                        · stop before any line that answers the cliffhanger · jump-cut long spans · dedupe
   ▼  4. ARCS (LLM + code)  pair an early setup with a later payoff across episodes; code cuts both parts
   ▼  5. JUDGE (2nd LLM)    a different model family scores hook strength, cliff, standalone, trope pull, pacing (1–5)
   ▼  6. RANK (code)        weighted score + early-episode bonus + penalties · diversity caps · weak cliffs kept out of top 10
   ▼  7. OUTPUT             promos.csv · promos.json · review.md (editor sheet) · manifest.json · raw model replies
```

**Who does what**

| | Responsible for |
|---|---|
| **AI (LLM)** | Judgement: which moment is a hook or a cliffhanger; scoring how strong it is; the one-line "why". |
| **Code** | Everything checkable: parsing, IDs → timestamps, shot snapping, the 20–60 s and 3 s rules, jump-cuts, dedupe, ranking, evaluation, caching. |
| **Human** | Final pick and trim, brand-safety calls (violent scenes are flagged, never auto-removed). |

**Why the LLM never writes timestamps:** models misread and invent numbers. Here they can only point at block IDs; a candidate with an ID that doesn't exist is sent back for one repair, then dropped. Every time in the output is computed by code from the script.

## 4. Quickstart

Requires **Python 3.11+** (developed on 3.13).

```bash
git clone https://github.com/Harshit2405-2004/kuku-fm-sub.git
cd kuku-fm-sub
python -m venv .venv
# Windows:      .venv\Scripts\Activate.ps1
# macOS/Linux:  source .venv/bin/activate
pip install -r requirements.txt

# 1) No API key needed: canned model replies on a fictional 3-episode show
python run.py --input samples/synthetic_show --mock --run-name demo

# 2) Real models: copy .env.example to .env and add a key (e.g. GROQ_API_KEY=..., GEMINI_API_KEY=...)
python run.py --input path/to/your/pack --run-name myrun
```

Results land in `outputs/<timestamp>-<run-name>/`. Open `review.md` first.

**Input format:** a folder (or `.zip`) of episode `.txt` files, each with `EPISODE NUMBER / EPISODE LOGLINE / CONTINUITY NOTES` headers, `SCENE` blocks, and `**CAMERA:**`, `**ACTION:**`, `**SOUND FX:**` or `**SPEAKER (emotion):**` blocks each followed by `Start: (MM:SS.ss) | End: (MM:SS.ss)`. See `samples/synthetic_show/` for a complete example. The parser is tolerant: header casing, `HH:MM:SS` times, CRLF line endings and missing optional sections become warnings, never crashes, and every non-empty line is accounted for.

## 5. Using the app

Live: **https://kuku-fm-sub.streamlit.app/** · Locally: `streamlit run app.py`

1. Upload a `.zip` or several episode `.txt` files, or click **Try the fictional sample**.
2. Keep **Mock mode** on to run without a key, or switch it off and enter a model name, optional API base and your API key (used in memory for that run only; never stored, logged or cached).
3. Optionally limit **Episodes to run**.
4. Click **Run** → see the ranked table with expandable script excerpts → download `promos.csv` and `review.md`.

Uploads and outputs live in a temporary folder per session; nothing is saved to the repo. One key is used for every stage; to use a different provider per stage, use `run.py`.

## 6. Command-line usage

```bash
python run.py --input <pack> [options]
```

| Option | Meaning |
|---|---|
| `--input` | Folder of episode `.txt` files or a `.zip` (required) |
| `--config` | Config file (default `config.yaml`) |
| `--run-name` | Name suffix for the output folder |
| `--out` | Where run folders go (default `outputs`) |
| `--episodes 1,3,8` | Run only these episodes |
| `--mock` | Canned replies, no API calls |
| `--no-cache` | Ignore the on-disk LLM cache |
| `--model` | One model for every stage |
| `--proposer-model` / `--arc-model` / `--judge-model` | Model for one stage |
| `--api-base` / `--api-key-env` | OpenAI-compatible endpoint URL / name of the env var holding its key |
| `--run-dir` | Continue in an existing run folder (finished episodes come from the cache) |
| `--episode-proposer "17-18,20=MODEL"` | Different proposer model for some episodes (e.g. when a quota runs out); add `\|KEY_ENV` for another provider |
| `--aliases` | Speaker alias file (optional; maps e.g. a descriptive label to a character name) |

**Evaluate a run**

```bash
python evaluate.py --run outputs/<run_id> --gold gold/gold_labels.csv                      # recall vs gold set
python evaluate.py --run outputs/<run_id> --make-blind-sheet                               # shuffled sheet for human rating
python evaluate.py --run outputs/<run_id> --gold gold/gold_labels.csv \
    --ratings gold/precision_ratings.csv --compare outputs/<other_run>                     # precision@10, Spearman, A vs B
```

| Option | Meaning |
|---|---|
| `--run` | The run folder to score (required) |
| `--gold` | Gold labels CSV (confidential, git-ignored) |
| `--ratings` | Filled `precision_ratings.csv`; its key file `precision_key.csv` sits next to it |
| `--compare` | Another run folder, for top-10 agreement |
| `--make-blind-sheet` | Write the shuffled top-15 sheet and its key |
| `--out-dir` | Where the blind sheet and key go |

## 7. Swap the model

Every model call goes through **LiteLLM**, so any supported provider or any **OpenAI-compatible endpoint** works, with no code change:

```bash
# everything on one model
python run.py --input <pack> --model gemini/<model-name> --api-key-env GEMINI_API_KEY

# upgrade only the judge
python run.py --input <pack> --judge-model openai/<model-name> --api-key-env OPENAI_API_KEY

# your own endpoint (e.g. Kuku's API)
python run.py --input <pack> --model openai/<their-model> \
    --api-base https://<their-host>/v1 --api-key-env KUKU_API_KEY
```

`--api-base` / `--api-key-env` apply to the stages whose model you overrode (all stages if none). The manifest records which model served every episode.

## 8. Configuration

`config.yaml` holds everything tunable. It has no secrets (keys come from environment variables named in the config):
- **`models`**: model, endpoint, key env var, temperature (0), max tokens and reasoning effort **per stage** (proposer, arc, judge).
- **`rank`**: score weights (hook 0.35, cliff 0.30, standalone 0.20, trope 0.10, pacing 0.05), early-episode and length bonuses, penalties, diversity caps, `min_cliff_top10`.
- **`build`** thresholds: 20–60 s, 3 s hook window, jump-cut and extension limits.
- **`retries` / `concurrency`**: honours provider `retry-after` hints; gives up at once when a provider asks for a wait longer than `max_wait_s` (a daily quota).

Prompts live in `promo_finder/prompts/` (`proposer.md`, `judge.md`, `arc.md`), each with a version header that goes into the cache key and the manifest.

## 9. Outputs

Each run writes `outputs/<timestamp>-<run-name>/`:

| File | Contents |
|---|---|
| `review.md` | Editor-facing shortlist: posting order, segment timecodes, hook → cliff, why, flags, script excerpt |
| `promos.csv` / `promos.json` | Ranked promos: type, segments (episode + start/end), length, hook, cliff, why, scores, final score, flags |
| `ranked.json` / `scored.json` | Score breakdown (base, bonuses, penalties) and the judge's raw scores and reasons |
| `candidates.json` / `rejected.json` | Every built clip, and every rejected one with its reason |
| `proposals_raw/`, `judge_raw/`, `arcs_raw.json` | Unedited model replies |
| `manifest.json` | Models and prompt versions, model per episode, counts, tokens and time per stage, errors |
| `eval_report.md` / `eval_metrics.json` | Written by `evaluate.py` |

Timecodes are `MM:SS.s` from the start of each episode. Every LLM call is cached on disk (keyed by model, prompt version, endpoint, settings and input), so re-running is free and reproducible.

## 10. Evaluation and results

Main run `20261107-2103-runA` on all 50 episodes of the provided show:

| Check | Result | Target |
|---|---|---|
| Validity: 20–60 s, hook ≤ 3 s, shot-aligned, nothing after the cliff | **30/30** | 100% |
| **Blind human precision@10** (top 15 rated shuffled, without scores) | **6/10** "would post" | ≥ 6/10 |
| Gold recall, any candidate: strict (IoU ≥ 0.5) / lenient | 3/13 / 6/13 | ≥ 70% |
| Gold recall within the final top 20: strict / lenient | 0/13 / 3/13 | ≥ 50% |
| Judge–human agreement (Spearman) | 0.25 | > 0.4 |

**Gold set:** 13 promos over 10 episodes (3 held out), drafted by Claude in a separate session (not a pipeline model) from a full read of the episodes, then reviewed and approved by me. Recall therefore measures agreement with an LLM-drafted, human-approved list; blind precision@10 is the independent human signal.

**Where it fails:** the judge's ranking only loosely matches a human's (the #1 clip was rated "maybe"); near-duplicate clips from one scene can both reach the top 15; forcing clips to open on the strongest moment can leave a weaker ending (now gated out of the top 10); and recall is limited mainly by **candidate generation**, see §11.

## 11. Recall experiment (`recall-sprint` branch)

Tuned on 7 gold episodes, checked on 3 held-out ones:

| Tried | Result | Adopted? |
|---|---|---|
| Re-judge all candidates with a second judge | Fixed unscored clips but agreed less with human ratings (0.25 → 0.18), ~5× judge tokens | No |
| Prompt v4: "up to 4 candidates" | No change: the model still returned about one clip per episode | No |
| **Prompt v4b: "exactly 3 per episode with conflict"** | Clips/episode 0.9 → 1.3 · held-out lenient recall 3/5 → 4/5 · dev strict 0/8 → 1/8 · +15% prompt, +61% completion tokens · 28% of proposals near-duplicates (removed by dedupe) | **As an option** |

`main` keeps proposer v3 (its precision is measured). The `recall-sprint` branch makes the proposer prompt selectable (config `prompts.proposer` + app dropdown) with v4b as its default, deployed separately at https://kuku-fm-sub-recall.streamlit.app/. Precision for v4b was not re-measured, and the samples are small (13 gold promos), so treat the gain as indicative.

## 12. Project structure

```
├── run.py                     CLI entry point
├── evaluate.py                evaluation CLI (recall, blind sheet, precision, comparison)
├── app.py                     Streamlit app
├── config.yaml                models per stage, weights, thresholds (no secrets)
├── requirements.txt · .env.example
├── promo_finder/
│   ├── parse.py               tolerant script parser → episodes and blocks
│   ├── aliases.py             speaker-name aliases (incl. per-episode overrides)
│   ├── compact.py             the one-line-per-block view the LLM reads
│   ├── llm.py, cache.py       single LiteLLM call path: retries, JSON validation, usage, disk cache
│   ├── config.py              config loading + CLI overrides
│   ├── propose.py             proposer stage (IDs only)
│   ├── build.py               IDs → validated cuts (snapping, durations, jump-cuts, dedupe)
│   ├── arcs.py                cross-episode promos
│   ├── judge.py               rubric scoring by a second model
│   ├── rank.py                scoring formula + diversity caps
│   ├── report.py              CSV / JSON / review.md / manifest
│   ├── pipeline.py            runs all stages, keeps going on per-episode failures
│   ├── metrics.py             IoU, recall, precision@k, Spearman, Jaccard
│   ├── mock.py                canned replies for --mock
│   └── prompts/               proposer.md, judge.md, arc.md (versioned)
├── samples/synthetic_show/    fictional 3-episode show (tests, demo, prompt examples)
├── scripts/                   leak_check.py, gold worksheet tools, analysis helpers
├── tests/                     pytest suite
├── docs/                      PRD, TECH_SPEC, EVAL_PLAN, PLAN, PROCESS_GUIDE, RESEARCH, BRIEF_COMPLIANCE
├── decisions.md · ai_log.md · report.md     decision log, AI-mistakes log, build log
└── CLAUDE.md, .claude/        rules, review agents and skills used with Claude Code
```

On the `recall-sprint` branch there is also `promo_finder/prompts/proposer_v4.md` and `proposer_v4b.md`, and `scripts/recall_pool.py`, `propose_only.py` and `rejudge.py` for the sprint analysis.

## 13. Testing

```bash
pytest -q
```

270 tests on `main` (272 on `recall-sprint`), all offline (fake model calls), covering the parser (including malformed and variant formats), cut building with exact worked examples and boundaries (20.0 s, 60.0 s, 3.0 s), the LLM layer (retries, rate-limit hints, JSON repair, cache keys), ranking, metrics, the evaluation CLI, the app and the confidentiality check. `docs/PROCESS_GUIDE.md` walks through the same numbers by hand.

## 14. Key design decisions
Full list with alternatives and consequences in [`decisions.md`](decisions.md). The main ones:
- **IDs, not timestamps, from the model**: correctness by construction.
- **One proposer call per episode + an arc pass**: robust to rate limits and failures; cost scales linearly.
- **Cuts snap to camera shots; hook ≤ 3 s; cut before the answer**: editor-ready clips.
- **Judge from a different model family**: reduces self-preference bias; measured against human ratings.
- **Shortlist for a human, not auto-posting**: taste varies and Kuku A/B tests.
- **Temperature 0, versioned prompts, disk cache**: reruns are free and reproducible.
- **Simple, readable code**: plain functions, small modules.

## 15. How AI was used
- **Claude Code** built and tested the code against written specs (`docs/`), one task at a time, with test-first development, a fresh-context reviewer agent at each phase, and checkpoints where I made the decisions. Every task is in [`report.md`](report.md).
- **Claude (chat)** for research, planning and reviewing outputs against the scripts.
- **Runtime models:** gpt-oss (proposer), Qwen (judge), Gemini (comparison and experiments).
- **Where AI got it wrong**, logged in [`ai_log.md`](ai_log.md), each with the check that caught it: e.g. a default model chosen without checking its daily quota; a clip that passed every automatic check but buried its strongest moment 26 s in; an AI-drafted name map that merged two characters.

## 16. Limitations
- Scripts are assumed to match the final video timing; drift can't be detected from text.
- Free-tier daily token caps meant run A used three proposer models across episodes and the judge scored 30 of 56 candidates.
- The gold set is small and LLM-drafted (human-approved); precision@10 rests on one rater and 15 clips.
- Judge–human agreement is low (0.25), so the ranking needs a human pass.
- Near-duplicate suppression across clips from the same scene is incomplete; no "slow middle → jump-cut" rule yet.

## 17. Scale and cost
About **0.48M tokens per 50-episode show** (measured, with judging extrapolated to all candidates). Episodes are independent, so they could run in parallel (the pipeline runs them one at a time today); wall time so far was set by free-tier rate limits, not compute. At an *assumed* $1 / $4 per million input/output tokens that is ≈ $0.76 per show, ≈ $114/month at 150 shows and ≈ $762 at 1,000. Production needs Kuku's API or a paid tier; switching is a config change.

## 18. Confidentiality
The input pack is confidential and never committed. `input/`, `outputs/`, `private/`, `config/aliases.yaml`, `gold/*.csv`, `.cache/` and `.env` are git-ignored; tests and demos use a fictional show; `scripts/leak_check.py --pre-push` scans the working tree, staged files, all history and commit messages for show names, keywords and sample dialogue before every push.

## 19. Next steps
- Log the editor's accept/reject on every shortlisted clip and each posted promo's CTR / cost per install; learn the ranker weights from that.
- Use past top-performing promos as judge examples; later, a small fine-tuned reranker distilled from the large model to cut cost.
- Near-duplicate suppression, a slow-middle jump-cut rule, and alignment to the rendered video.
- A continuity checker for AI-written series, where names and places can drift between episodes.
