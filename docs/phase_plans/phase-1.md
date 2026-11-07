# Phase 1: Parser and data — Implementation Plan

> **For agentic workers:** Execute natively, task by task (Harshit's kickoff instructions). Steps use `- [ ]` checkboxes.

**Goal:** Turn any episode-script pack (folder or zip) into validated `Episode`/`Block` data with stable block IDs, plus a compact one-line-per-block view for the LLM.
**Architecture:** `parse.py` (Pydantic models + tolerant line-based parser + pack loader + stats CLI) → `aliases.py` (raw speaker → canonical) → `compact.py` (LLM view + token estimate + CLI). Pure code, no LLM.
**Tech stack:** Python 3.11+ (venv 3.13), pydantic 2, PyYAML, pytest.
**Spec:** `docs/TECH_SPEC.md` §3, §4.1, §10, §11; `docs/PLAN.md` Phase 1.

## Global constraints
- Only TECH_SPEC §9 dependencies. Plain functions, module docstring of 3–5 lines, comments explain why.
- Block ID `E{ep:02d}-B{n:03d}`, numbered in file order within the episode.
- Public files (this plan, report.md, decisions.md, ai_log.md, tests, samples) hold no show text, names or plot. Real-pack details go to `private/parse_stats_T1.3.md`.
- Never hard-code show-specific logic in Python; aliases live in `config/aliases.yaml` (git-ignored), with `config/aliases.example.yaml` documenting the format using the synthetic show.

## Review focus (inputs the spec implies but could bite)
1. Speaker flags inside the emotion parens, e.g. `(Harsh, O.S.)`, `(O.S. / Low, Threatening)` → flag extracted, emotion keeps the rest. Test in T1.2.
2. Block with no time line → skipped with a warning, IDs stay contiguous. Test in T1.2.
3. `Scene start/end` on one line or on separate lines, any casing. Test in T1.2.
4. Zip input with a nested folder, and files that don't sort numerically by name → ordered by episode number. Test in T1.2.
5. Missing `config/aliases.yaml` → raw names title-cased, one warning, no crash. Test in T1.3.

---

### Task T1.1: Synthetic show
**Files:** Create `samples/synthetic_show/episode-001-Episode 9001.txt`, `…-002-Episode 9002.txt`, `…-003-Episode 9003.txt`, `samples/synthetic_show/README.md`, `config/aliases.example.yaml`.
- Fictional show "The Locket" (Mara, aunt Vera, stranger Ellis) as in PROCESS_GUIDE.
- Ep 1: lower-case-style headers, a two-line ACTION text, an `(O.S.)` speaker, a flag inside emotion parens, speaker first credited as `THE STRANGER`.
- Ep 2: capitalised `SCENE HEADING:/SCENE START:/SCENE END:`, a scene with no SOUND FX.
- Ep 3: reproduces PROCESS_GUIDE Process 1–3 exactly: `E03-B010` CAMERA 12.0–15.5, `E03-B011` MARA 13.0–14.8 "You sold the house?", `E03-B029` CAMERA 42.5–47.0, `E03-B030` ELLIS 44.0–46.2, `E03-B031` VERA 47.4–49.0; no other CAMERA starts in [10.5, 13.0].
- [ ] Write files → [ ] leak check passes → [ ] commit `T1.1: synthetic show`.

### Task T1.2: Parser + tests (TDD)
**Files:** Create `promo_finder/__init__.py`, `promo_finder/parse.py`, `tests/test_parser.py`, `tests/test_parser_variants.py`, `tests/conftest.py`; `requirements.txt` already exists (D-014).
**Interfaces (produced):**
- Models `Block(id, ep, scene, type, speaker_raw, speaker, emotion, flags: list[str], start, end, text)`, `Scene(ep, num, heading, start, end)`, `Episode(ep, source_file, logline, continuity, duration, scenes, blocks)`.
- `parse_time(s: str) -> float` — `MM:SS(.d{1,3})` or `HH:MM:SS(.d{1,3})`.
- `parse_speaker_label(label: str) -> tuple[str, str | None, list[str]]` → (speaker_raw, emotion, flags); flags ⊂ {O.S., V.O., O.C., CONT'D}.
- `parse_episode_text(text: str, source_file: str, aliases: dict[str, str] | None = None) -> tuple[Episode, list[str]]` (episode, warnings).
- `load_pack(path: Path, aliases: dict[str, str] | None = None) -> tuple[list[Episode], list[str]]` — folder or `.zip`, recursive `*.txt`, sorted by episode number.
- CLI `python -m promo_finder.parse --input <pack> [--out episodes.json]` prints the stats summary.
**Tests (synthetic show):** 3 episodes; exact block counts per type per episode; `E03-B011` = (13.0, 14.8, DIALOGUE, "MARA", "Stunned, Quiet", "You sold the house?"); ep 2 capitalised headers give its scene times; `(O.S.)` → flag; flag inside emotion parens; multi-line text joined with a space; duration = max(block end, last scene end).
**Variant tests (built by mutating the synthetic text):** HH:MM:SS times; 1, 2, 3 decimals; CRLF; extra blank lines; no SOUND FX; unknown label (`**TITLE CARD:**`, unquoted text) → DIALOGUE + warning; missing time line → skipped + warning; end < start → warning; block outside scene → warning; episode number from filename when header missing; zip input.
- [ ] Failing tests → [ ] run, see fail → [ ] implement → [ ] `pytest -q` green → [ ] log D-018 (parser choices) → [ ] commit `T1.2: parser + tests`.

### Task T1.3: Real pack stats + alias draft
**Files:** Create `promo_finder/aliases.py`, `tests/test_aliases.py`; private outputs `private/parse_stats_T1.3.md`, `config/aliases.yaml` (both git-ignored).
**Interfaces:** `load_aliases(path: Path | None) -> tuple[dict[str, str], dict[str, str]]` (raw→canonical, cast name→role; missing file → empty + logged warning); `canonical_speaker(raw: str, aliases: dict[str, str]) -> str` (upper-case lookup, else title-case).
- [ ] Tests (lookup, title-case fallback, missing file) → [ ] implement → [ ] parse real pack → counts in report.md, speakers/warnings in private file → [ ] draft aliases.yaml → [ ] leak check → [ ] commit `T1.3: aliases + real-pack parse stats`.

### Task T1.4: Compact view + tokens
**Files:** Create `promo_finder/compact.py`, `tests/test_compact.py`.
**Interfaces:** `format_tc(seconds: float) -> str` (`MM:SS.s`); `compact_episode(ep: Episode, cast: dict[str, str] | None = None) -> str`; `estimate_tokens(text: str) -> int` (= `len(text) // 4`, D-019 if litellm counter not used). CLI `python -m promo_finder.compact --input <pack> --ep N` and `--tokens` (table for all episodes).
**Line format:** `[E03-B011 00:13.0–00:14.8] MARA (Stunned, Quiet): "You sold the house?"`; CAMERA→`CAM:`, ACTION→`ACT:`, SOUND_FX→`SFX:`. Header lines: episode, logline, continuity, duration, optional cast.
- [ ] Tests (exact line for E03-B011 and E03-B010; header present; tokens > 0) → [ ] implement → [ ] token table (counts only) in report.md → [ ] commit `T1.4: compact view + token table`.

### CP-1
- [ ] `/checkpoint CP-1` (independent-reviewer on the phase diff), then stop for Harshit.
