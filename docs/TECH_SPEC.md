# Technical spec: Kuku Promo Finder

Read with PRD.md. If something isn't specified here, make a sensible choice and log it in decisions.md as `Proposed`.

---

## 1. Architecture

```
input pack (folder or .zip of episode .txt)
   │
   ▼
[1] parse.py ──────────► episodes.json            (code only)
      + aliases.py (config/aliases.yaml)
   │
   ▼
[2] propose.py ────────► proposals_raw/*.json     (LLM: "proposer" stage, 1 call per episode)
   │                      returns BLOCK IDs only
   ▼
[3] build.py ──────────► candidates.json          (code: IDs→times, snap, validate, jump-cut, dedupe)
   │
   ├─[2b] arcs.py ─────► arcs_raw.json            (LLM: "arc" stage, 1–2 calls per show)
   │        └─ build.py validates arc segments ─► merged into candidates.json
   ▼
[4] judge.py ──────────► judge_raw/*.json, scored.json   (LLM: "judge" stage, batched)
   │
   ▼
[5] rank.py ───────────► ranked.json              (code: weighted score + bonuses + diversity)
   │
   ▼
[6] report.py ─────────► promos.csv, promos.json, review.md, manifest.json
   │
   ▼
[7] evaluate.py ───────► eval_report.md, eval_metrics.json   (vs gold/gold_labels.csv)
```

**Division of labour:** the LLM makes judgement calls (which moment is a hook or cliff, how good it is). Code handles everything checkable or numeric: timestamps, durations, snapping, dedupe, ranking arithmetic, validation, evaluation. A human makes the final pick and trim.

## 2. Repo layout
```
kuku-promo-finder/
├── CLAUDE.md  README.md  report.md  decisions.md  ai_log.md
├── requirements.txt             # exactly the §9 packages, pinned (D-014)
├── config.yaml                  # models per stage, weights, thresholds (no secrets)
├── config/aliases.yaml          # speaker alias map, show-specific (GIT-IGNORED)
├── config/aliases.example.yaml  # synthetic show's aliases (committed, documents the format)
├── scripts/leak_check.py        # pre-push confidentiality check
├── private/                     # GIT-IGNORED: INPUT_PACK_NOTES.md, EXPLANATION.md, interview notes
├── .env.example                 # GEMINI_API_KEY=, GROQ_API_KEY=, OPENAI_API_KEY=, ...
├── run.py                       # CLI entry point
├── evaluate.py                  # eval CLI
├── app.py                       # Streamlit app
├── promo_finder/
│   ├── __init__.py
│   ├── config.py   parse.py   aliases.py   compact.py
│   ├── llm.py      cache.py   propose.py   arcs.py
│   ├── build.py    judge.py   rank.py      report.py
│   ├── metrics.py               # IoU, matching, precision/recall (used by evaluate.py)
│   ├── mock.py                  # canned LLM responses for --mock
│   └── prompts/ proposer.md  arc.md  judge.md
├── samples/synthetic_show/      # 3 fictional episodes in the same format (we write these)
├── tests/                       # pytest
├── gold/ gold_labels.csv  precision_ratings.csv   (CSVs GIT-IGNORED)  ad_observations.md (committed, public ads only)
├── docs/ ...
├── input/      (git-ignored)    # Kuku pack goes here
└── outputs/    (git-ignored)    # runs go here
```

## 3. Parsing (`parse.py`)

### 3.1 Input format (observed in the pack)
```
EPISODE NUMBER: Episode 1
EPISODE LOGLINE: ...
CONTINUITY NOTES: ...
--- SCRIPT START ---
SCENE 01
Scene heading: INT. OLD HOUSE – DAY          (ep 6 uses "SCENE HEADING:" in capitals)
Scene start: 00:00.00
Scene end: 02:18.00
Actions and dialogue:
**CAMERA:**
Start: (00:00.00) | End: (00:04.80)
<text, may span lines until the next blank line or ** header>
**MARA (Confused, Breathless):**
Start: (00:13.50) | End: (00:14.30)
"Why?"
**SOUND FX:** / **ACTION:** ...
--- SCRIPT END ---
```
Filename: `episode-001-Episode <id>.txt`. Take the episode number from the `EPISODE NUMBER` header, falling back to the filename.

### 3.2 Rules
- All header keys are **case-insensitive** and whitespace-tolerant.
- Block header regex (roughly): `^\*\*(?P<label>[^*]+?):\*\*\s*$`.
  - `label` ∈ {CAMERA, ACTION, SOUND FX} → `type` = that value. Anything else is `DIALOGUE`.
  - Dialogue label: `SPEAKER (Emotion, Emotion)` or `SPEAKER (O.S.) (Emotion)`. Split into `speaker_raw`, `emotion`, and flags like `O.S.`/`V.O.`.
- Time regex: `Start:\s*\((\d+):(\d+(?:\.\d+)?)\)\s*\|\s*End:\s*\((\d+):(\d+(?:\.\d+)?)\)`. Also accept `HH:MM:SS.ss` and 1–3 decimals, convert to float seconds, and **test these variants**.
- Text = the lines after the time line until the next block header, scene header or blank-line gap. Strip surrounding quotes from dialogue text.
- Block ID: `E{ep:02d}-B{n:03d}`, numbered in file order within the episode.
- Episode duration = max(block end, last scene end).
- **Validation warnings** (logged, never fatal): end < start; block outside its scene's range; missing times; episode with zero dialogue.

### 3.3 Data model (Pydantic)
```python
class Block(BaseModel):
    id: str            # "E01-B037"
    ep: int
    scene: int
    type: Literal["CAMERA","ACTION","SOUND_FX","DIALOGUE"]
    speaker_raw: str | None
    speaker: str | None   # canonical, after aliases
    emotion: str | None
    start: float          # seconds from episode start
    end: float
    text: str

class Scene(BaseModel):
    ep: int; num: int; heading: str; start: float; end: float

class Episode(BaseModel):
    ep: int; source_file: str; logline: str; continuity: str
    duration: float; scenes: list[Scene]; blocks: list[Block]
```

### 3.4 Aliases (`aliases.py`, `config/aliases.yaml`)
- Map uppercase raw speaker to canonical name. Unknown names keep their raw value, title-cased.
- The **show-specific** file is built in T1.3. Claude drafts it from the unique speakers plus loglines, and **Harshit verifies it at CP-1**. LLM-drafted maps are a known error source, so log any mistakes in ai_log.md.
- Aliases make prompts clearer. **Never hard-code show-specific logic in Python.**

## 4. Pipeline stages

### 4.1 Compact view (`compact.py`)
This is the text the LLM sees, one line per block:
```
[E01-B036 00:36.5–00:39.0] CAM: Close-up on the envelope as Mara tears it open.
[E01-B037 00:39.1–00:41.2] MARA (Stunned): "This says the house was never ours."
[E01-B038 00:39.0–00:41.5] ACT: ...
[SFX]  ...
```
- Include all types: visual hooks live in CAM/ACT.
- Show times so the model can reason about duration, but the **output schema only allows IDs**.
- Header lines: episode number, logline, continuity notes, duration, a canonical cast list with one-line roles (from aliases.yaml, optional).
- Measure tokens per episode (`len(text)/4` estimate, or `litellm.token_counter`) and log them.

### 4.2 Proposer (`propose.py`, prompt `prompts/proposer.md`)
- One call per episode. Episodes are independent, so run them with a small thread pool (concurrency set in config) and respect rate limits.
- Prompt contents: what a microdrama promo is (the brief's definition, verbatim); the 3 rules (hook ≤ 3 s, unresolved cliff, standalone); target 20–60 s, ideally 30–45 s; **3 hook patterns from `gold/ad_observations.md`**; instructions to propose 2–4 candidates **or zero** if nothing is promo-worthy; return block IDs only.
- **Do not put gold-set answers in the prompt**, since that would leak into eval. Use the synthetic show for examples.
- Output schema:
```json
{"episode": 1,
 "candidates": [
   {"start_block": "E01-B021", "hook_block": "E01-B023", "cliff_block": "E01-B061",
    "end_block": "E01-B062", "beat_type": "betrayal_reveal",
    "hook_summary": "...", "cliff_summary": "...", "reasoning": "..."}]}
```
- `beat_type` enum: slap_or_violence, humiliation, betrayal_reveal, identity_reveal, threat_ultimatum, rescue, proposal_or_romance, accusation_or_framing, death_or_danger, twist, other.
- Validation: every ID must exist in that episode and be ordered `start ≤ hook ≤ cliff ≤ end`. Otherwise retry once with the error message appended, then drop the candidate and log it.

### 4.3 Builder (`build.py`): pure code, fully unit-tested
Input: proposals + parsed episodes. Output: `Candidate` objects.

1. **IDs → times.** `t_hook = block[hook].start`, `t_cliff_end = block[cliff].end`.
2. **Snap start:** choose the CAMERA block start in `[t_hook − 2.5, t_hook]` closest to `t_hook − 1.0`, which gives a beat of lead-in. If there is none, use the start of the CAMERA shot containing `t_hook`. If that is more than 3.0 s before `t_hook`, start at `t_hook` and add the flag `midshot_start`. Constraint: `hook_offset = t_hook − start ≤ 3.0`.
3. **Snap end:** the end of the CAMERA shot that contains `t_cliff_end`. If any DIALOGUE block *starts* in `(t_cliff_end, snapped_end]`, use `end = t_cliff_end` and add the flag `midshot_end`. This prevents leaking a resolving line.
4. **Duration rules** (`d = end − start`):
   - `20 ≤ d ≤ 60` → type `single`.
   - `d > 60` → **jump-cut**. Segment 1 = `[start, s1_end]`: s1_end = the first shot boundary ≥ max(hook_end, start + 12 s). If there isn't one at or before start + 25 s, use the last shot boundary in [hook_end, start + 25 s]; if there isn't one of those either, use hook_end and add the flag `midshot_s1`. Segment 2 = `[s2_start, end]`: s2_start = the earliest CAMERA shot start that is after s1_end, keeps the total ≤ 55 s, and doesn't land inside a DIALOGUE block (if one spans it, move to the next shot start). s2_start must be ≤ the cliff block's start (s2 contains the whole cliff line); otherwise reject with reason `cliff_segment_too_long`. Type `jumpcut`, flag `trimmed`. Worked example with exact numbers: PROCESS_GUIDE Process 3 (D-015).
   - `d < 20` → try extending `end` forward by whole shots while no new DIALOGUE starts (max +8 s). Otherwise try moving `start` back by whole shots, only if the hook stays within 3 s (usually impossible). Otherwise mark `too_short` and drop, but keep it in `rejected.json` with the reason.
5. **Dedupe:** within an episode, if the temporal IoU of two candidates' union intervals is > 0.5, keep the one the proposer listed first. The judge rescores later; record merges.
6. **Validity checks** (each recorded as a boolean on the candidate): `dur_ok`, `hook_within_3s`, `starts_on_shot`, `ends_on_shot`, `no_dialogue_after_cliff`, `segments_ordered`.
7. Candidate ID: `P{ep:02d}-{k}` for single/jumpcut, `ARC-{k}` for arcs.

### 4.4 Arc promos (`arcs.py`, prompt `prompts/arc.md`)
- Input: all episode loglines, plus each episode's proposer candidates (ID, beat_type, hook/cliff summaries, block IDs).
- Ask for 3–8 cross-episode promos: 2–3 segments from different episodes, in order. The first segment carries the hook (often a payoff moment as a cold open, or an early humiliation as setup), and the last carries a cliff. Each segment is given as `{episode, start_block, end_block}`.
- Code: snap each segment to shots, require each segment ≥ 4 s, total 20–60 s, and hook_within_3s on segment 1. Invalid arcs are rejected with a reason.
- Classic pattern to allow: *early-episode humiliation → late-episode hidden-identity reveal*. Don't hard-code it; it should appear in the eval naturally.

### 4.5 Judge (`judge.py`, prompt `prompts/judge.md`)
- Batch 3–5 candidates per call. Each candidate is shown as its **exact excerpt** (compact lines of each segment, with a `--- CUT ---` marker between segments), plus the episode logline for context, clearly labelled "editor context, viewer does NOT see this".
- The rubric is 1–5 each, with written anchors in the prompt:
  - `hook`: would a scrolling stranger stop in the first 3 s?
  - `cliff`: does it cut on an unresolved question?
  - `standalone`: does it make sense with zero context?
  - `trope_pull`: is the trope strong for a US microdrama audience (revenge, hidden identity, betrayal, rescue)?
  - `pacing`: no dead air, escalation.
- Also return: `hook_text` (the line or action that hooks), `cliff_text`, `why` (one line, ≤ 25 words), `risk_flags` ⊂ {needs_context, cliff_may_resolve, graphic_violence, slow_middle, confusing_cut}.
- **Reasons before scores** in the schema (the field order makes the model reason first).
- Use a **different model family** from the proposer when available (config `judge.model`) to reduce self-preference bias. Log which one was used.

### 4.6 Ranker (`rank.py`): code
```
base = 0.35*hook + 0.30*cliff + 0.20*standalone + 0.10*trope_pull + 0.05*pacing   # scores normalised to 0–1
bonus:  episode ≤ 5: +0.06 · 6–15: +0.03 · duration 30–45 s: +0.03 · type arc: +0.02
penalty: each of midshot_start/midshot_end: −0.03 · needs_context: −0.05 · cliff_may_resolve: −0.05
final = base + bonus − penalty
```
- All weights live in `config.yaml`. Changing a weight means a decision entry.
- **Diversity pass** on the top 20: at most 2 per episode, and at most 1 per scene in the top 10. A promo's scene = the scene of its hook block. An arc counts under its segment-1 episode and scene for these caps; its episode bonus uses its earliest episode (logged at T4.3). When a promo is skipped, the next one moves up. Record any skipped promos.
- `posting_rationale` per promo is a short code-generated sentence built from the scores and flags. If `config.rank.llm_rationale: true`, one extra LLM call writes a 5-line "what to post first and why" for the top 10.

## 5. LLM layer (`llm.py`, `cache.py`)
- Use **LiteLLM** `completion()` with `response_format=<PydanticModel>` when `litellm.supports_response_schema(model)`. Otherwise use JSON mode or a plain prompt plus `model_validate_json` with JSON extraction. Set `litellm.enable_json_schema_validation = True` where useful.
- Signature: `call_llm(stage: str, messages: list, schema: type[BaseModel]) -> BaseModel`. The stage name selects its model config.
- Config per stage (in `config.yaml`):
```yaml
models:
  proposer: {model: "gemini/<current-flash-model-id>", api_base: null, api_key_env: GEMINI_API_KEY, temperature: 0, max_tokens: 4000,
             reasoning_effort: low}   # optional; null = provider default; part of the cache key (D-027)
  arc:      {model: "gemini/<current-flash-model-id>", ...}
  judge:    {model: "groq/<current-free-model-id>", api_key_env: GROQ_API_KEY, ...}
concurrency: 2
rate_limit: {rpm: 10}
```
- **Don't hard-code model IDs.** At T3.1, look up the current free-tier model IDs (Google AI Studio and the Groq console change often) and verify each with a 1-token test call. Record them in decisions.md.
- CLI overrides: `--model X` (all stages), `--proposer-model`, `--judge-model`, `--api-base URL`, `--api-key-env NAME`. That is enough to plug in Kuku's endpoint, for example `--model openai/<their-model> --api-base https://... --api-key-env KUKU_KEY`.
- **Retries:** exponential backoff on 429 and 5xx (max 5). On JSON validation failure, retry once with the error appended.
- **Cache:** `.cache/llm/<sha256(model|prompt_version|messages)>.json` stores the raw response plus usage. A cache hit costs nothing. `--no-cache` disables it.
- **Usage accounting:** record per call the stage, model, prompt and completion tokens, latency and cache hit. Aggregate per stage into the run manifest. Cost = tokens × price, from an editable `config.yaml: prices` table, where free models are listed at $0 and also priced at a reference paid model for the scale estimate.
- **Mock mode** (`--mock`): `mock.py` returns deterministic canned JSON built from the parsed blocks (for example, the first strong dialogue line as hook and the last line as cliff). Used by tests and the demo when no key is available.

## 6. Prompts
- Files in `promo_finder/prompts/`, each starting with `<!-- version: proposer_v1 -->`. The version goes into the cache key and the manifest.
- Keep prompts short and concrete. Include the brief's definition of a promo verbatim.
- Include ≤ 2 worked examples, taken from the **synthetic show** (never from gold labels).
- Changing a prompt means bumping the version and adding a line to report.md with the reason and a before/after on 3 episodes.

## 7. Outputs (`outputs/<run_id>/`, run_id = `YYYYMMDD-HHMM-<run-name>`)
| File | Content |
|---|---|
| `manifest.json` | run id, timestamp, git commit, config snapshot (no keys), models per stage, prompt versions, episodes parsed, counts, tokens, time and estimated cost per stage, errors |
| `episodes.json` | parsed data |
| `proposals_raw/E01.json …` | **unedited** raw LLM responses |
| `arcs_raw.json`, `judge_raw/batch_*.json` | unedited raw responses |
| `candidates.json`, `rejected.json` | built candidates and rejected ones with reasons |
| `scored.json`, `ranked.json` | after judge and ranker |
| `promos.csv` | rank, promo_id, type, total_sec, segments (`E01 00:11.0–00:41.5; E42 …`), hook_text, cliff_text, why, scores, final_score, flags |
| `promos.json` | same, structured: `segments: [{episode, start, end, start_tc, end_tc, start_block, end_block}]` |
| `review.md` | editor-facing: posting-order rationale, then per promo the rank, timestamps, hook → cliff, why, flags and the script excerpt |
| `run.log` | full log |
| `eval_report.md`, `eval_metrics.json` | written by evaluate.py |

Timecodes are shown as `MM:SS.s` relative to episode start.

## 8. Streamlit app (`app.py`)
- Upload a zip or several .txt files, or use the **synthetic sample** button.
- Sidebar: model per stage (text input with defaults from config), optional API base, API key input (password field; otherwise `st.secrets`), and a mock toggle.
- Run with a progress bar per stage. Then show a ranked table (filter by type and flags) and expandable rows with excerpts. Downloads: CSV, JSON, review.md.
- **Never ship Kuku data with the app.** Uploaded files live only in a temp dir for the session.
- Deploy to Streamlit Community Cloud from the public GitHub repo. The free key goes in app secrets, with a note that the quota may run out (the mock toggle still works).

## 9. Dependencies (ask before adding others)
`python>=3.11`, `litellm`, `pydantic>=2`, `pyyaml`, `python-dotenv`, `pandas`, `streamlit`, `pytest`, `tenacity` (optional, for retries). The standard library covers the rest (re, json, hashlib, zipfile, concurrent.futures, logging, pathlib).

## 10. Testing (`tests/`)
- `test_parser.py`: the synthetic show parses to exact expected counts and times; ep-6-style capitalised headers; `(O.S.)` speakers; multi-line text.
- `test_parser_variants.py`: HH:MM:SS timestamps, 1–3 decimals, missing SOUND FX, CRLF line endings, extra blank lines, unknown block labels (become DIALOGUE with a warning). **This is what protects the live interview run on a new pack.**
- `test_build.py`: snapping, hook ≤ 3 s, no dialogue after cliff, jump-cut construction, too-short handling, dedupe IoU.
- `test_rank.py`: weights, bonuses, diversity constraint.
- `test_metrics.py`: IoU on single and multi-segment, matching, precision/recall.
- `test_pipeline_mock.py`: full run on the synthetic show with `--mock` produces all output files with a valid schema.
- Real-API tests are **not** in pytest. They are manual smoke runs logged in report.md.

## 11. Security and confidentiality
- The repo is public, so show-derived material goes only in git-ignored paths. `.gitignore` covers `input/`, `outputs/`, `private/`, `.cache/`, `config/aliases.yaml`, `gold/*.csv`, `.env`, `*.zip`, `.streamlit/secrets.toml`.
- Commit `config/aliases.example.yaml`, which holds the synthetic show's aliases, so the format is documented. If `config/aliases.yaml` is missing, the pipeline uses no aliases (raw names, title-cased) and logs a warning. This keeps it working on a brand-new pack in the interview.
- Never log API keys. The manifest stores the env var *name*, not its value.
- **Leak check** (`scripts/leak_check.py`, run before every commit that touches public logs and before every push): read the canonical and raw names from `config/aliases.yaml`, the show keywords in `private/leak_keywords.txt` (title words, places, props, scene types), plus 20 random dialogue lines from `input/`. Default mode scans the working tree and staged blobs; `--pre-push` also scans every commit (added lines) and commit message on all branches (D-020). Grep all git-tracked files for them, and fail on any hit.
