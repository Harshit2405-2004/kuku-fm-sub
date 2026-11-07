# Build report

A running log of every task Claude Code executes, in order. A new session must be able to resume from this file alone.

**Rules:** append one entry per task ID (from docs/PLAN.md), newest at the bottom. Never rewrite earlier entries; add corrections as new entries. Paste real command output (shortened), not summaries of what you expected.

**Entry template**
```
### T<id>: <task title>  ·  <YYYY-MM-DD HH:MM>  ·  status: done | partial | blocked
**Goal:** <one line>
**What I did:** <3–6 bullets>
**Files changed:** <paths>
**Commands & results:** 
    $ pytest -q  → 23 passed
    $ python run.py ... → 50/50 episodes, 3m12s, 182k tokens
**Decisions:** <D-0xx ids added/affected, or "none">
**AI mistakes caught:** <short; also logged in ai_log.md, or "none">
**Open issues / risks:** <or "none">
**Next:** <next task ID>
```

**Checkpoint entry template** (when stopping at CP-x)
```
### CP-<n> reached  ·  <time>
**Summary for Harshit:** <what's built, key numbers>
**Please review:** <exact files/sections to look at>
**Questions / proposed decisions awaiting approval:** <D-0xx list>
```

---

## Status board
**Deadline:** TBD (Harshit to fill in, IST) · **Submit by:** deadline − 3 h

| Phase | Status | Last task | Notes |
|---|---|---|---|
| 0 Setup | ☐ | | Harshit |
| 1 Parser | ☐ | | |
| 2 Gold | ☐ | | Harshit |
| 3 LLM/propose/build | ☐ | | |
| 4 Arcs/judge/rank/run A | ☐ | | |
| 5 Eval / run B | ☐ | | |
| 6 App/deploy | ☐ | | |
| 7 Doc/video/submit | ☐ | | |

---

## Log
<!-- Claude Code: append entries below -->

### T0-fix: Kickoff resolutions (owner rename, leak fixes, spec clarifications)  ·  2026-11-07  ·  status: done
**Goal:** Apply Harshit's answers to the 12 kickoff points before the first commit.
**What I did:**
- Renamed the owner to Harshit in all tracked and private files (63 occurrences); added INSTRUCTIONS.md (generic input path, no account-switch step, leak check before first commit and push).
- Made 5 show-specific doc lines generic (PRD ×2, RESEARCH ×2, TECH_SPEC filename); moved one research sentence to private notes.
- Clarified specs: deterministic jump-cut (TECH_SPEC §4.3 + PROCESS_GUIDE Process 3 with exact shot list), diversity scope and arc rules (§4.6 + Process 6), public-logs rule (CLAUDE.md hard rule 3), requirements.txt in §2 layout, leak check in §11.
- Built scripts/leak_check.py (alias names + private keyword list + 20 dialogue lines); drafted private/leak_keywords.txt (39 phrases) for review at CP-1.
- Recreated .venv on Python 3.13.2 and installed exactly the §9 packages; pinned them in requirements.txt.
**Files changed:** CLAUDE.md, INSTRUCTIONS.md (new), KICKOFF_PROMPT.md, decisions.md, ai_log.md, report.md, requirements.txt (new), scripts/leak_check.py (new), docs/{PRD,RESEARCH,TECH_SPEC,PLAN,PROCESS_GUIDE,BRIEF_COMPLIANCE,SUBMISSION,EVAL_PLAN}.md, .claude/{agents,skills}; private files (not tracked).
**Commands & results:**
    $ python scripts/leak_check.py → first run: FAIL (1 hit, docs/RESEARCH.md:62); after rewording: PASS (30 files, 39 keywords, 20 dialogue lines)
    $ python --version → Python 3.13.2
    $ pytest -q → not run (no code or tests yet; Phase 1 starts next)
**Decisions:** D-013 (Python 3.13, Proposed), D-014, D-015, D-016, D-017 (Accepted per Harshit's kickoff answers)
**AI mistakes caught:** truncated grep missed a plot line (ai_log #1)
**Open issues / risks:** Deadline not yet provided (placeholders in PLAN, INSTRUCTIONS, status board). Leak keyword list awaits review at CP-1.
**Next:** T1.1

### T1.1: Synthetic show  ·  2026-11-07  ·  status: done
**Goal:** A fictional 3-episode pack in the exact real format, for tests, demos and prompt examples.
**What I did:**
- Wrote `samples/synthetic_show/` ("The Locket", original characters) with the edge cases listed in its README.
- Ep 3 reproduces PROCESS_GUIDE Processes 1–3 block for block (E03-B010/B011/B029–B031 at the guide's times), so build tests can use real parsed data.
- Added `config/aliases.example.yaml` (format doc, synthetic names only).
- Phase plan saved to `docs/phase_plans/phase-1.md`.
**Files changed:** samples/synthetic_show/*, config/aliases.example.yaml, docs/phase_plans/phase-1.md
**Commands & results:**
    $ grep -c per type → ep1 20 (8 CAM, 3 ACT, 2 SFX), ep2 13 (6, 2, 1), ep3 41 (18, 5, 5)
    $ python scripts/leak_check.py → PASS
    $ pytest -q → no tests yet (parser is T1.2)
**Decisions:** none
**AI mistakes caught:** none
**Open issues / risks:** none
**Next:** T1.2
