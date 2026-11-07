# CLAUDE.md: Kuku Promo Finder

Claude Code reads this file on every turn. Keep it short and follow it strictly.

## What this project is
A take-home for the **Kuku AI Generalist** role, Problem 1: **"Find the Promos"**. The tool reads a microdrama screenplay pack (50 timestamped episode scripts) and outputs a **ranked shortlist of 20–60 s promo clips**. Each clip has its episode, the start/end timestamps of every segment, the hook, the cliffhanger, and one line on why it works.
The owner is **Harshit**. He makes the decisions and must be able to explain every line in an interview, where Kuku may run this on a **new show** with **their own, stronger model API**.

## Source of truth (read before starting any phase)
1. `docs/BRIEF_COMPLIANCE.md`: every requirement from Kuku's brief. **This wins any conflict.**
2. `docs/PRD.md`: what we're building and why
3. `docs/TECH_SPEC.md`: how to build it (schemas, algorithms, CLI)
4. `docs/EVAL_PLAN.md`: how quality is measured
5. `docs/PLAN.md`: phases, task IDs, checkpoints
6. `decisions.md`: decisions already made. Don't silently reverse one.

## Hard rules
1. **The LLM never writes timestamps.** Models return block IDs such as `E01-B037`, and code converts them to times. If you're tempted to parse a time out of model text, stop.
2. **No hard-coded model names in code.** Models come from `config.yaml` or CLI flags, through `promo_finder/llm.py` (LiteLLM). Every stage can use a different model. An OpenAI-compatible `api_base` must work, so Kuku can plug in their API.
3. **Confidentiality.** The repo is **public** (Kuku must be able to open it), but the input pack is confidential. Anything derived from it lives only in git-ignored paths: `input/`, `outputs/`, `private/` (show notes, explanation), `config/aliases.yaml` (character names), `gold/*.csv` (labels), and `.cache/`. Never put the show's script text, character names or plot in tracked files, prompts, tests, examples or commit messages. Tests and demos use `samples/synthetic_show/` (fictional, written by us), and prompt examples come from it too. Show-specific context is in `private/INPUT_PACK_NOTES.md`.
   **Public logs rule:** `report.md`, `decisions.md`, `ai_log.md` and `docs/phase_plans/` are public. They may contain only counts, block IDs, run IDs, timings and generic descriptions. Anything with script text, speaker names or plot goes to `private/` (e.g. `private/parse_stats_T1.3.md`, `private/smoke_T3.5.md`, `private/ai_log_details.md`), and the public file gets a one-line pointer. Run `python scripts/leak_check.py` before every commit that touches these files and before every push.
4. **Never fabricate results.** Every number in reports and docs comes from an actual run, saved in `outputs/<run_id>/`. If a run failed, say so.
5. **Never edit `gold/gold_labels.csv`.** Harshit writes it by hand. Only read it.
6. **Checkpoints are blocking.** At each `CP-x` in `docs/PLAN.md`, stop, summarise, and wait for Harshit's go-ahead.
7. **Dependencies:** only those listed in TECH_SPEC §9. Ask before adding any other.
8. **Temperature 0, cached LLM calls.** Every call is cached on disk, keyed by (model, prompt version, input hash). Reruns must be free.

## Logging (required after every task)
- Append an entry to **`report.md`** after **every** task ID in PLAN.md. Use the template at the top of that file.
- Append to **`decisions.md`** whenever you make a choice that the spec doesn't dictate: new ID, status `Proposed`, with alternatives and consequences. Harshit flips it to `Accepted`.
- Append to **`ai_log.md`** whenever an AI tool (you, a subagent, or a runtime LLM) gets something wrong and it gets caught: hallucinated API, wrong alias, bad JSON, a wrong assumption. Be honest. Kuku explicitly asks for "one place where AI got it wrong".
- You can use the `/log-decision` and `/checkpoint` skills for this.

## Code style (Harshit's preference)
- Simple, readable, human-looking Python 3.11+ (venv runs 3.13, see D-013): plain functions, small modules, few classes (Pydantic models for schemas are fine). No clever metaprogramming or deep abstraction layers.
- Comments explain **why**, not what. Each module starts with a 3–5 line docstring saying what it does and how it fits the pipeline.
- Type hints on public functions. `pathlib` for paths. No global state except config.
- Prompts live in `promo_finder/prompts/*.md` with a version header (e.g. `version: proposer_v2`). Changing a prompt means bumping its version and adding a line to `report.md` saying why.

## Commands
- Tests: `pytest -q` (must pass before every task is marked done)
- Pipeline: `python run.py --input input/<pack> --config config.yaml --run-name <name>`
- Mock run, no API: `python run.py --input samples/synthetic_show --mock`
- Eval: `python evaluate.py --run outputs/<run_id> --gold gold/gold_labels.csv`
- App: `streamlit run app.py`

## Workflow
- Work one PLAN.md task ID at a time: plan briefly, implement, test, log, then commit with the message `T<id>: <summary>`.
- Prefer a test first for deterministic code (parser, snapping, durations, IoU, ranking).
- Before marking a phase done, use the `independent-reviewer` subagent on the diff. Before the final checkpoint, use `brief-auditor`.
- If something in the brief or spec is unclear, **make a sensible assumption, log it in decisions.md, and keep going.** The brief rewards this. Only stop when you reach a checkpoint or something is irreversible.
- When the context gets long, write state to `report.md` first so a new session can resume from it.
