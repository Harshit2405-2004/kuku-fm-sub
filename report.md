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
| 0 Setup | ☑ | T0-fix | venv 3.13, git init, kit + doc fixes committed (fc4c4b7). Deadline still TBD. |
| 1 Parser | ◐ CP-1 waiting | T1.4 | 68 tests; real pack 50/50 eps parsed; alias map awaits Harshit |
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

### T1.2: Parser + tests  ·  2026-11-07  ·  status: done
**Goal:** `parse.py` (Pydantic models, tolerant parser, pack loader) with synthetic and variant tests (TECH_SPEC §3, §10).
**What I did:**
- Tests first (RED: collection failed, module missing), then `promo_finder/parse.py` and `promo_finder/aliases.canonical_speaker`.
- `test_parser.py`: exact counts per type for all 3 synthetic episodes; PROCESS_GUIDE blocks E03-B010/B011/B029–B031; capitalised scene headers; O.S./V.O. flags, including inside the emotion parens; multi-line text; duration; aliases.
- `test_parser_variants.py`: HH:MM:SS, 1–3 decimals, CRLF, extra blank lines, no SOUND FX, unknown label, missing time line, end<start, outside scene, no dialogue, episode number from filename, lower-case keys, one-line scene start/end, zip with nested folder, sort by episode number, empty folder.
- Probe on the real pack (counts only): parses cleanly.
**Files changed:** promo_finder/{__init__,parse,aliases}.py, tests/{conftest,test_parser,test_parser_variants}.py
**Commands & results:**
    $ pytest -q → (RED) 2 errors during collection: No module named promo_finder.parse
    $ pytest -q → 47 passed in 0.44s
    $ real-pack probe → 50 episodes (1..50), 3727 blocks (CAMERA 1754, DIALOGUE 1487, ACTION 372, SOUND_FX 114), 1 warning (outside scene), durations 70.5–200.75 s, 0 empty texts
**Decisions:** D-018 (parser tolerance rules, Proposed). D-014 requirements.txt already logged at kickoff.
**AI mistakes caught:** none
**Open issues / risks:** none
**Next:** T1.3

### T1.3: Aliases + real-pack parse stats  ·  2026-11-07  ·  status: done
**Goal:** `aliases.py` (load map, missing file = raw names), real-pack stats, a draft alias map for Harshit to verify.
**What I did:**
- Tests first (RED: import error), then `load_aliases`, `pack_stats` and a stats CLI (`python -m promo_finder.parse --input <pack> [--speakers] [--out]`).
- Parsed the real pack. Counts are below; speaker names, warnings and the reasoning behind the alias draft are in `private/parse_stats_T1.3.md`.
- Drafted `config/aliases.yaml` (git-ignored): 22 raw labels merged into 8 characters, ambiguous labels deliberately left unmapped and marked VERIFY.
- Found that the private notes' guess about one descriptive label was contradicted by the script context (details private). Logged as an open check for CP-1, not as an AI mistake yet.
**Files changed:** promo_finder/{aliases,parse}.py, tests/test_aliases.py; private: config/aliases.yaml, private/parse_stats_T1.3.md, outputs/parse_T1.3/episodes.json
**Commands & results:**
    $ pytest -q → (RED) 1 error during collection: cannot import load_aliases; then 54 passed in 0.37s
    $ python -m promo_finder.parse --input input → episodes 50, scenes 100, blocks 3727 (CAMERA 1754, ACTION 372, DIALOGUE 1487, SOUND_FX 114); duration min 70.5 s, max 200.8 s, total 102.7 min; raw speakers 64 → canonical 52 (with the draft map); warnings 1 (block 0.3 s past its scene end)
    $ python scripts/leak_check.py → PASS (45 files, 28 alias names, 40 keywords, 20 dialogue lines)
**Decisions:** none new (alias format documented in config/aliases.example.yaml)
**AI mistakes caught:** none yet; the alias draft is verified at CP-1
**Open issues / risks:** One descriptive label probably covers one character across early and late episodes; a global alias map can't split a label by episode. If Harshit finds it's really two people, we need per-episode overrides (a spec change).
**Next:** T1.4

### T1.4: Compact view + token table  ·  2026-11-07  ·  status: done
**Goal:** `compact.py`: the one-line-per-block text the LLM reads, a CLI to print an episode, and token counts per episode.
**What I did:**
- Tests first (RED: import error), then `format_tc`, `compact_block`, `compact_episode`, `estimate_tokens` and a CLI: `python -m promo_finder.compact --input <pack> --ep N` / `--tokens`.
- Line format exactly as in TECH_SPEC §4.1 (`[E03-B011 00:13.0–00:14.8] MARA (Stunned, Quiet): "You sold the house?"`), plus scene marker lines and flags (D-019).
- Token table for the real pack (counts only; uses the draft alias map and cast list).
**Files changed:** promo_finder/compact.py, tests/test_compact.py
**Commands & results:**
    $ pytest -q → (RED) 1 error during collection; then 68 passed in 0.43s
    $ python -m promo_finder.compact --input input --tokens → 50 episodes; est_tokens min 1327, median 2399, max 3471, total 120540
    per-episode est_tokens (ep:tokens): 1:2820 2:2377 3:3471 4:3039 5:2156 6:2946 7:1988 8:1944 9:2733 10:1927 11:2695 12:1843 13:2452 14:1833 15:1920 16:2083 17:2465 18:2676 19:2363 20:2328 21:2807 22:2609 23:2230 24:2370 25:2648 26:1992 27:2760 28:2854 29:2412 30:2454 31:2864 32:3274 33:2582 34:3459 35:2346 36:3383 37:2771 38:1861 39:2220 40:2005 41:1975 42:1327 43:2623 44:1757 45:2448 46:2577 47:2386 48:1569 49:2334 50:1584 
**Decisions:** D-019 (compact-view details, Proposed)
**AI mistakes caught:** none
**Open issues / risks:** Proposer input is about 2.4k tokens per episode plus the prompt, well inside free-tier context limits. The whole show (~120k) would fit one long-context call, but D-003 keeps per-episode calls.
**Next:** CP-1

### CP-1 reached  ·  2026-11-07
**Summary for Harshit:** Phase 1 is built and committed (T1.1–T1.4). There's a fictional 3-episode synthetic show, a tolerant parser, an alias loader, a stats CLI and the compact LLM view. `pytest -q` → 68 passed. Real pack: 50/50 episodes, 100 scenes, 3727 blocks (CAMERA 1754, ACTION 372, DIALOGUE 1487, SOUND_FX 114), durations 70.5–200.8 s (102.7 min total), 1 harmless warning. 64 raw speaker labels → 52 canonical speakers with the draft alias map. About 120.5k estimated tokens for the whole show (median 2.4k per episode).
**Please review:**
1. `config/aliases.yaml`: every line marked VERIFY, and the deliberately unmapped labels at the bottom. One descriptive label contradicts the private notes' guess; the reasoning is in `private/parse_stats_T1.3.md`.
2. `private/parse_stats_T1.3.md`: speaker list and the one warning.
3. One compact view: `python -m promo_finder.compact --input input --ep 1`.
4. `private/leak_keywords.txt`: add or remove keywords.
**Proposed decisions awaiting approval:** D-013 (Python 3.13 venv), D-018 (parser tolerance rules), D-019 (compact-view details).
**Reviewer verdict:** PASS WITH FIXES, 0 blocking. It reproduced every real-pack count and found 0 silently dropped lines on the real pack, and git history plus commit messages are clean. Should-fix items left for Harshit:
- (a) Lines after a block's text, or a `**LABEL**:` header variant, are dropped with no warning.
- (b) A malformed time string crashes the whole pack (contradicts D-018's "never crashes").
- (c) A file with no SCRIPT START marker parses to 0 blocks with only a "no dialogue" warning.
- (d) An unknown header key gets appended to the logline.
- (e) The duration test passes for the wrong reason.
- (f) The leak check reads the working tree, not staged blobs, and doesn't scan history or commit messages.
- Nits: banker's rounding in format_tc, pytest only works from the repo root, multi-line quoted dialogue, more flag spellings, the SFX label alias isn't logged.

### CP-1 fixes: parser hardening + leak check history scan  ·  2026-11-07  ·  status: done
**Goal:** Apply Harshit's CP-1 instructions: malformed time → warning and skip; unknown formats → warning, never a silent drop; line-coverage check; duration test that can fail; leak check covering staged files, all history and commit messages (`--pre-push`).
**What I did:**
- RED: 21 new tests in `tests/test_parser_hardening.py` and `tests/test_leak_check.py`; 19 failed. The 2 duration tests passed at once because the logic was already right; the old test just couldn't tell whether it was. Each new test now pins one side of max().
- Restructured `parse.py` into a line-reading pass that places or reports every non-empty line, plus a building pass (IDs, times, scenes, warnings). Same public API.
- Rewrote `scripts/leak_check.py` as testable functions: `scan_working_tree`, `scan_staged`, `scan_history` (+ `--pre-push`). The tests use a throwaway git repo and a made-up keyword.
- Nits: `**LABEL**:` header variant, flag spellings, multi-line quoted dialogue, half-up timecode rounding, a `pytest.ini` so tests run from any directory, and a compact CLI error when there are no args.
**Files changed:** promo_finder/{parse,compact}.py, scripts/leak_check.py, tests/{test_parser_hardening,test_leak_check,test_compact,test_aliases}.py, pytest.ini, CLAUDE.md, INSTRUCTIONS.md, KICKOFF_PROMPT.md, docs/TECH_SPEC.md §11, decisions.md, ai_log.md
**Commands & results:**
    $ pytest -q → (RED) 19 failed, 2 passed (new tests only)
    $ pytest -q → 89 passed (from repo root), 89 passed (from tests/)
    $ python -m promo_finder.parse --input input → 50 eps, 3727 blocks (unchanged); line coverage 11931/11931 placed, 0 unassigned; 1 warning (unchanged)
    $ python scripts/leak_check.py --pre-push → PASS (28 alias names, 40 keywords, 20 dialogue lines, full history)
**Decisions:** D-013, D-018, D-019 → Accepted (Harshit, CP-1). D-020 (hardening, Accepted), D-021 (small choices, Proposed).
**AI mistakes caught:** ai_log #2 (claimed "never crashes" without a test for malformed times; caught by the independent reviewer).
**Open issues / risks:** Harshit's alias corrections, keyword changes and deadline didn't come through (the template placeholders were still in his message, and the files are unchanged). Pending.
**Next:** T3.1

### T3.1: Current free model IDs, verified  ·  2026-11-07  ·  status: done
**Goal:** Find the current free-tier Gemini and Groq model IDs, verify each with a 1-token LiteLLM call, record them.
**What I did:**
- Web search (2 queries): contradictory limits and unconfirmable names, so I didn't use it for IDs (ai_log #3).
- Listed models from `generativelanguage.googleapis.com/v1beta/models` and `api.groq.com/openai/v1/models` with our keys.
- Made a 1-token `litellm.completion` call (temperature 0) to 5 candidates and checked `litellm.supports_response_schema`.
- Wrote `config.yaml` (models per stage, concurrency, retries, cache, prices left unfilled until verified, build and rank parameters from TECH_SPEC §4).
**Files changed:** config.yaml (new), decisions.md, ai_log.md
**Commands & results:**
    gemini/gemini-3.8-flash      157.9s schema=True  OK finish=length usage=3/0
    gemini/gemini-3.5-flash        2.7s schema=True  OK finish=length usage=3/0
    gemini/gemini-3.5-flash-lite   4.2s schema=True  OK finish=length usage=3/0
    groq/openai/gpt-oss-120b       0.4s schema=True  OK finish=length usage=73/1
    groq/qwen/qwen3.8-27b          0.1s schema=True  OK finish=length usage=14/1
**Decisions:** D-022 (default models, Proposed)
**AI mistakes caught:** ai_log #3 (web sources unreliable for model IDs)
**Open issues / risks:** Free-tier daily quotas are unverified (Harshit to check AI Studio / Groq console). Gemini 3+ temperature deprecation warning.
**Next:** T3.2

### T3.2: config + cache + llm + mock  ·  2026-11-07  ·  status: done
**Goal:** One swappable, cached, validated LLM call path with retries and usage accounting (TECH_SPEC §5).
**What I did:**
- Tests first (RED: collection errors), then `config.py` (load + CLI override rules), `cache.py` (sha256 key, atomic write), `llm.py` (`call_llm`, backoff, `response_format` fallback, JSON extraction and one repair retry, usage, `summarize_usage`), and a `mock.py` stub (mock replies come in T3.4).
- 22 new tests with a fake completion function (no network).
- Live check outside pytest (scratch script, temp cache): one tiny schema call per default model through `call_llm`.
**Files changed:** promo_finder/{config,cache,llm,mock}.py, tests/{test_config,test_llm}.py, docs/phase_plans/phase-3.md
**Commands & results:**
    $ pytest -q → (RED) 2 errors during collection; then 111 passed in 7.88s
    live: proposer gemini/gemini-3.5-flash → valid JSON (E03-B011); judge groq/openai/gpt-oss-120b → valid JSON (E03-B011); repeat call cache_hit=True
    live usage: proposer 2 calls (1 cache hit), 206 prompt / 480 completion tokens, 5.43 s; judge 1 call, 256 / 175 tokens, 0.67 s
**Decisions:** D-023 (LLM-layer details, Proposed)
**AI mistakes caught:** none
**Open issues / risks:** Gemini's hidden reasoning tokens inflate completion tokens (480 for a tiny answer). Watch the free-tier token quotas in the full run.
**Next:** T3.3
