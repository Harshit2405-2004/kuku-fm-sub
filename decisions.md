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
- **Note (CP-2, 2026-11-07):** Superseded in part by D-029 (models): the proposer is now gpt-oss-120b and the judge qwen3.8-27b, still different families.
- Context: LLM judges tend to favour outputs that look like their own (self-preference bias).
- Decision: Default to a Gemini proposer and a Groq-hosted judge from a different family. Measure judge–human agreement (EVAL §2).
- Alternatives: Same model for both (simpler, but biased); no judge, rank by proposer order (no calibrated scores).
- Consequences: Less bias, plus two free quotas instead of one. Two providers to configure.
- Reversible?: Yes (config).

## D-007: Harshit hand-labels the gold set before seeing any model output
- Date: 2026-11-07 · Owner: Harshit · Status: Superseded by D-033
- **Note (CP-2, 2026-11-07):** Superseded by D-033: the gold picks were drafted by a non-pipeline Claude session and reviewed and approved by Harshit, not hand-labelled from scratch.
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
- **Note (CP-2, 2026-11-07):** Python version: see D-013 (the venv runs 3.13).
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
- Date: 2026-11-07 · Owner: Claude · Status: Accepted (Harshit, CP-2, 2026-11-07)
- Context: The reviewer's nits left the exact choices to us.
- Decision: Accept `**LABEL**:` as a block header. Normalise flag spellings (O.S / OS / Off-screen → O.S.; V.O / VO → V.O.; CONT'D with a curly apostrophe → CONT'D). Map label `SFX` to SOUND_FX like `SOUND FX`. Strip quotes per line in multi-line dialogue. `format_tc` rounds half up (0.25 → 0.3) instead of Python's half-to-even; this amends D-019. Add `pytest.ini` so tests run from any directory.
- Alternatives: Leave the variants as emotions or speakers (worse prompts, missed flags); keep banker's rounding (hard to explain, and timecodes reach editors).
- Consequences: More real-world variants parse cleanly. Display timecodes can differ by 0.1 s from round(); stored times are untouched.
- Reversible?: Yes.

## D-022: Default free models: Gemini 3.5 Flash (proposer, arc) and gpt-oss-120b on Groq (judge)
- Date: 2026-11-07 · Owner: Claude · Status: Accepted (Harshit, CP-2, 2026-11-07)
- **Note (CP-2, 2026-11-07):** Superseded in part by D-029 (models): all stages moved to Groq because of Gemini's 20 requests/day free tier. Gemini 3.5 Flash-Lite is run B's proposer (D-032).
- Context: T3.1 asks for current free-tier IDs, verified live. Web sources disagreed and named models we couldn't confirm, so we listed models from each provider's own API with our keys, then made a 1-token LiteLLM call to each candidate.
- Decision: proposer and arc = `gemini/gemini-3.5-flash` (OK in 2.7 s, LiteLLM schema support = True). Judge = `groq/openai/gpt-oss-120b` (OK in 0.4 s, schema = True; a different family from Gemini, per D-006; Groq lists strict JSON-schema decoding for it). Also verified as fallbacks: `gemini/gemini-3.5-flash-lite` (4.2 s), `groq/qwen/qwen3.8-27b` (0.1 s).
- Alternatives: `gemini/gemini-3.8-flash` (newest; the call succeeded but took 157.9 s for 1 token, and one blog reports only ~20 requests/day on the free tier, which can't cover 50 episodes). Free-tier quotas are not published by API; Harshit should confirm them in AI Studio / the Groq console.
- Consequences: LiteLLM warns that `temperature` is "planned for removal" for Gemini 3+. It works today and we keep temperature 0 (hard rule 8), but this is a known future break. With max_tokens=1 Gemini returned no text (reasoning tokens), so real calls need enough max_tokens (4000 set).
- Reversible?: Yes (config.yaml or --proposer-model / --judge-model).

## D-023: LLM-layer details where TECH_SPEC §5 is silent
- Date: 2026-11-07 · Owner: Claude · Status: Accepted (Harshit, CP-2, 2026-11-07)
- Context: §5 fixes LiteLLM, per-stage config, retries and the cache, but not how flags combine, what gets cached, or how odd endpoints are handled.
- Decision: (1) `--api-base` / `--api-key-env` apply to the stages whose model was overridden on the CLI, or to all stages if no model flag was given, so "upgrade only the judge" keeps the free proposer. (2) `call_llm` returns (validated object, raw text) so stages can save raw replies unedited (FR8). (3) Only the final valid reply is cached; every attempt is recorded in usage. (4) Retry on HTTP 408/429/5xx with backoff 2, 4, 8… s; other errors fail fast. (5) If an endpoint rejects `response_format`, retry once without it and validate JSON extracted from the text (fences and prose stripped). (6) Schema-constrained output is requested when `litellm.supports_response_schema` says yes, JSON mode otherwise. (7) A missing key env var is a clear error naming the variable; key values are never stored.
- Alternatives: tenacity for retries (optional per §9; a 10-line loop is easier to explain); caching every attempt (would make a bad reply "stick").
- Consequences: Kuku's endpoint works even without JSON-schema support. Live check: both default models returned schema-valid JSON. Gemini 3.5 Flash billed 480 completion tokens for a ~170-character answer (hidden reasoning tokens), so token budgets and the cost estimate must use the reported usage, not the visible text.
- Reversible?: Yes.

## D-024: Cut-builder choices where TECH_SPEC §4.3 is silent
- Date: 2026-11-07 · Owner: Harshit (tie rule) / Claude (rest) · Status: Accepted (Harshit, CP-2, 2026-11-07)
- Context: §4.3 leaves ties, a few edge cases and the role of the proposed start/end blocks open.
- Decision: (1) Snap-start tie (two shots equally close to hook − 1 s): the earlier shot wins (more lead-in). (2) Shots are searched by time, not file order (real scripts list a line before the shot it sits under). (3) The cut is computed from the hook and cliff blocks only; the proposed start_block/end_block are stored for reference. Otherwise the 3 s hook rule and the no-leak end rule could be broken by the model. (4) A jump-cut whose only valid cut leaves < 20 s is rejected as `too_short`. (5) "Shot holding the cliff" = the camera shot with start < cliff end ≤ shot end; a cliff ending exactly on a shot boundary ends there. (6) A float tolerance of 1e-6 s is used at every boundary (exactly 3.0 s or 60.0 s passes).
- Alternatives: Honour the model's start/end blocks (gives up code control of the two hardest constraints, against D-002's spirit); keep under-20 s jump-cuts with dur_ok=false (an invalid clip in the list).
- Consequences: Validity is guaranteed by construction (EVAL check 1). The model's start/end picks can still be compared with ours in the failure gallery.
- Reversible?: Yes.

## D-025: Proposer prompt v1 and stage details
- Date: 2026-11-07 · Owner: Claude · Status: Accepted (Harshit, CP-2, 2026-11-07)
- Context: TECH_SPEC §4.2/§6 want the brief's promo definition verbatim, 3 hook patterns from gold/ad_observations.md, and ≤ 2 synthetic examples. ad_observations.md may not be read until Harshit says "Gold labels done", and the brief's exact wording isn't stored in the repo.
- Decision: (1) v1 quotes the brief fragments recorded in docs/BRIEF_COMPLIANCE.md §B (the closest verbatim text we have). (2) v1's 3 opening patterns come from public category research (docs/RESEARCH.md §3); proposer_v2 will swap in Harshit's observed patterns after the gold labels. (3) One worked example (synthetic ep 3, from PROCESS_GUIDE). (4) `reasoning` is the first field, so the model explains before choosing IDs (§4.5 uses the same idea). (5) The order check is start ≤ hook ≤ cliff by start time and end_block ending at or after the cliff, because end_block may be the shot the cliff sits in, which starts before the cliff line. (6) One repair round for bad IDs or order, then drop and log. (7) Mock proposer: the first line with "?"/"!" (else any line) that has a later line 15–45 s after it to cut on.
- Alternatives: Wait for ad_observations before writing any prompt (blocks Phase 3); put the example in a separate file (harder to see what the model sees).
- Consequences: Live check on the synthetic show: 4 candidates over 3 episodes, 0 invalid IDs, all cuts valid. Synthetic ep 3 is contaminated as a test (the model returned the prompt's own example), so it can't be used to judge prompt quality. Paste Harshit's exact brief wording into the prompt if available (v2).
- Reversible?: Yes (prompt versioned; cache keys include the version).
- **Update 2026-11-07 (CP-2):** point (1) is superseded. Harshit supplied the brief's exact promo definition; it is stored verbatim in docs/BRIEF_COMPLIANCE.md §B and quoted word for word in proposer_v3 and judge.md (D-035).

## D-026: Per-episode speaker-alias override
- Date: 2026-11-07 · Owner: Harshit (choice of option b) / Claude (format) · Status: Accepted (Harshit, CP-2, 2026-11-07)
- Context: The CP-1 alias evidence sheet showed that one descriptive speaker label means two different characters: one character in a single early episode (2 blocks) and another in 9 later episodes (51 blocks). A global label → name map can't express that. Details are in private/ai_log_details.md.
- Decision: An alias key `"E<n>:LABEL"` (e.g. `"E02:LABEL"`) overrides `LABEL` for episode n only. `load_aliases` normalises it to `E02:LABEL` (upper case, zero-padded); `canonical_speaker(raw, aliases, ep)` checks the episode key first, then the global key, then falls back to title case. The parser passes the episode number. `leak_check.py` strips the `E<n>:` prefix so the bare label is still scanned for.
- Alternatives: (a) keep the global mapping and accept 2 mislabelled blocks; they only feed context text, but the ranker or judge would attribute one character's lines to the main villain. (c) Per-block overrides (more precise, but nothing needs that today).
- Consequences: Real pack after the change: 64 raw labels → 51 canonical speakers (was 52); the 2 blocks resolve to the right character; the other 51 are unchanged. A new show with no alias file is unaffected. 3 alias tests + 1 leak-check test.
- Reversible?: Yes (delete the override line).

## D-027: Proposer thinking budget set via config (`reasoning_effort: low`)
- Date: 2026-11-07 · Owner: Claude · Status: Accepted (Harshit, CP-2, 2026-11-07); as revised: provider-default reasoning (`reasoning_effort: null`), not `low`
- Context: Gemini 3.5 Flash spends about 2.3k hidden reasoning tokens per synthetic episode (T3.4). Over 50 real (longer) episodes, plus repair calls and run B, that eats the free daily quota and adds latency. Harshit asked whether the budget can be set from config.yaml, so a model swap still needs no code change.
- Decision: Add an optional per-stage key `reasoning_effort` (minimal | low | medium | high | null). `llm.py` passes it to LiteLLM only when set. LiteLLM 1.108.2 maps this one OpenAI-style name to each provider's own control (Gemini 3 → `thinkingLevel`; OpenAI-compatible endpoints and Groq's gpt-oss take it as is). The value is part of the cache key, but only when set, so existing cache entries stay valid. If an endpoint answers 400 naming `reasoning_effort`, the call is retried once without it, like `response_format` (D-023). Set the **proposer to `low`**; arc and judge stay at the provider default until they are tested.
- Evidence (synthetic show only, run `outputs/effort_synth_20261107_184345/`, proposer_v1, same prompts):

  | setting | completion tokens (3 eps) | per ep | candidates | built valid | invalid IDs / repairs |
  |---|---|---|---|---|---|
  | default (cached T3.4 run) | 7,028 | 2,999 / 2,480 / 1,549 | 4 | 4/4 | 0 / 0 |
  | **low** | **1,791 (−75%)** | 732 / 543 / 516 | 3 | 3/3 | 0 / 0 |
  | minimal | 769 (−89%) | 405 / 213 / 151 | 4 | 4/4 | 0 / 0 |

  Prompt tokens are identical (7,114). Ep 3 picked the same hook and cliff at all three settings, but it is contaminated (it's the prompt's worked example). On eps 1–2, low and minimal both chose a **different hook** from the default: a physical action or a revealing line placed earlier, rather than an entrance shot or a later line. Claude's read is that these are at least as strong; that's a judgement, not a measurement. low returned 1 candidate for ep 1 where the default returned 2. API latency was dominated by 503/429 retries, so it isn't comparable.
- Alternatives: `minimal` (cheapest, and its picks matched low's, but it leaves the least room for reasoning on long real episodes with several scenes); keep the default (safe but 4× the tokens); a provider-specific `thinking` dict (not portable to Kuku's endpoint).
- Consequences: About 4× fewer proposer completion tokens. Risk: 3 synthetic episodes is a tiny sample. **Check at T3.5:** run the smoke episodes at `low`, and run 1 of them at the default too, comparing picks (details private). If quality drops, set `reasoning_effort: null` in config.yaml; no code change needed. A swapped-in stronger model keeps `low` unless config says otherwise.
- Reversible?: Yes (one config line).
- **Update 2026-11-07, T3.5 real-episode check (run `outputs/smoke_T3.5_20261107_192614/`, proposer_v2, 3 non-gold episodes):** the synthetic result did **not** carry over. At `low`, 3 episodes gave 3 proposals → 1 built clip and 2 rejected `too_short` (hook→cliff spans of 11–12 s). At the default setting, the one episode with both runs gave 2 proposals → 2 built clips, one of them identical to low's. One episode returned 0 proposals at both settings (allowed for a quiet episode). One default-setting call failed JSON validation at about 3,982 completion tokens, probably because hidden reasoning used up `max_tokens: 4000` (unconfirmed: finish_reason isn't recorded); the repair round fixed it. The `medium` cells and one default cell couldn't run because the Gemini daily quota ran out (see D-029). **Revised recommendation:** don't adopt `low` for the proposer. Use `null` (or `medium` once tested) and raise the proposer's `max_tokens` to 8000, or switch proposer models per D-029. The config still says `low` until Harshit decides at CP-2.
- **Resolved 2026-11-07 (Harshit):** `reasoning_effort: null` (provider default) for Gemini and for gpt-oss, unless the re-smoke shows a problem. gpt-oss re-smoke at the default: 6 proposals over 3 episodes, completion 1,708–2,994 tokens per call (no problem found, see D-030 for max_tokens).

## D-028: Gold-label tooling: neutral worksheet → CSV converter
- Date: 2026-11-07 · Owner: Harshit (workflow) / Claude (details) · Status: Accepted (Harshit, CP-2, 2026-11-07)
- **Note (CP-2, 2026-11-07):** Superseded in practice by D-033 (gold drafted by a non-pipeline Claude, human-approved). The tooling is unchanged and was used to write the CSV; CP-2 added stricter input checks (D-034).
- Context: Harshit picks the gold promos by hand (EVAL_PLAN §1). Typing times by hand is slow and error-prone, and hard rule 5 says Claude never writes or edits the gold labels.
- Decision: (1) `scripts/make_gold_worksheet.py` writes every block of the chosen episodes in file order, with no highlighting, ranking or suggestions, plus empty answer slots, into `private/` (git-ignored). (2) `scripts/gold_from_worksheet.py` is run **by Harshit**. It converts block IDs to times from the parsed pack and writes `gold/gold_labels.csv` in the EVAL_PLAN format; the CSV is still Harshit's, since the script only transcribes his picks. (3) Hard errors block the write: unknown IDs, an ID from the wrong episode, a quality outside 1–3, or bad order (by time: start ≤ hook ≤ cliff by start time and cliff end ≤ end-block end, the same rule as D-025, because the end block can be the shot holding the cliff). A length outside 20–60 s is only a warning, because the human label is ground truth. (4) Arc lines take optional `hook=E01:B012 cliff=E42:B019`; by default hook = the first segment's first block and cliff = the last segment's last block. An arc counts under its first segment's episode. (5) The script refuses to overwrite an existing CSV (or worksheet) without `--force`. (6) Held-out episodes are in `gold/holdout.txt` (git-ignored) and are never used for prompt iteration.
- Alternatives: label straight into the CSV with times (slow, typo-prone); have Claude pre-select candidate moments (anchoring; it would invalidate gold recall).
- Consequences: 18 tests on the synthetic show only; they were written after the code, so a mutation check was run (4 deliberate bugs, each caught). Claude has not opened the filled worksheet or the CSV, and won't until evaluation.
- Reversible?: Yes.

## D-029: The default proposer model can't cover a full run on its free tier
- Date: 2026-11-07 · Owner: Harshit · Status: **Accepted** (Harshit, 2026-11-07: option a; no billing, stay on free tiers)
- Context: During T3.5, Gemini returned HTTP 429 with `quotaId: GenerateRequestsPerDayPerProjectPerModel-FreeTier`, `quotaValue: 20` and `retryDelay: 64822s`, meaning **20 requests per day** for gemini-3.5-flash. Run A needs at least 50 proposer calls plus repairs and arc calls. Groq's response headers, read live the same day: `x-ratelimit-limit-requests: 1000`, `x-ratelimit-limit-tokens: 8000` (per minute), for both `openai/gpt-oss-120b` and `qwen/qwen3.8-27b`. A real episode prompt is about 4.3–6.1k tokens.
- Options: (a) **Recommended:** proposer and arc → `groq/openai/gpt-oss-120b`; judge → `groq/qwen/qwen3.8-27b` (a different family, so D-006 holds); concurrency 1 per model. Needs one small code fix first: on a 429, honour the provider's retry-after. Today's backoff (2+4+8+16 s) is shorter than the 60 s token window, so a TPM limit would fail the call. Gemini 3.5 Flash becomes the "swap one stage's model family" for run B, on whatever its 20/day allows. Costs a new 3-episode smoke test on gpt-oss (cheap on Groq). (b) Enable billing on the Gemini key (no code change; cost not estimated here, because prices must come from the pricing page, not memory). (c) Try `gemini/gemini-3.5-flash-lite`: it has its own per-model quota, but its daily limit is unknown until it 429s.
- Consequences of (a): about 1 proposer call per minute under 8k TPM, so roughly 50–60 min for 50 episodes. Start run A early on 2026-11-08. The Gemini quota resets in about 18 h (around 13:30 IST on 2026-11-08).
- Reversible?: Yes (config.yaml only, apart from the retry-after fix).
- Applied 2026-11-07: config.yaml stages = proposer/arc `groq/openai/gpt-oss-120b`, judge `groq/qwen/qwen3.8-27b`, concurrency 1. **For the doc:** explain that a paid tier (or Kuku's own API) removes the 20/day and 8k/min caps; the pipeline needs only a config change (D-005).

## D-030: Rate limits on Groq: honour the provider's wait hint, size max_tokens from measured usage
- Date: 2026-11-07 · Owner: Claude · Status: Accepted (Harshit, CP-2, 2026-11-07)
- Context: Groq's free tier is 8,000 tokens/minute per model. Our fixed backoff (2+4+8+16 s = 30 s) can't outlast a 60 s token window, and max_tokens had to be sized without knowing how Groq counts it.
- Measured (live, 2026-11-07, gpt-oss-120b): (1) **max_tokens is not charged up front.** These all returned 200 with an idle window: tiny prompt + max_tokens 9,000; a ~4,074-token prompt + 4,500; and a real episode prompt (5,031 tokens) + 4,400. A "Request too large … TPM" 429 appeared only when earlier calls were still inside the 1-minute window, so actual prompt + completion tokens are what count. (2) **Reasoning can eat the whole cap:** one episode used 2,994 of max_tokens 3,000 (twice, in separate runs). On another attempt with that cap, Groq returned **HTTP 400 `json_validate_failed`** with an empty `failed_generation`: the model ran out of tokens before writing JSON. (3) Groq isn't deterministic at temperature 0: the same request gave 1,619 and then 2,275 completion tokens (relevant to EVAL check 5, self-stability).
- Decision: (a) On a 429, wait for the longest provider hint: `Retry-After`, `x-ratelimit-reset-tokens`, `x-ratelimit-reset-requests` (only when 0 requests remain), or the text "try again in Xs" / Gemini's `retryDelay`, plus 0.5 s. Use the exponential backoff only when there's no hint. If the hint exceeds `retries.max_wait_s` (120 s; a daily quota), fail at once with the provider's error. (b) Retry Groq's generation-failure 400s (`json_validate_failed`, "Failed to generate/validate JSON") like a 5xx. (c) max_tokens: proposer and arc 4,000, judge 3,000. Since max_tokens isn't reserved, a cap above the observed maximum (2,994) costs nothing in TPM and avoids empty replies. The per-minute budget is governed by actual totals (largest smoke call 5,378 + 2,994 = 8,372, which went through on an idle window). (d) concurrency 1 per model. 9 new tests.
- Alternatives: a client-side token bucket that predicts usage (more code, still needs the 429 path); a smaller max_tokens to "fit under 8k" (it causes the empty-JSON failure and saves nothing, because max_tokens isn't reserved).
- Consequences: the re-smoke waited 56.5 s and 46.0 s on Groq's hints and then succeeded. A daily quota now fails in seconds, not after 5 pointless retries.
- Reversible?: Yes.

## D-031: Proposer reads CAMERA text cut to 70 characters (config `proposer_input.camera_max_chars`)
- Date: 2026-11-07 · Owner: Harshit (requested) / Claude (measurement) · Status: Accepted (Harshit, CP-2, 2026-11-07)
- Context: Fit the proposer input under Groq's 8k tokens/minute with room for reasoning.
- Decision: `compact_episode(..., camera_max_chars)` shortens CAMERA text only, ending in "…"; dialogue, action and SFX lines are never cut. It's on by default for the proposer (70). The judge always sees full lines (TECH_SPEC §4.5). The worksheet script now uses the same `shorten()` helper.
- Measured (LiteLLM token counter for gpt-oss, proposer_v2 messages): 80% of the pack's 1,754 CAMERA lines are over 70 chars (median 93). Ep 6: 5,179 → 4,981 (−4%); ep 24: 4,327 → 4,159 (−4%); ep 40: 3,725 → 3,474 (−7%). Whole pack: 220,040 → 210,675 (−4%); largest episode 6,013 → 5,770. Tighter limits barely help: 50 chars → 204,499; 40 → 201,077. Groq's own prompt count runs about 8–11% above this counter (chat-format overhead): 5,378 / 4,558 / 3,858 for the same three episodes.
- Why the saving is small: in ep 24's user message, the `[ID start–end]` stamps on every line are about 1,170 of about 2,900 tokens, against about 1,080 for all CAMERA text. Shorter stamps (for example dropping the end time, or `B046 1:12` instead of `[E24-B046 01:12.3–01:15.0]`) are the bigger lever if we need one. Not done: D-002 lets the model see times for length reasoning, and that's a prompt-format change for Harshit to approve.
- Risk: a visual hook described late in a long shot line could be cut off. Watch the CP-2 review for missed visual hooks; `camera_max_chars: null` restores full text.
- Reversible?: Yes (config).

## D-032: Run B = proposer `gemini/gemini-3.5-flash-lite` on the 10 gold episodes, same judge
- Date: 2026-11-07 · Owner: Claude (proposal; Harshit asked for a Groq Llama) · Status: Accepted (Harshit, CP-2, 2026-11-07), with a condition: a 1-token call to gemini-3.5-flash-lite must succeed first. Checked 2026-11-07 20:48 IST: OK, so run B uses flash-lite
- Context: Harshit asked for run B with a different Groq model family (e.g. Llama) as proposer, on the 10 gold episodes only, with the same judge, running tonight after or in parallel with run A. Groq's live model list (2026-11-07) has **no Llama chat models**, only `llama-prompt-guard-2` classifiers. The chat models are gpt-oss-120b/20b (same family as run A), qwen3.8-27b (the judge's family, so self-preference bias), and allam-2-7b (small, Arabic-focused).
- Decision (proposed): run B's proposer = `gemini/gemini-3.5-flash-lite`. It's a different family from both gpt-oss and the qwen judge, was verified in D-022, and answered a 1-token call tonight, on its own per-model quota. 10 episodes ≈ 10–12 requests, which fits even a 20/day limit (its real limit is unknown until it 429s). Reasoning default (D-027). Judge = qwen3.8-27b, same as run A. It can run in parallel with run A's proposer (different provider), but its judge calls queue behind run A's because they share qwen's 8k TPM. **Optional extra:** `gemini/gemini-3.5-flash` on the same 10 episodes after its quota resets (~13:30 IST, 2026-11-08), if time allows.
- Alternatives: proposer qwen3.8-27b (same family as the judge, which biases the comparison); gpt-oss-20b (same family, so it's a size swap, not a family swap); swap the judge too (confounds the comparison).
- Consequences: run B compares OpenAI-family vs Google-family proposers on the gold set, with the judge held fixed. If flash-lite hits a quota mid-run, report the episodes completed (never fabricate).
- Reversible?: Yes (CLI `--proposer-model`).

## D-033: Gold-set provenance (exact wording to reuse)
- Date: 2026-11-07 · Owner: Harshit · Status: Accepted (Harshit, 2026-11-07; kept public at CP-2)
- Context: EVAL_PLAN §1 assumed hand labels. Harshit reports how the gold set was actually made, and asked that this exact wording be used wherever the gold set is described (eval report, doc draft).
- **Wording to use verbatim** (Harshit's words): "Gold episodes: 1, 3, 8, 12, 17, 18, 27, 31, 42, 45. Held-out: 3, 27, 45. Provenance: picks were drafted by Claude in a separate claude.ai session (not a pipeline model), from a full read of these 10 episodes, then reviewed and approved by me; I chose to keep E31 at quality 3 with a brand-safety note, and E08/E17 as none."
  (In third-person documents, "me" = Harshit.)
- Decision: The gold set is LLM-drafted and human-approved. Report every gold-based metric (recall, recall@20, weighted recall, quiet-episode false positives) together with this provenance statement, never as "human labels" alone.
- Consequences (Claude's note, for honest reporting, not a reversal): gold recall measures agreement with a Claude-drafted, Harshit-approved shortlist, not with an independent human editor. Claude is not in the pipeline (proposer gpt-oss, judge qwen, run B Gemini; D-029, D-032), so there's no same-model leakage. Still, two LLMs can share blind spots, so recall may be inflated on moments any LLM finds obvious and say little about moments only a human would pick. Blind precision@10 (EVAL check 3, Harshit rating outputs) is the more independent human signal, and should be named as such in the doc. Claude Code (this session) has not opened the filled worksheet or the CSV.
- Reversible?: The wording is fixed by Harshit; the labels can be revised by hand.

## D-034: CP-2 reviewer fixes: retry loop, per-run rejected settings, repair failure, cache key, gold input checks
- Date: 2026-11-07 · Owner: Harshit (chose which to fix) / Claude (how) · Status: Proposed
- Context: The Phase 3 independent review (CP-2) found 11 should-fix items. Harshit picked 4 code fixes plus boundary tests and the 3 gold-converter checks to do before run A.
- Decision:
  (1) `_call_with_retries` keeps two separate budgets: `max_attempts` counts real failures, and dropping a rejected setting is free (there are only 3 possible drops), so the loop always ends with a reply or the provider's real error. No more "unreachable".
  (2) Generation-failure 400s (`json_validate_failed`, "Failed to generate/validate JSON") are checked before the rejected-parameter check, so they are retried even when their text mentions `response_format`. A setting the endpoint rejects is remembered per model for the run, in the run's config dict (`_rejected_params`, not a module global). A rejected schema falls back to JSON mode, then to no `response_format`.
  (3) If the proposer's repair call fails, the episode keeps its valid first-round candidates. The broken ones are dropped with "repair failed: …" in the log. A wrong top-level `episode` field alone no longer triggers a repair call.
  (4) The cache key includes the request settings `api_base`, `temperature`, `max_tokens` and `reasoning_effort` (always, as one dict), so two endpoints serving the same model name never share answers. Existing cache entries became invalid once; only experiment runs were cached.
  (5) Gold converter: a present but unreadable arc `hook=`/`cliff=` is an error (no silent default; a trailing comma is tolerated); arc segments out of episode/time order give a warning; `note=` is split case-insensitively, so text inside a note is never read as a field.
  (6) Boundary tests: exactly 60.0 s is a single cut and 60.1 s is not; exactly 20.0 s is a single cut and 19.9 s with dialogue right after is too_short; a hook exactly 3.0 s after the clip start passes.
- Tests: 8 llm/propose tests and 6 gold tests (RED first), plus 5 boundary tests (they lock existing behaviour, so they passed at once). 200 tests total.
- Not done (Harshit's call): no v1→v2 comparison (v3 has one, D-035). The nits are left for later.
- Reversible?: Yes.

## D-035: proposer_v3: the brief's verbatim definition plus 7 hard rules from the CP-2 review
- Date: 2026-11-07 · Owner: Harshit (rules) / Claude (wording) · Status: Proposed
- Context: Harshit's CP-2 review of the v2 smoke clips against the scripts: soft non-conflict hooks, spans too short to build, a vow used as a cliff, a beat_type that didn't match the hook, and a clip that built up to its strike instead of opening on it (ai_log #8).
- Decision: proposer_v3 quotes the brief's promo definition word for word (source: docs/BRIEF_COMPLIANCE.md §B). It adds hard rules: (1) if the stretch contains a strike, slap or shocking reveal, that moment is the hook and the clip starts on it; (2) the hook must be conflict; (3) the cliff must be an open question, so a vow, resolve or answer is not a cliff; (4) hook start → cliff end ≥ 20 s; (5) quiet episodes return fewer or zero candidates, never soft ones; (6) beat_type describes the hook honestly; (7) variety. The worked example is unchanged (synthetic), and its reasoning no longer quotes times.
- Before/after (gpt-oss-120b, same non-gold episodes 6, 24, 40; runs `smoke_T3.5_gptoss_20261107_200730` → `smoke_v3_gptoss_20261107_204635`): proposals 6 → 2; valid clips 4 → 2; too_short rejects 2 → 0; the quiet episode 2 proposals → 0. The episode containing a strike now opens on it (hook offset 1.7 s); before, the strike sat about 26 s into the clip. Both v3 clips have hook offsets ≤ 1.7 s, and both beat types now name the hook. Details are only in private/smoke_T3.5.md.
- Risks seen: (a) yield drops to about 0.7 valid clips per episode, so run A may give about 35 candidates, enough for a top 20 but with less choice; (b) rule 1 can conflict with the cliff: one v3 clip opens on the episode's strongest line and then runs on to a weaker closing beat; (c) one v3 clip is 54.4 s with a slow middle, a case for the future "slow middle → jump-cut" rule. The judge and ranker should catch (b) and (c).
- Reversible?: Yes (prompt versioned; the cache key includes the version).

## D-036: Judge design: first-3-seconds marker, batch and retry rules, brand-safety flag only
- Date: 2026-11-07 · Owner: Claude (proposed) · Status: Accepted (Harshit, 2026-11-08; none changes the evaluation method)
- Context: TECH_SPEC §4.5 fixes the rubric and fields but not how the judge knows what "the first 3 s" are, or what to do when a batch reply is incomplete. Harshit (CP-2): score hook STRENGTH in the first 3 s; flag strikes and torture, don't exclude.
- Decision: (1) lines that start in the first 3 s of the clip are marked `>>` in the excerpt, and the hook anchors score what is there (5 = strike/slap/shocking reveal inside 3 s, 3 = the big moment comes later). (2) Batches of 3 (config `judge.batch_size`; ~4.4k prompt tokens for 2 clips, so 3 fit under 8k tokens/minute). (3) A skipped clip is re-judged alone; a failed batch is retried clip by clip; still unscored → manifest error, not ranked, never given a default score. (4) graphic_violence carries no penalty; it adds "Brand-safety check before posting" to the posting note. (5) Qwen `<think>` text is stripped before JSON extraction.
- Alternatives: no marker (the judge would score the best line anywhere); penalise violence (would bury the strongest hooks, against Harshit's call); default scores for unscored clips (fabrication).
- Reversible?: Yes.

## D-037: Ranker details: greedy diversity, skip log, tie-break, code-written posting note
- Date: 2026-11-07 · Owner: Claude (proposed) · Status: Accepted (Harshit, 2026-11-08; none changes the evaluation method)
- Context: TECH_SPEC §4.6 gives the formula and caps but not the algorithm, tie-breaks or the rationale wording.
- Decision: scores normalised as (s − 1)/4; penalties from builder flags and judge risk_flags (only the keys in `rank.penalty`). Greedy diversity: at each position, take the highest promo that breaks no cap; a skipped promo is recorded once (rank, reason, final position). If every remaining promo breaks a cap, order is kept rather than leaving gaps. Ties break on hook, cliff, then id. posting_rationale is one sentence from the scores ≥ 4 / ≤ 2, the early-episode and sweet-spot bonuses, and flags. `rank.llm_rationale` stays false.
- Reversible?: Yes (weights and caps in config; changing a weight needs a decision entry).

## D-038: Run orchestration: keep going on failure, write each stage early, `--episodes`, arcs deferred
- Date: 2026-11-07 · Owner: Claude (proposed) · Status: Accepted (Harshit, 2026-11-08; none changes the evaluation method)
- Context: Run A is ~1 hour of free-tier calls; one 429 or bad reply must not lose the run.
- Decision: a failed episode (proposer) or batch (judge) is logged in `manifest.errors` and the run continues; candidates.json/rejected.json are written before judging; the cache makes a rerun of finished work free. `--episodes 1,3,8` limits a run (for run B on the gold episodes). Two runs with the same name in the same minute get a `-2` suffix. Pipeline logic lives in `promo_finder/pipeline.py` so app.py reuses it. Arcs (T4.1) are built last, per Harshit's order; until then the manifest says `"arcs": "not run"`.
- Reversible?: Yes.

## D-039: Arcs pair built candidates by ID (2 segments), instead of free block-ID segments
- Date: 2026-11-07 · Owner: Claude (proposed) · Status: Accepted (Harshit, 2026-11-08; none changes the evaluation method)
- Context: TECH_SPEC §4.4 lets the arc model return 2–3 segments as {episode, start_block, end_block}. On Groq's free tier the arc prompt with full candidate detail was estimated at ~6.6k prompt + ~2.3k completion tokens, over 8k tokens/minute for one call. Arcs also had a 30-minute build cap.
- Decision: the model only pairs two already-built single-episode candidates (opener → closer) by candidate ID; code cuts both parts on shot boundaries (opener's start → first clean shot end ≥ 8 s after the hook line; closer's tail sized to a 55 s total, ending on its own cliff). The input is one short line per candidate plus loglines shortened to 160 characters, only for episodes with candidates.
- Alternatives: free block-ID segments (spec; bigger prompt, more to validate, more ways to cut a line in half); 3-segment arcs (left for later).
- Consequences: arcs can only reuse moments the proposer already found; each arc has exactly 2 segments. The "early humiliation → late reveal" pattern is still possible if both are candidates.
- Reversible?: Yes (arcs.enabled: false turns it off).

## D-040: Correction to D-030: Groq checks prompt + max_tokens per request; retry "too large" with a lower max_tokens
- Date: 2026-11-07 · Owner: Claude (proposed) · Status: Accepted (Harshit, 2026-11-08; none changes the evaluation method)
- Context: Run A (first start, 20:58) lost one long episode to "Request too large … Limit 8000, Requested 9050" (ai_log #10). D-030 was right that only actual tokens are charged to the window, but wrong to conclude max_tokens doesn't matter: each request's prompt + max_tokens must fit under the limit.
- Decision: on that error, retry immediately with max_tokens = current − overshoot − 150, if that stays ≥ 1,000; otherwise fail the call. It doesn't use a retry attempt and doesn't wait. The cache key keeps the configured max_tokens. Config values are unchanged (proposer 4000, judge 3000), so short prompts still get the full budget.
- Alternatives: lower max_tokens in config for everyone (D-030 showed 3000 can be too few for reasoning on some episodes); smaller judge batches (more calls).
- Consequences: on very long prompts the model gets less room to reason; if it runs out, Groq's json_validate_failed is retried as before and a persistent failure is a logged episode error.
- Reversible?: Yes.

## D-041: How to finish run A after gpt-oss-120b's daily token quota ran out (needs Harshit)
- Date: 2026-11-07 · Owner: Harshit (to decide) · Status: Accepted, then amended by D-042 (host changed)
- Context: Groq free tier, gpt-oss-120b: 200,000 tokens/day. Run A finished 18/50 episodes (ai_log #11). The 32 left need about 7k tokens each (about 225k), plus the arc call. No billing (Harshit). Deadline: submit by 2026-11-08 17:00 IST.
- Options:
  (a) Finish the 32 episodes tonight with a second Groq proposer model that has its own daily quota (e.g. gpt-oss-20b, same family and prompt), after a 1-token check and reading its limits; the manifest records two proposer models. Reruns of the 18 done episodes are free from the cache.
  (b) Wait for gpt-oss-120b's quota. Whether Groq's daily window is rolling or resets at a fixed time is unverified, so it may not free up before the deadline, and 225k is still over one day's 200k.
  (c) Ship run A as a partial (18 episodes) and say so plainly; spend the remaining quota on run B (Gemini flash-lite proposer, gold episodes).
  (d) Groq Dev tier (paid) removes the cap: excluded by Harshit; note it in the doc as the scaling path.
- Recommendation: (a), then arcs on the full candidate set, then run B on flash-lite as planned.
- Reversible?: Yes.

## D-042: Run A's missing 32 episodes served by gpt-oss-20b on Groq (OpenRouter fallback failed)
- Date: 2026-11-08 · Owner: Claude (proposed) · Status: Proposed
- Context: Harshit chose (D-041) to finish run A with the same model on another host, openrouter/openai/gpt-oss-120b:free, and, if that failed, to fall back to groq/openai/gpt-oss-20b. The OpenRouter 1-token call returned HTTP 401 "User not found" with a fresh, well-formed key (the /models endpoint accepted it; /key and chat did not), so the account side could not be fixed from here. Groq gpt-oss-20b answered a 1-token call (1000 requests/day, 8000 tokens/minute; Groq sends no daily-token header).
- Decision: episodes 1, 2, 4–16, 19, 24, 40 stay on gpt-oss-120b (cache); the other 32 use gpt-oss-20b, same prompts (proposer_v3), same settings, same run folder. New CLI/config: `--run-dir`, `--episode-proposer "EPISODES=MODEL"`; the manifest records `proposer_model_by_episode`.
- Alternatives: wait for the 120b daily quota (unverified window); ship 18 episodes only.
- Consequences: **one run uses two proposer sizes** (120b and 20b), so quality may differ between episode groups; this is a stated limitation, not hidden. The judge is one model (qwen) for all clips, as required. The model-swap path (per-episode model, any api_base) is exercised.
- Reversible?: Yes: rerun with `--episode-proposer` removed once 120b quota is back (the 20b results stay cached).
- Qwen's remaining daily tokens could not be read from headers (none exist), so the "enough tokens" check was replaced by running the judge and stopping on a 429.

## D-043: CP-3 reviewer items left unfixed (limitations)
- Date: 2026-11-08 · Owner: Claude (proposed) · Status: Proposed
- Decision (Harshit, 2026-11-08): fix only item (1) (the `arc_` prefix, commit c1dbcf6). Not fixed, listed as limitations: duplicate arc picks not deduped; a crash outside the per-episode/batch handlers leaves no manifest; mock test lacks arcs_raw.json / arc-row / keep-going cases; the judge excerpt drops a dialogue line already playing at a single's start; the lowered max_tokens is not reused on the JSON-repair retry; plus the nits in the CP-3 report entry.
- Reversible?: Yes.
