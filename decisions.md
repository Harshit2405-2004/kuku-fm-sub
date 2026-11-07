# Decisions log

Every non-obvious choice is recorded here: what we chose, what we rejected, and what it costs us. Kuku's brief grades "the assumptions you made where the brief was silent" and "what you gave to AI vs code vs human", and this file is the evidence.

**Rules**
- Append only. Never delete an entry. To reverse one, add a new entry that says `Supersedes D-0xx`.
- Claude Code adds entries with `Status: Proposed`. Harshit changes them to `Accepted` or `Rejected` at checkpoints.
- Keep each entry short.

**Template**
```
## D-0xx: <title>
- Date: YYYY-MM-DD · Owner: Harshit | Claude · Status: Proposed | Accepted | Rejected | Superseded
- Context: <why a decision was needed>
- Decision: <what we chose>
- Alternatives: <what else, and why not>
- Consequences: <what this costs us and what it buys us; how it shows up in the eval or interview>
- Reversible?: yes/no (how)
```

---

## D-001: Solve Problem 1 (Find the Promos)
- Date: 2026-11-07 · Owner: Harshit · Status: Accepted
- Context: The brief says pick one of three problems, and the choice itself is graded.
- Decision: Problem 1.
- Alternatives: P2 (AI lawyer): unrelated to Kuku's business, likely the most crowded, and hallucinated law is the main risk. P3 (own problem): highest variance; it needs evidence that it matters *more than P1*, which is hard to show in a few hours. A continuity checker was considered (the pack has name and place drift) and kept as a "noticed along the way" note.
- Consequences: The work ties directly to Kuku's largest cost (marketing, ₹1,105 Cr, 77.7% of FY26 expenses). The input pack makes the output checkable. Many candidates may pick it, so we stand out on execution and evaluation, not on the choice.
- Reversible?: No, after submission.

## D-002: The LLM never writes timestamps. It returns block IDs, and code computes the times.
- Date: 2026-11-07 · Owner: Harshit · Status: Accepted
- Context: LLMs misread and invent numbers. A promo with wrong timestamps is useless to an editor.
- Decision: Every block gets an ID (`E01-B037`). Models output IDs only, and code maps IDs to times, snaps and validates.
- Alternatives: Let the model output times and then verify them (still error-prone, needs repair logic). Pure rules with no LLM (can't judge drama).
- Consequences: Timestamp hallucination is impossible by construction. Validity is 100%. IDs that don't exist are caught and retried. This is our clearest "AI vs code" talking point.
- Reversible?: n/a

## D-003: One proposer call per episode, plus one cross-episode arc pass
- Date: 2026-11-07 · Owner: Harshit · Status: Accepted
- Context: The whole show is about 100–150k tokens. One giant call is possible on some models, but it's hard to control and is all-or-nothing.
- Decision: Run the proposer per episode (parallel, cacheable, retryable). Run a separate arc pass over loglines plus per-episode summaries for multi-episode promos.
- Alternatives: A single long-context call (cheaper in calls, but worse attention to detail, a single point of failure, and not possible on small free models).
- Consequences: Robust to free-tier limits and partial failures. Cost scales linearly with episodes. Arc quality depends on how good the summaries are.
- Reversible?: Yes (config).

## D-004: Cuts snap to CAMERA shot boundaries; the hook must start within 3.0 s
- Date: 2026-11-07 · Owner: Harshit · Status: Accepted
- Context: The brief requires a hook in the first 3 seconds. Editors cut on shots.
- Decision: TECH_SPEC §4.3 snapping rules. Overlong spans become jump-cuts; too-short ones are extended or rejected.
- Alternatives: Cut exactly on dialogue times (mid-shot cuts look amateur).
- Consequences: Clean, editor-ready cuts. It sometimes trades away a little context, which shows up as `needs_context` and is measured.
- Reversible?: Yes (thresholds in config).

## D-005: LiteLLM provider layer, with the model chosen per stage and an OpenAI-compatible api_base
- Date: 2026-11-07 · Owner: Harshit · Status: Accepted
- Context: The brief says "we may also connect stronger models through APIs we provide, so a solution where the model is easy to swap will shine."
- Decision: All calls go through `llm.py` (LiteLLM). Models are set in `config.yaml` per stage, overridable with flags (`--model`, `--api-base`, `--api-key-env`).
- Alternatives: Use the Gemini SDK directly (locks us to one vendor). LangChain (heavy, harder to explain).
- Consequences: Swapping is one flag, and we rehearse it (T8.2). LiteLLM is a dependency we have to understand at a basic level.
- Reversible?: Yes.

## D-006: The judge uses a different model family from the proposer
- Date: 2026-11-07 · Owner: Harshit · Status: Accepted
- Context: LLM judges tend to favour outputs that look like their own (self-preference bias).
- Decision: Default to a Gemini proposer and a Groq-hosted judge from a different family. Measure judge–human agreement (EVAL §2).
- Alternatives: Same model for both (simpler, but biased); no judge, rank by proposer order (no calibrated scores).
- Consequences: Less bias, plus two free quotas instead of one. Two providers to configure.
- Reversible?: Yes (config).

## D-007: Harshit hand-labels the gold set before seeing any model output
- Date: 2026-11-07 · Owner: Harshit · Status: Accepted
- Context: Without ground truth, "quality checking" is only opinion. Labelling after seeing the outputs anchors you to them.
- Decision: 12–20 gold promos over about 10 episodes, labelled before the smoke test output is read, with 3 held-out episodes.
- Alternatives: LLM-generated gold (circular). No gold (weak quality lens).
- Consequences: Costs about an hour of Harshit's time, and it's the strongest evidence in the submission. It is a single-annotator set, which is a stated limitation.
- Reversible?: n/a

## D-008: The repo is public but contains nothing derived from the confidential pack
- Date: 2026-11-07 · Owner: Harshit · Status: Accepted
- Context: The prototype link must "open for anyone", and the brief says not to publish or share the pack.
- Decision: Git-ignore `input/`, `outputs/`, `private/`, `config/aliases.yaml`, `gold/*.csv` and `.cache/`. Tests, demos and prompt examples use a fictional synthetic show. A leak-check script runs before every push. Raw outputs are shared only through the Drive link in the form.
- Alternatives: Private repo (Kuku can't open it). Public repo including the pack (breaks confidentiality).
- Consequences: A little extra work (synthetic show, leak check), and it shows good judgement.
- Reversible?: No (once pushed, it's out), so the leak check is mandatory.

## D-009: Spoilers allowed; mild bonus for early episodes
- Date: 2026-11-07 · Owner: Harshit · Status: Accepted
- Context: Should late reveals be used as hooks? Which promos should go first?
- Decision: Allow spoilers (category leaders use payoff moments). Rank bonus +0.06 for episodes 1–5 and +0.03 for episodes 6–15, because those promos land the viewer at the start of the show.
- Alternatives: Ban spoilers (loses the strongest hooks). No bonus.
- Consequences: The ranking favours promos at the top of the funnel. Weights are tunable and should later be learnt from ad performance.
- Reversible?: Yes.

## D-010: Output a ranked shortlist for a human editor, not one "best" promo
- Date: 2026-11-07 · Owner: Harshit · Status: Accepted
- Context: Taste is subjective, and Kuku A/B tests creatives.
- Decision: 15–25 diverse promos with risk flags. A human picks and trims.
- Alternatives: Auto-post the top 1 (too risky; there's no performance data).
- Consequences: Clear human-in-the-loop story. Adoption metric = % of posted promos that came from the shortlist.
- Reversible?: Yes.

## D-011: Temperature 0, versioned prompts, on-disk cache
- Date: 2026-11-07 · Owner: Harshit · Status: Accepted
- Context: Free-tier rate limits, plus the brief's "build something you can run again".
- Decision: Cache keyed by model, prompt version and input hash. A manifest is written per run.
- Alternatives: No cache (reruns burn quota and results drift).
- Consequences: Reruns are free and reproducible. Stability is measured separately with the cache off.
- Reversible?: Yes (`--no-cache`).

## D-012: Simple, readable code; Streamlit app plus CLI; Python 3.11
- Date: 2026-11-07 · Owner: Harshit · Status: Accepted
- Context: Harshit has to explain every line, and the brief says polish earns nothing.
- Decision: Plain functions and a minimal dependency list (TECH_SPEC §9). Streamlit for the hosted demo.
- Alternatives: FastAPI with a React front end (more polish, no extra credit). No-code (harder to rerun and swap models).
- Consequences: Fast to build, easy to defend in the interview.
- Reversible?: Yes.

<!-- Claude Code: append new decisions below as D-013, D-014, … with Status: Proposed -->

## D-013: Use Python 3.13 for the venv (spec says 3.11+)
- Date: 2026-11-07 · Owner: Claude · Status: Accepted (Harshit, CP-1)
- Context: The kit venv was Python 3.10 (below the 3.11 floor). Python 3.11 isn't installed on the dev machine; 3.13 is.
- Decision: Recreate `.venv` with `py -3.13`. Code stays 3.11-compatible (no 3.12+/3.13-only syntax), so `python>=3.11` in TECH_SPEC §9 still holds.
- Alternatives: Install 3.11 with winget (extra setup step, no benefit we need); keep 3.10 (violates the spec).
- Consequences: All tests run on 3.13. Streamlit Cloud must be set to 3.11+ (pick 3.13 to match). The interview machine only needs 3.11+.
- Reversible?: Yes (recreate the venv with 3.11 and `pip install -r requirements.txt`).

## D-014: requirements.txt with exactly the §9 packages, pinned
- Date: 2026-11-07 · Owner: Harshit · Status: Accepted
- Context: TECH_SPEC §2 had no requirements file, but Streamlit Cloud and a reproducible interview run need one.
- Decision: `requirements.txt` lists only the TECH_SPEC §9 packages, pinned to the versions the tests pass on. Added to the §2 layout.
- Alternatives: Unpinned (a new LiteLLM release could break the live demo); pyproject/uv lock (more to explain).
- Consequences: Reproducible installs. Pins must be bumped deliberately (re-run tests, update this file).
- Reversible?: Yes.

## D-015: Deterministic jump-cut construction
- Date: 2026-11-07 · Owner: Harshit · Status: Accepted
- Context: TECH_SPEC §4.3 said "s1_end roughly 12–25 s in" and "s2_start such that total ≤ 55 s", which allows many answers, and the PROCESS_GUIDE example gave no shot list.
- Decision: s1_end = first shot boundary ≥ max(hook_end, start+12); else the last boundary in [hook_end, start+25]; else hook_end with flag `midshot_s1`. s2_start = earliest shot start after s1_end that keeps total ≤ 55 s and isn't inside a DIALOGUE block (else the next shot start). If s2_start would be after the cliff block's start, reject with `cliff_segment_too_long` (Claude's addition, so the cliff line is never chopped). PROCESS_GUIDE Process 3 now gives the exact shot list (93 s hook-to-cliff, 94.5 s snapped → 52 s).
- Alternatives: Pick s2 to maximise length up to 60 s (less headroom for an editor's trim); let the LLM pick the cut (violates D-002 spirit: cuts are code).
- Consequences: Same input always gives the same cut; the worked example is a unit test. Some long spans get rejected instead of producing a chopped cliff (visible in rejected.json).
- Reversible?: Yes (thresholds in config).

## D-016: Public logs carry only counts, IDs, timings and generic descriptions
- Date: 2026-11-07 · Owner: Harshit · Status: Accepted
- Context: report.md, decisions.md, ai_log.md and docs/phase_plans/ are pushed to a public repo, but PLAN asked for parse stats and smoke-test excerpts in report.md.
- Decision: Public files hold only counts, block IDs, run IDs, timings and generic descriptions. Script text, speaker names and plot go to `private/` (parse_stats_T1.3.md, smoke_T3.5.md, ai_log_details.md) with a one-line pointer. Added to CLAUDE.md hard rule 3; PLAN T1.3/T3.5 updated.
- Alternatives: Keep everything in report.md and scrub before push (one slip leaks the pack forever).
- Consequences: Two places to read at checkpoints. The public log still shows the process; the details stay confidential.
- Reversible?: No once pushed, hence the rule.

## D-017: Leak check built at kickoff with three word lists, run before the first commit
- Date: 2026-11-07 · Owner: Harshit · Status: Accepted
- Context: The first scan found show-specific scene details in tracked docs (now made generic). A names-only check would have missed them.
- Decision: `scripts/leak_check.py` checks every file git would publish against alias names (config/aliases.yaml), show keywords (private/leak_keywords.txt: title words, places, props, scene types) and 20 fixed-seed dialogue lines from input/. It runs before the first commit, before commits touching public logs, and before every push.
- Alternatives: Build it at T6.4 as planned (too late: the first commit would already be in history).
- Consequences: Some harmless generic words had to be reworded (e.g. a trope example in RESEARCH.md). The keyword list is a draft for Harshit to review at CP-1.
- Reversible?: n/a

## D-018: Parser tolerance rules where TECH_SPEC §3 is silent
- Date: 2026-11-07 · Owner: Claude · Status: Accepted (Harshit, CP-1)
- Context: §3.2 lists the warnings but not what happens to the affected block, or where speaker flags live.
- Decision: (1) A block with no time line is skipped with a warning, and later IDs stay contiguous (so IDs always map to a timed block). (2) Speaker flags (O.S., V.O., O.C., CONT'D) are extracted from any paren group, including inside the emotion parens (the real pack has both forms), into a new `Block.flags` list. (3) A non-CAMERA/ACTION/SOUND FX label whose text isn't quoted becomes DIALOGUE with an "unquoted" warning (how we detect "unknown labels"). (4) "Outside its scene" uses a 0.1 s tolerance. (5) A scene missing start/end takes them from its blocks, with a warning. (6) Episodes are sorted by episode number, not filename; duplicates warn.
- Alternatives: Fail the whole episode on a bad block (one typo would kill the live demo); keep untimed blocks with guessed times (code would invent timestamps).
- Consequences: Never crashes on odd input, and every oddity is visible in the warnings. Skipping an untimed block shifts later IDs versus "position in file", which only matters if someone counts blocks by hand.
- Reversible?: Yes.

## D-019: Compact-view details where TECH_SPEC §4.1 is silent
- Date: 2026-11-07 · Owner: Claude · Status: Accepted (Harshit, CP-1)
- Context: §4.1 gives the block-line format but not scene boundaries, speaker flags or how tokens are counted.
- Decision: (1) Add a `## SCENE n · heading · start–end` line before each scene, so the model sees where locations change (useful for cuts and the per-scene diversity cap). (2) Speaker shown as canonical name in caps, emotion in (), flags in [] (e.g. `VERA (Startled) [O.S.]`). (3) Timecodes use whole tenths so 59.96 s prints 01:00.0. (4) Tokens estimated as len/4, not `litellm.token_counter`, because the count only budgets calls, and the real per-model count is logged from API usage in Phase 3.
- Alternatives: No scene lines (the model has to infer scene changes from times); litellm's tokenizer (model-specific, slower, and the estimate is only for planning).
- Consequences: A few dozen extra tokens per episode. Real token usage still comes from the API response and goes into the manifest (NFR7).
- Reversible?: Yes.

## D-020: Parser and leak-check hardening after the CP-1 review
- Date: 2026-11-07 · Owner: Harshit · Status: Accepted
- Context: The independent reviewer found that a malformed timestamp crashed the whole pack, some unusual formats were dropped without a warning, a test passed for the wrong reason, and the leak check ignored staged files and git history.
- Decision: (1) A malformed block time gives a warning and that block is skipped; a malformed scene time falls back to its blocks. (2) Every non-empty line is either placed (header, scene, block) or reported as an "unassigned line" warning. Episodes carry `lines_total` and `lines_unassigned`, and the parse summary prints the coverage (target 0 unassigned). (3) A file with no SCRIPT START marker starts at the first SCENE/block line, with a warning. Unknown `KEY:` header lines warn instead of being appended to the logline. Duplicate scene numbers warn once. (4) `leak_check.py` scans the working tree and staged blobs by default; `--pre-push` adds every line ever added on all branches plus every commit message.
- Alternatives: Fail the episode on bad input (one typo kills the interview demo); scan only HEAD (a leak fixed in a later commit still ships with the push).
- Consequences: Real pack: 11,931/11,931 lines placed, 0 unassigned, same 3,727 blocks. Pre-push now scans all history, which takes a few seconds.
- Reversible?: Yes.

## D-021: Small parser and display choices made during the CP-1 fixes
- Date: 2026-11-07 · Owner: Claude · Status: Proposed
- Context: The reviewer's nits left the exact choices to us.
- Decision: Accept `**LABEL**:` as a block header. Normalise flag spellings (O.S / OS / Off-screen → O.S.; V.O / VO → V.O.; CONT'D with a curly apostrophe → CONT'D). Map label `SFX` to SOUND_FX like `SOUND FX`. Strip quotes per line in multi-line dialogue. `format_tc` rounds half up (0.25 → 0.3) instead of Python's half-to-even; this amends D-019. Add `pytest.ini` so tests run from any directory.
- Alternatives: Leave the variants as emotions or speakers (worse prompts, missed flags); keep banker's rounding (hard to explain, and timecodes reach editors).
- Consequences: More real-world variants parse cleanly. Display timecodes can differ by 0.1 s from round(); stored times are untouched.
- Reversible?: Yes.

## D-022: Default free models: Gemini 3.5 Flash (proposer, arc) and gpt-oss-120b on Groq (judge)
- Date: 2026-11-07 · Owner: Claude · Status: Proposed
- Context: T3.1 asks for current free-tier IDs, verified live. Web sources disagreed and named models we couldn't confirm, so we listed models from each provider's own API with our keys, then made a 1-token LiteLLM call to each candidate.
- Decision: proposer and arc = `gemini/gemini-3.5-flash` (OK in 2.7 s, LiteLLM schema support = True). Judge = `groq/openai/gpt-oss-120b` (OK in 0.4 s, schema = True; a different family from Gemini, per D-006; Groq lists strict JSON-schema decoding for it). Also verified as fallbacks: `gemini/gemini-3.5-flash-lite` (4.2 s), `groq/qwen/qwen3.8-27b` (0.1 s).
- Alternatives: `gemini/gemini-3.8-flash` (newest; the call succeeded but took 157.9 s for 1 token, and one blog reports only ~20 requests/day on the free tier, which can't cover 50 episodes). Free-tier quotas are not published by API; Harshit should confirm them in AI Studio / the Groq console.
- Consequences: LiteLLM warns that `temperature` is "planned for removal" for Gemini 3+. It works today and we keep temperature 0 (hard rule 8), but this is a known future break. With max_tokens=1 Gemini returned no text (reasoning tokens), so real calls need enough max_tokens (4000 set).
- Reversible?: Yes (config.yaml or --proposer-model / --judge-model).

## D-023: LLM-layer details where TECH_SPEC §5 is silent
- Date: 2026-11-07 · Owner: Claude · Status: Proposed
- Context: §5 fixes LiteLLM, per-stage config, retries and the cache, but not how flags combine, what gets cached, or how odd endpoints are handled.
- Decision: (1) `--api-base` / `--api-key-env` apply to the stages whose model was overridden on the CLI, or to all stages if no model flag was given, so "upgrade only the judge" keeps the free proposer. (2) `call_llm` returns (validated object, raw text) so stages can save raw replies unedited (FR8). (3) Only the final valid reply is cached; every attempt is recorded in usage. (4) Retry on HTTP 408/429/5xx with backoff 2, 4, 8… s; other errors fail fast. (5) If an endpoint rejects `response_format`, retry once without it and validate JSON extracted from the text (fences and prose stripped). (6) Schema-constrained output is requested when `litellm.supports_response_schema` says yes, JSON mode otherwise. (7) A missing key env var is a clear error naming the variable; key values are never stored.
- Alternatives: tenacity for retries (optional per §9; a 10-line loop is easier to explain); caching every attempt (would make a bad reply "stick").
- Consequences: Kuku's endpoint works even without JSON-schema support. Live check: both default models returned schema-valid JSON. Gemini 3.5 Flash billed 480 completion tokens for a ~170-character answer (hidden reasoning tokens), so token budgets and the cost estimate must use the reported usage, not the visible text.
- Reversible?: Yes.
