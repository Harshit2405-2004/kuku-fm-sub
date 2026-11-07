---
name: run-pipeline
description: Run the promo-finder pipeline on an input pack (mock, smoke, or full), then evaluate it and record the results. Use when asked to run, re-run, smoke-test, compare models, or evaluate a run.
---

Run the pipeline reproducibly and record the results honestly. Arguments: $ARGUMENTS (for example `full A`, `smoke E05,E09,E14`, `mock`, `compare A B`).

1. **Pre-flight:** `pytest -q` must pass. Check that `.env` has the key named by each stage's `api_key_env` (check presence only, never print values). Show the models per stage from `config.yaml` plus any overrides.
2. **Run:**
   - mock: `python run.py --input samples/synthetic_show --mock --run-name mock`
   - smoke: `python run.py --input input/<pack> --episodes <list> --run-name smoke`
   - full: `python run.py --input input/<pack> --run-name <name>`
   - With a different model: add `--model …` or `--proposer-model …` / `--judge-model …`, and `--api-base … --api-key-env …` if needed.
3. If it fails, use systematic debugging: read `outputs/<run_id>/run.log`, find the first error, fix the root cause, and re-run (the cache makes this cheap). Don't hand-edit outputs.
4. **Evaluate** (if `gold/gold_labels.csv` exists): `python evaluate.py --run outputs/<run_id> --gold gold/gold_labels.csv`.
5. **Record:** append to report.md the run ID, episodes processed, candidates (built, rejected), final promos, tokens and time per stage, estimated cost, and key eval metrics. Copy numbers from `manifest.json` and `eval_metrics.json`; never retype them from memory.
6. Show the top 5 promos (timecodes, hook → cliff, why, flags) in chat. These outputs contain confidential script text, so keep them in chat, `outputs/` or `private/` only.
