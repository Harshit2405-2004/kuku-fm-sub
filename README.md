# Kuku Promo Finder

Reads a microdrama screenplay pack (timestamped episode scripts) and outputs a **ranked shortlist of 20–60 s promo clips**. Each clip has its episode, the start and end time of every segment, the hook, the cliffhanger, scores from a judge model, and one line on why it works. Built for the Kuku AI Generalist take-home, Problem 1.

A promo here follows the brief: a 20–60 s clip that opens on a hook in the first 3 seconds, ends on an unresolved cliffhanger, and makes sense to someone who has never seen the show. It can be one stretch, a jump-cut of two stretches from one episode, or an arc joining two episodes.

## How it works

```
episodes → parse (block IDs + times) → propose (LLM picks block IDs) → build (code cuts, snaps, checks)
         → arcs (LLM pairs clips across episodes) → judge (second model scores 1–5) → rank (code) → outputs
```

- **The model never writes timestamps.** It returns block IDs such as `E01-B037`; code turns them into times and checks length (20–60 s) and hook offset (≤ 3 s).
- Every LLM call is cached on disk (keyed by model, prompt version, endpoint, temperature and input), so a rerun is free.
- Proposer, arc and judge models are set per stage and come from `config.yaml` or CLI flags.

## Quickstart

```bash
# 1. install (Python 3.11+)
python -m venv .venv && .venv/Scripts/activate        # Linux/macOS: source .venv/bin/activate
pip install -r requirements.txt

# 2. try it with no API key: canned model replies on a fictional 3-episode show
python run.py --input samples/synthetic_show --mock --run-name demo

# 3. run it on a real pack: put your key in .env (e.g. GROQ_API_KEY=...) and point at your episodes
python run.py --input input/<your-pack> --config config.yaml --run-name myrun
```

Results land in `outputs/<timestamp>-<run-name>/`. Tests: `pytest -q`.

## Swap the model

Models live in `config.yaml` (`models.proposer`, `models.arc`, `models.judge`). Override from the command line, no code change:

```bash
# every stage on one model (any LiteLLM name)
python run.py --input input/<pack> --model gemini/<model-name> --api-key-env GEMINI_API_KEY

# only the judge on a stronger model
python run.py --input input/<pack> --judge-model openai/<model-name> --api-key-env OPENAI_API_KEY

# your own OpenAI-compatible endpoint (e.g. Kuku's API)
python run.py --input input/<pack> --model openai/<their-model> \
    --api-base https://<their-host>/v1 --api-key-env KUKU_API_KEY

# a different proposer for some episodes only (e.g. when one model's daily quota runs out)
python run.py --input input/<pack> --run-dir outputs/<existing-run> \
    --episode-proposer "17-18,20-23=groq/openai/gpt-oss-20b"

# continue in a finished or partial run folder: episodes already done come from the cache
python run.py --input input/<pack> --run-dir outputs/<existing-run>
```

`--api-base` and `--api-key-env` go with the stages whose model you overrode (all stages if you gave none). `--episodes 1,3,8` runs a subset. The manifest records the model used for every episode (`proposer_model_by_episode`).

## What you get

Each run folder holds:

| File | What it is |
|---|---|
| `review.md` | Start here: the posting-order table, then each promo with its cut list, scores, a posting note and the exact script excerpt |
| `promos.csv`, `promos.json` | The ranked shortlist: rank, ID, type (`single`, `jumpcut`, `arc`), duration, every segment with start/end, hook, cliffhanger, why, five judge scores, flags |
| `ranked.json`, `scored.json` | Full detail: score breakdown (base, bonuses, penalties), diversity skips, unscored promos |
| `candidates.json`, `rejected.json` | Every clip the builder made, and every rejection with its reason |
| `proposals_raw/`, `judge_raw/` | Unedited model replies, for audit |
| `manifest.json` | Models and prompt versions, per-episode proposer model, counts, tokens and calls per stage, cost (null if a price is unknown), timings, errors, config |
| `run.log` | What happened, in order |

**Ranking:** base = weighted judge scores (hook 0.35, cliff 0.30, stand-alone 0.20, trope pull 0.10, pacing 0.05), plus small bonuses (early episodes, 30–45 s, arcs) and penalties (cuts mid-shot, needs context). A promo whose cliff scores below 3 cannot be in the top 10; no more than 2 per episode in the top 20 and 1 per scene in the top 10. On-screen violence is flagged (`graphic_violence`), not excluded.

**Evaluation:** `python evaluate.py --run outputs/<run> --gold gold/gold_labels.csv` computes validity, gold recall (strict IoU ≥ 0.5, lenient) and quiet-episode false positives; `--make-blind-sheet` writes a shuffled sheet for human ratings and `--ratings` scores precision@10 and judge-vs-human agreement. See `docs/EVAL_PLAN.md`.

## Limitations

- **Free-tier coverage.** The runs here used free API tiers with daily token caps (about 200k tokens per model per day, roughly 7k tokens per episode), so a full 50-episode pass needs more than one day or a paid key. Episodes that fail on a daily quota are recorded as not processed in the manifest; they are never retried silently. Check `manifest.json` for how many episodes each run actually covered.
- **Two proposer sizes in one run.** Run A mixes `gpt-oss-120b` and `gpt-oss-20b` across different episodes after a quota switch. The per-episode model is in the manifest. Compare their scores with care: different episodes, so it is indicative, not controlled.
- **Script ≠ final video.** Times come from the script's timestamps; if the edited video drifts from them, clips shift. This can't be detected offline.
- **The judge is an LLM.** Scores are a proxy; they have been checked against human ratings only on the small gold and blind sets (see the eval reports). Groq's qwen judge is not fully deterministic even at temperature 0; the cache makes reruns reproducible.
- **Known unfixed items:** duplicate arc picks are not de-duplicated; a crash outside the per-episode and per-batch handlers leaves no manifest; the judge excerpt can drop a dialogue line already playing at a single clip's start; a lowered `max_tokens` is not reused on the JSON-repair retry.
- **Not built:** a Streamlit app, and a "slow middle → jump-cut" rule.

## Confidentiality

Kuku's input pack is confidential. `input/`, `outputs/`, `private/`, `config/aliases.yaml`, `gold/*.csv` and `.cache/` are git-ignored, and tests and demos use a fictional synthetic show (`samples/synthetic_show/`). `python scripts/leak_check.py` checks tracked files and history for pack content.

## Project docs

`docs/BRIEF_COMPLIANCE.md` (the brief's requirements), `docs/PRD.md`, `docs/TECH_SPEC.md`, `docs/EVAL_PLAN.md`, `docs/PLAN.md`, `decisions.md` (decision log), `report.md` (build log with real numbers), `ai_log.md` (where AI tools got it wrong).
