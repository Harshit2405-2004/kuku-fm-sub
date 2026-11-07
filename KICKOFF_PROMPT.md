# Prompts for Claude Code

`INSTRUCTIONS.md` tells you **when** to send each prompt (the step numbers are shown next to each one below).
- Send **Prompt 1** once, at Step 9.
- Send **Prompt 2** any time you start a fresh session (after `/clear`, a restart or a crash).
- Everything else is a ready reply for a specific step. Copy it, fill in the `<…>` parts, and send.

---

## Prompt 1: Kickoff (Step 9, paste once)

```
You are building "Kuku Promo Finder", my take-home for the Kuku AI Generalist role (Problem 1: Find the Promos). I'm Harshit. I own every decision and must be able to explain every line in the interview, where Kuku will run this on a NEW show and may plug in THEIR OWN, stronger model through an API.

STEP 0 — Load context and check the setup. Read these fully, in this order, before doing anything else:
  1. CLAUDE.md (hard rules — non-negotiable)
  2. docs/BRIEF_COMPLIANCE.md (Kuku's brief — wins any conflict)
  3. docs/PRD.md, docs/TECH_SPEC.md, docs/EVAL_PLAN.md
  4. docs/PLAN.md (phases, task IDs, checkpoints) and INSTRUCTIONS.md (which steps are mine, so you know when to wait for me)
  5. docs/PROCESS_GUIDE.md (worked examples of snapping, ranking and IoU — your code must reproduce these numbers)
  6. decisions.md (D-001..D-012 are Accepted — never reverse one silently)
  7. report.md and ai_log.md (templates and current state)
  8. private/INPUT_PACK_NOTES.md (confidential — never copy its content into tracked files)
  9. docs/SKILLS_AND_TOOLS.md §3 (how to use superpowers alongside our existing spec)
Then check the setup: confirm you can see the superpowers skills, our project skills (log-decision, checkpoint, run-pipeline) and the subagents independent-reviewer and brief-auditor; confirm the Python venv is active and its version is 3.11+; confirm input/ contains the pack and `git status` shows it as ignored. Also note my OS and use commands that work on it.
Then reply with:
  (a) a 10-line summary of what we're building, plus the 5 hard rules you consider most important
  (b) setup check results (anything missing → tell me the exact command to fix it)
  (c) any contradictions or gaps between the docs, each with a proposed resolution
  (d) the Phase 1 task IDs you will do
Then STOP and wait for my "go".

HOW TO WORK (every phase, after I say go):
- The approved spec is docs/PRD.md + docs/TECH_SPEC.md. No open-ended brainstorming. At the start of each phase, use superpowers `writing-plans` to break that PLAN.md phase into small steps, save it to docs/phase_plans/phase-<n>.md, show me a 5-line summary, then execute.
- One task ID at a time. For deterministic modules (parse, build, rank, metrics) use `test-driven-development` (failing test first). Use `systematic-debugging` for failures and `verification-before-completion` before calling anything done. Tests for build.py and rank.py must include the worked examples in docs/PROCESS_GUIDE.md (Processes 3 and 6) and produce exactly those numbers.
- After EVERY task: (1) `pytest -q` green, (2) a report.md entry using its template with REAL command output, (3) /log-decision for any choice the spec doesn't make (Status: Proposed), (4) ai_log.md for any AI mistake (yours, a subagent's, or a runtime LLM's), (5) git commit "T<id>: <summary>". Never git push or deploy — pushing and deploying are mine.
- At every CP-x in PLAN.md: run /checkpoint (which includes the independent-reviewer subagent), then STOP. Never start the next phase without my explicit go-ahead.
- Things you must WAIT for me on, even mid-phase:
    • T3.5 smoke test: wait until I send "Gold labels done" with the gold episode numbers. Use only non-gold episodes for smoke tests and prompt iteration.
    • T5.2: wait until I say "ratings done" before computing precision.
    • Before any push: run scripts/leak_check.py and show me the result.
- Gold set: never open gold/gold_labels.csv yourself. Before Phase 5 don't read anything in gold/ except ad_observations.md (and only after I say labels are done). In Phase 5, only evaluate.py reads gold_labels.csv.
- Where the spec is silent: make a sensible assumption, /log-decision it, keep going. Stop early only for a checkpoint, a "wait for me" item above, an irreversible action, or a hard-rule conflict.
- Never: let an LLM produce timestamps; hard-code model IDs; put the show's script text, character names, plot, gold labels or outputs into any git-tracked file, prompt example, test or commit message; invent numbers; add dependencies outside TECH_SPEC §9 without asking.
- Model IDs: at T3.1, look up the CURRENT free-tier model IDs for Gemini (Google AI Studio) and Groq, verify each with a 1-token litellm call, and record them in config.yaml + decisions.md. Don't trust model names from memory.
- Free-tier limits: on 429s, back off and resume from cache — don't switch models or providers on your own. If a quota blocks a run, stop and tell me the options.
- Code style: simple, readable Python 3.11. Plain functions, small modules, a short docstring per module explaining where it fits in the pipeline, comments that explain WHY. If I couldn't explain it on a whiteboard, simplify it.
- Keep me informed briefly: one line in chat per finished task ("T1.2 done — parser + 14 tests passing"). Details go in report.md.
- If context gets long: make sure report.md holds the full current state, then tell me it's a good moment to /clear and use the resume prompt.

Start with STEP 0 now.
```

---

## Prompt 2: Resume (after `/clear`, a restart or a crash)

```
Resume work on Kuku Promo Finder. Read CLAUDE.md, the status board and the LAST 3 entries of report.md, the open (Proposed) items in decisions.md, the current phase in docs/PLAN.md, and docs/phase_plans/ if present. Run `pytest -q` and `git status`. Tell me in ≤8 lines: where we are, test status, uncommitted changes, what's next, and anything you're waiting on me for. Then wait for my "go".
```

---

## Replies by step

### Step 9: after Claude's STEP 0 answer
```
Resolutions: (1) <…> (2) <…>. Log any that change the spec with /log-decision. go — start Phase 1.
```

### Step 11: CP-1 (after you've fixed the alias map)
```
CP-1: I've corrected config/aliases.yaml by hand. Diff it against your draft and log every correction you got wrong in ai_log.md generically (e.g. "merged two distinct characters into one"), with the names in private/ai_log_details.md (this is our "AI got it wrong" evidence). Re-run the parser stats. Then start Phase 3 (T3.1–T3.4) while I do the gold labels. Do NOT read anything in gold/ and do NOT run the T3.5 smoke test until I say "Gold labels done".
```

### Step 12d: gold labels finished
```
Gold labels done. Gold episodes: <e.g. 1, 3, 8, 12, 17, 18, 27, 31, 41, 45>. Held-out (never use for prompt iteration): <3 of them>. You may now read gold/ad_observations.md (NOT gold_labels.csv) and use its hook patterns in the proposer prompt. Then run the T3.5 smoke test on 3 NON-gold episodes and stop at CP-2.
```

### Step 14: CP-2 (prompt review)
```
CP-2 feedback on proposer_v1: <your notes, e.g. "E05 promo starts 4 s before the hook", "E09 clip leaks the answer">. Bump to proposer_v2, re-run the same 3 episodes, and show a before/after table (candidate, hook offset, duration, hook line, cliff line). Log the change in report.md (counts and generic reasons only; the table goes in private/smoke_T3.5.md). If it's better, proceed to Phase 4.
```

### Step 16: CP-3 (after full run A)
```
CP-3 approved. Accept D-0xx, D-0yy. Proceed to Phase 5 (T5.1, then generate the blind sheet for T5.2 and wait for my ratings).
```
or
```
CP-3: one round of changes before eval: (1) <…> (2) <…>. Don't tune on gold episodes. Re-run full run A after the changes (new run ID), then show the checkpoint summary again.
```

### Step 17: blind ratings done
```
Ratings done in gold/precision_ratings.csv. Compute precision@10 and judge–human Spearman. Then do T5.3 (run B: swap only <proposer|judge> to <model>; plus the 10-episode stability re-run with the cache off) and T5.4 (eval_report.md for A and B + comparison table). Then propose 6–8 failure cases with evidence (promo ID, what's wrong, stage, root cause, fix) and stop.
```

### Step 17: failure gallery
```
Keep failures <#, #, #, #>. Here they are in my words: <…>. Put them into both eval reports' Failure gallery section as written. Then /checkpoint for CP-4.
```

### Step 18: CP-4 (final config)
```
CP-4: final config is <run A | run B | mix: proposer=<…>, judge=<…>>, because <reason>. Log it as a decision (Owner: Harshit, Accepted). Proceed to Phase 6.
```

### Step 19: before pushing (CP-5)
```
Run scripts/leak_check.py and `git status`, and show me both. List every file that will be pushed for the first time. Don't push — I will.
```

### Changes at any checkpoint
```
CP-<n>: not yet. Changes: (1) … (2) …. Make them, log the decisions, re-run the reviewer, and show me the checkpoint summary again.
```

### Step 20: solution doc draft
```
Draft private/solution_doc_draft.md following docs/SUBMISSION.md §2 exactly (sections, word budgets). Use ONLY numbers from the final runs and cite run IDs next to them. Include the AI/code/human split table, the top 5 promos, the metrics table, my 3–5 failures as written, the cost per show (measured) plus extrapolation to 150 and 1,000 shows/month, and the best ai_log.md entry. Mark every sentence that is your inference rather than a measured fact with [CHECK].
```

### Step 23: final audit (CP-6)
```
Run the brief-auditor subagent on everything: repo, latest outputs, private/solution_doc_draft.md, README and the links list I'll paste: <PDF, app, repo, outputs folder, video>. Fix all blocking gaps in your lane, list the ones that need me, and remove any over-claims from the doc draft.
```

### Step 25: model-swap rehearsal (interview prep)
```
Rehearse the interview swap (PLAN T8.2): run the full pipeline on samples/synthetic_show with --model openai/<model> --api-base <OpenAI-compatible URL> --api-key-env <VAR>, cache off. Then run 10 real episodes the same way. Report wall time, tokens and any error. Fix only what breaks the swap path, and add the exact working command to the README's "Swap the model" section.
```

### Step 26: format robustness (interview prep)
```
Do PLAN T8.1: make 2 mutated copies of the pack in input/mutations/ (rename speakers, HH:MM:SS timestamps, CRLF line endings, drop the CONTINUITY NOTES line, uppercase headers). Run both. Fix only crashes, add a regression test for each fix using the synthetic show, and report.
```