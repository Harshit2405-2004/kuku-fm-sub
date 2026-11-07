# Phase 3: LLM layer, builder, proposer — Implementation Plan

> Execute natively, task by task (Harshit's instructions). T3.5 (smoke test) waits for "Gold labels done".

**Goal:** One swappable, cached, validated LLM call path; a pure-code cut builder; proposer prompt v1 + stage, runnable end to end in mock mode.
**Architecture:** `config.py` (YAML + CLI overrides) → `cache.py` (disk cache) → `llm.py` (`call_llm`, retries, JSON repair, usage) ← `mock.py` (no-API responses). `build.py` turns block IDs into validated cuts (TECH_SPEC §4.3, D-015). `propose.py` + `prompts/proposer.md` produce candidates as IDs only.
**Spec:** TECH_SPEC §4.2, §4.3, §5, §6; PROCESS_GUIDE Process 3; decisions D-002, D-005, D-011, D-015, D-022.

## Global constraints
- No model IDs in Python; models only from config/flags (hard rule 2). Temperature 0; every call cached by (model, prompt version, messages, schema) (hard rule 8).
- The LLM never returns times (hard rule 1): schemas contain block IDs only.
- Prompt examples come from the synthetic show only; no gold content.

## Review focus
1. An OpenAI-compatible endpoint that rejects `response_format` → retry without it, then validate JSON from text. Test in T3.2.
2. A model that wraps JSON in ``` fences or adds prose → extract the JSON object. Test in T3.2.
3. The API key value never appears in usage records, cache files or the manifest (only the env var name). Test in T3.2.
4. Proposer returns an ID from another episode, or out of order → one repair retry, then the candidate is dropped and logged. Test in T3.4.
5. Snapping when blocks are not time-ordered in the file (synthetic ep 3 has one) → snapping searches by time, not file order. Test in T3.3.

### T3.2: config + cache + llm + mock
**Files:** `promo_finder/{config,cache,llm,mock}.py`, `tests/test_llm.py`, `tests/test_config.py`.
**Interfaces:** `load_config(path) -> dict`; `apply_overrides(cfg, model=None, proposer_model=None, arc_model=None, judge_model=None, api_base=None, api_key_env=None, no_cache=False, mock=False) -> dict` (api_base/api_key_env go to the stages whose model was overridden, or to all stages if none was); `cache_key(model, prompt_version, messages, schema_name) -> str`; `call_llm(stage, messages, schema, cfg, prompt_version, usage, completion_fn=None, sleep=time.sleep) -> tuple[BaseModel, str]` (parsed, raw text); `summarize_usage(usage) -> dict`.
**Tests:** cache hit skips the call; prompt-version change misses; invalid JSON → one repair retry with the error appended; twice invalid → `LLMOutputError`; 429 ×2 → backoff sleeps 2, 4; persistent 429 → raises after max_attempts; fenced JSON; api_base + key from env var name, key value absent from records; response_format rejected → retry without; overrides rules.

### T3.3: build.py (TDD, PROCESS_GUIDE Process 3 numbers)
**Interfaces:** `snap_start(ep, t_hook, cfg) -> tuple[float, list[str]]`; `snap_end(ep, t_cliff_end) -> tuple[float, list[str]]`; `build_candidate(ep, proposal, k, cfg) -> Candidate | Rejected`; `dedupe(cands, iou) -> tuple[list, list]`; `interval_iou(a, b) -> float`. Model `Candidate(id, ep, type, segments: list[Segment], hook_block, cliff_block, start_block, end_block, beat_type, hook_summary, cliff_summary, reasoning, flags, checks: dict[str,bool], hook_offset_s, total_s)`.
**Tests:** synthetic ep 3 → start 12.0, hook offset 1.0, end 47.0, 35.0 s single; jump-cut fixture → [4.0–19.5] + [62.0–98.5] = 52 s; too-short fixture → extended to 38.5 then rejected; dialogue inside (cliff_end, shot_end] → end = cliff_end + `midshot_end`; no shot near the hook → `midshot_start`; tie → earlier shot (D-023 at T3.3); dedupe IoU > 0.5 keeps the first; `cliff_segment_too_long` rejection; validity flags.

### T3.4: proposer prompt v1 + propose.py
**Interfaces:** `ProposalCandidate`, `EpisodeProposals` (Pydantic, IDs only, beat_type enum); `build_messages(ep, cast, prompt) -> list[dict]`; `validate_proposals(ep, proposals) -> list[str]` (errors); `propose_episode(ep, cast, cfg, usage, raw_dir) -> EpisodeProposals`. `mock.py` returns valid proposals built from the compact lines in the message.
**Tests:** validation catches unknown ID / wrong episode / bad order; repair retry path; mock pipeline proposes ≥ 1 valid candidate per synthetic episode and `build.py` turns it into a valid cut; raw response saved unedited.
