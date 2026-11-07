# Kuku Promo Finder

Reads a microdrama screenplay pack and finds the best **20–60 s promo clips**. For each clip it gives the episode, segment timestamps, hook, cliffhanger and why it works, then ranks them.
This was built for the Kuku AI Generalist take-home, Problem 1.

> 🚧 This README is the **project kit index**. In task T6.2 Claude Code replaces it with the product README (quickstart, model swap, outputs, limitations).

## What's in this kit
| File | What it is | Who reads it |
|---|---|---|
| `CLAUDE.md` | Rules Claude Code follows on every turn | Claude Code |
| `KICKOFF_PROMPT.md` | Prompts to paste into Claude Code (kickoff, resume, checkpoint replies) | You |
| `docs/BRIEF_COMPLIANCE.md` | Every requirement in Kuku's brief and how we meet it | Both |
| `docs/RESEARCH.md` | Kuku, the microdrama market, the role, problem comparison | Both |
| `docs/PRD.md` | What we're building, for whom, goals, assumptions, requirements | Both |
| `docs/TECH_SPEC.md` | Architecture, schemas, algorithms, LLM layer, outputs, tests | Claude Code |
| `docs/EVAL_PLAN.md` | How quality is measured (gold set, metrics, failure gallery) | Both |
| `docs/PLAN.md` | Phases, task IDs, owners, checkpoints, timeline | Both |
| `docs/SUBMISSION.md` | Form fields, 2-page doc outline, video script, final checklist | You |
| `docs/SKILLS_AND_TOOLS.md` | Claude Code plugins/skills to install and how we use them | You |
| `decisions.md` | Decision log (D-001…), with alternatives and consequences | Both |
| `report.md` | Task-by-task build log, appended by Claude Code | Both |
| `ai_log.md` | Where AI tools got it wrong, and how it was caught | Both |
| `.claude/agents/` | `independent-reviewer`, `brief-auditor` subagents | Claude Code |
| `.claude/skills/` | `/log-decision`, `/checkpoint`, `/run-pipeline` | Claude Code |
| `gold/` | Gold-label template and ad observations (your hand labels go here) | You |
| `private/` *(git-ignored)* | `EXPLANATION.md` (why everything is planned this way), `INPUT_PACK_NOTES.md` | You |
| `input/` *(git-ignored)* | Put Kuku's script pack here | — |

## Start
1. Read `private/EXPLANATION.md` (about 20 min).
2. Do Phase 0 in `docs/PLAN.md`.
3. Open Claude Code in this folder and paste Prompt 1 from `KICKOFF_PROMPT.md`.

## Confidentiality
Kuku's input pack is confidential. `input/`, `outputs/`, `private/`, `config/aliases.yaml`, `gold/*.csv` and `.cache/` are git-ignored, and tests and demos use a fictional synthetic show. See decisions.md D-008.
