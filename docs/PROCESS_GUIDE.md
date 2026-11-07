# Process guide: how everything works, step by step

This guide explains **every process** in the project in plain language, using one small worked example that runs all the way through. The example uses a **made-up show** ("The Locket": Mara, her aunt Vera, and a stranger called Ellis), never Kuku's script, so this file is safe in the public repo.

How the three explainer docs fit together:
- `INSTRUCTIONS.md`: *what to do, in what order*
- **this file**: *what actually happens* in each process
- `private/EXPLANATION.md`: *why* we chose each design

---

## The big picture

```
 ┌──────────────┐   ┌─────────────┐   ┌──────────────┐   ┌────────────┐   ┌──────────┐   ┌─────────┐
 │ 1 PARSE      │──►│ 2 PROPOSE   │──►│ 3 BUILD CUTS │──►│ 5 JUDGE    │──►│ 6 RANK   │──►│ 7 OUTPUT│
 │ text → blocks│   │ LLM picks   │   │ code: IDs →  │   │ 2nd LLM    │   │ code:    │   │ CSV +   │
 │ with IDs     │   │ moments (IDs)│   │ times, snap, │   │ scores 1–5 │   │ formula +│   │ review  │
 └──────────────┘   └─────────────┘   │ validate     │   └────────────┘   │ diversity│   └────┬────┘
        code            AI           └──────▲───────┘        AI           └──────────┘        │
                    ┌─────────────┐          │                                code             ▼
                    │ 4 ARCS      │──────────┘                                           ┌──────────┐
                    │ LLM links   │                                                      │ 8 EVALUATE│
                    │ episodes    │                                                      │ vs your  │
                    └─────────────┘                                                      │ gold set │
                         AI                                                              └──────────┘
```
The rule behind the whole design: **AI decides what's dramatic; code handles anything that can be checked or calculated; you make the final call.**

---

## Process 1: Parsing (script text → structured data)

**Input:** one episode file. This is a piece of our fictional Episode 3:
```
**CAMERA:**
Start: (00:12.00) | End: (00:15.50)
Close-up: Mara freezes at the door, an envelope in her hand.

**MARA (Stunned, Quiet):**
Start: (00:13.00) | End: (00:14.80)
"You sold the house?"
```
**What the parser does:**
1. Finds each `**LABEL:**` header. CAMERA, ACTION and SOUND FX are their own types; anything else is a speaker, so it's DIALOGUE.
2. Splits `MARA (Stunned, Quiet)` into speaker `MARA` and emotion `Stunned, Quiet`.
3. Reads `Start: (00:13.00) | End: (00:14.80)` and converts it to seconds: 13.0 and 14.8.
4. Gives each block an ID in file order: `E03-B010`, `E03-B011`, and so on.
5. Maps nicknames to one name using `config/aliases.yaml` (e.g. "THE STRANGER" → Ellis).

**Output (one block):**
```json
{"id": "E03-B011", "ep": 3, "scene": 1, "type": "DIALOGUE", "speaker": "Mara",
 "emotion": "Stunned, Quiet", "start": 13.0, "end": 14.8, "text": "You sold the house?"}
```
**Why it matters:** everything later depends on these IDs and times being right. That's why the parser has the most tests, including weird formats (capitalised headers, different timestamp styles, Windows line endings). In the interview Kuku gives you a *new* pack, and a crash here would sink the demo.

---

## Process 2: Proposing (the LLM picks moments, by ID)

**What the LLM sees:** a compact version of the episode, one line per block:
```
EPISODE 3 · logline: Mara learns her aunt sold the family house... · duration 01:52
[E03-B010 00:12.0–00:15.5] CAM: Close-up: Mara freezes at the door, an envelope in her hand.
[E03-B011 00:13.0–00:14.8] MARA (Stunned, Quiet): "You sold the house?"
[E03-B012 00:15.5–00:19.0] CAM: Vera turns, smiling coldly.
...
[E03-B029 00:42.5–00:47.0] CAM: Ellis steps out of the shadows.
[E03-B030 00:44.0–00:46.2] ELLIS (Low): "Then who signed the deed?"
[E03-B031 00:47.4–00:49.0] VERA (Pale): "...You."
```
**What the prompt asks:** "Find 2–4 promo moments (or zero). A promo opens on a hook in the first 3 s, ends on an unresolved moment, and makes sense to a stranger. Answer **only with block IDs**."

**What the LLM answers:**
```json
{"episode": 3, "candidates": [{
  "start_block": "E03-B010", "hook_block": "E03-B011",
  "cliff_block": "E03-B030", "end_block": "E03-B030",
  "beat_type": "betrayal_reveal",
  "hook_summary": "Mara discovers the house was sold",
  "cliff_summary": "stranger asks who signed the deed",
  "reasoning": "instant betrayal hook; ends on a question the viewer needs answered"}]}
```
Notice it **never writes a time**. It sees times, so it can judge length, but it may only point at IDs.

**Checks right away (code):** every ID must exist in Episode 3, and the order must be start ≤ hook ≤ cliff ≤ end. If not, we send the error back and ask once more. If it fails again, that candidate is dropped and logged.

---

## Process 3: Building cuts (code turns IDs into real clips)

This is pure code, deterministic and fully tested. Using the example above:

**Step 1: look up times.** Hook `E03-B011` starts at **13.0**. Cliff `E03-B030` ends at **46.2**.

**Step 2: snap the start to a shot.** Editors cut between camera shots. We look for a CAMERA shot starting between 13.0 − 2.5 = 10.5 and 13.0. Shot `E03-B010` starts at **12.0**, so the clip starts at 12.0.
Hook offset = 13.0 − 12.0 = **1.0 s**, which is ≤ 3 s ✓. The hook lands in the first 3 seconds.

**Step 3: snap the end to a shot.** The shot containing 46.2 is `E03-B029`, which ends at **47.0**. Does any dialogue *start* between 46.2 and 47.0? Vera's reply starts at 47.4, so no ✓. End = 47.0. We stop before "...You.", so the question stays unanswered. **That's the cliffhanger.**

**Step 4: check duration.** 47.0 − 12.0 = **35.0 s**. That's within 20–60 ✓ and in the 30–45 sweet spot ✓. Type: `single`.

**What if it's too long? (jump-cut).** Say the hook line runs 5.0–7.0 and the cliff line ends at 98.0: that's **93 s hook-to-cliff (94.5 s once snapped)**. The camera shots in this example start at 0.0, 4.0, 9.0, 14.0, 19.5, 30.0, 45.0, 58.0, 60.5, 62.0, 80.0 and 98.5 (each runs to the next), and a dialogue line runs 60.0–61.0.
- Start snaps to the shot at **4.0** (closest to hook − 1 s); end snaps to the end of the shot 80.0–98.5, so **98.5**.
- **Segment 1 end:** the first shot boundary ≥ max(hook end 7.0, start + 12 = 16.0) is **19.5**. It's within start + 25 = 29.0 ✓. (If there were none by start + 25, we'd use the last boundary between the hook end and start + 25; if none at all, the hook end itself, flagged `midshot_s1`.)
- **Segment 2 start:** segment 1 is 15.5 s, so segment 2 may be at most 55 − 15.5 = 39.5 s, i.e. start at ≥ 98.5 − 39.5 = 59.0. The earliest shot start ≥ 59.0 is 60.5, but the dialogue line 60.0–61.0 spans it (cutting there would chop a line), so we move to the next shot start, **62.0**.
- Result: **[4.0–19.5]** (the hook and its setup) + **[62.0–98.5]** (the build-up and cliff) = 15.5 + 36.5 = **52 s** ✓. The slow middle is cut out, which is what real promo editors do. Type: `jumpcut`. This exact case is a unit test in `tests/test_build.py`.

**What if it's too short?** Say start 19.0 and end 34.0: 15 s. Code tries adding whole shots at the end *only while nobody starts speaking* (so we don't leak the answer). The next shot (34.0–38.5) is silent, so end = 38.5, giving 19.5 s, still short. The shot after that has a line starting at 39.0, so we stop. The result is **rejected as too short** and saved in `rejected.json` with the reason. We never silently stretch a clip into a spoiler.

**Dedupe:** if two candidates from the same episode overlap by more than 50%, keep one.

**Validity flags saved on every clip:** `dur_ok`, `hook_within_3s`, `starts_on_shot`, `ends_on_shot`, `no_dialogue_after_cliff`.

---

## Process 4: Arc promos (stitching across episodes)

Some of the best promos join two episodes: *"they humiliated her…"* (episode 1) → *"…then the truth came out"* (episode 40).
1. The LLM sees **all loglines** plus each episode's best moments (from Process 2).
2. It proposes 3–8 arcs, each with 2–3 segments given as `{episode, start_block, end_block}`.
3. **Code** snaps each segment to shots and checks: every segment ≥ 4 s, total 20–60 s, hook in the first 3 s of segment 1.

Fictional example:
```
ARC-1:  E01 00:05.0–00:21.5  (Vera tears up Mara's letter in front of the family)
        E19 01:02.0–01:24.0  (Ellis reveals he owns the estate; Vera goes white)   total 38.5 s
```

---

## Process 5: Judging (a second LLM scores each clip)

**Why a second model:** a model grading its own picks tends to like them (self-preference bias). A different model family is a fairer judge.

**What the judge sees:** the exact clip text (with `--- CUT ---` between segments), plus the episode summary marked *"for the editor only; the viewer doesn't see this"*.

**What it returns (reasons first, then scores):**
```json
{"promo_id": "P03-1",
 "reasons": "Opens on a shocking line; ends on an unanswered question; a viewer can follow it, though who Ellis is stays unclear.",
 "hook": 5, "cliff": 4, "standalone": 3, "trope_pull": 5, "pacing": 4,
 "hook_text": "You sold the house?", "cliff_text": "Then who signed the deed?",
 "why": "Family betrayal plus a mysterious stranger, cut right before the answer.",
 "risk_flags": ["needs_context"]}
```

---

## Process 6: Ranking (a formula in code, not a vibe)

**Step 1: normalise each 1–5 score to 0–1** using (score − 1) / 4:
hook 5 → 1.00 · cliff 4 → 0.75 · standalone 3 → 0.50 · trope 5 → 1.00 · pacing 4 → 0.75

**Step 2: weighted base score**
```
0.35×1.00 + 0.30×0.75 + 0.20×0.50 + 0.10×1.00 + 0.05×0.75
= 0.350 + 0.225 + 0.100 + 0.100 + 0.0375 = 0.8125
```
**Step 3: bonuses and penalties**
- Episode 3 is in episodes 1–5: **+0.06** (early-episode promos send viewers to the start of the show)
- 35 s is in 30–45 s: **+0.03**
- Flag `needs_context`: **−0.05**

**Final = 0.8125 + 0.06 + 0.03 − 0.05 = 0.8525**

**Step 4: diversity.** Sort all clips by final score. In the top 20, allow at most 2 per episode; in the top 10, at most 1 per scene (the scene of the hook block). An arc promo counts under its segment-1 episode and scene, but its episode bonus uses its *earliest* episode, since that's where the viewer starts watching. Otherwise the top 10 could be the same scene five times, which is useless for A/B testing.

All weights live in `config.yaml`. They're sensible starting guesses, and in production they'd be learnt from real ad results.

---

## Process 7: Outputs (what the editor gets)

Everything for a run lands in `outputs/<run_id>/`. The key file is `promos.csv`, one row per promo:

| rank | promo_id | type | total_sec | segments | hook_text | cliff_text | why | final | flags |
|---|---|---|---|---|---|---|---|---|---|
| 1 | P03-1 | single | 35.0 | E03 00:12.0–00:47.0 | "You sold the house?" | "Then who signed the deed?" | Family betrayal + stranger, cut before the answer | 0.85 | needs_context |

There's also `review.md` (a readable version with the script excerpt for each promo and a "post these first" note), `promos.json` (the same data for code), `manifest.json` (which models and prompts were used, plus tokens, time and cost), and the **raw, unedited LLM responses**. Kuku asked for those.

---

## Process 8: Evaluation (proving it's good)

**Gold set:** your own hand-picked promos, written *before* you see the tool's output.

**Matching a tool clip to a gold clip: temporal IoU.**
Tool clip 12.0–47.0, your gold clip 10.0–40.0:
- overlap = 12.0 to 40.0 = **28 s**
- union = 10.0 to 47.0 = **37 s**
- IoU = 28 / 37 = **0.76**, which is ≥ 0.5, so it's a **match** ✓

**Recall:** you picked 15 gold promos and the tool matched 11, so recall = 11/15 = **73%**.
**Precision@10:** you rate the tool's top 15 blind (shuffled, no scores). Seven of its top 10 are "would post", so precision@10 = **7/10**.
**Judge vs you (Spearman ρ):** do the judge's scores rank clips in the same order as your ratings? Above 0.4 means the judge is useful. Low means it needs a human, and you report that honestly.
**Model agreement (Jaccard):** how many top-10 clips two different models share. It shows how much the result depends on the model.
**Failure gallery:** 3–5 concrete misses, each with its cause and a fix.

(These are illustrative numbers. Your doc uses only real ones from your runs.)

---

## Process 9: Swapping the model (the interview moment)

Every LLM call goes through a single function, `call_llm(stage, …)`, built on **LiteLLM**, a library that speaks to 100+ providers with one interface. Which model each stage uses comes from `config.yaml` or a flag:
```bash
# everything on Kuku's model, through their OpenAI-compatible endpoint
python run.py --input input/new_show --model openai/<their-model> --api-base https://<their-url>/v1 --api-key-env KUKU_API_KEY
# or upgrade only the judge
python run.py --input input/new_show --judge-model openai/<their-model> --api-base https://<their-url>/v1 --api-key-env KUKU_API_KEY
```
What happens inside: LiteLLM sends the same messages and schema to their server, we validate the JSON the same way, and everything after it (cuts, ranking, outputs) is unchanged because it's code. That's why the swap is safe.

---

## Process 10: How Claude Code works in this repo

**Life of one task** (e.g. T3.3, "build the cut builder"):
```
Claude reads CLAUDE.md + TECH_SPEC §4.3
   → superpowers:test-driven-development: writes failing tests (snapping, jump-cut, too-short)
   → writes build.py until the tests pass
   → superpowers:verification-before-completion: runs pytest, shows real output
   → appends a report.md entry (what, files, commands + results)
   → /log-decision for any choice the spec didn't make   (Status: Proposed)
   → ai_log.md if any AI got something wrong
   → git commit "T3.3: cut builder + tests"
```

**Life of one checkpoint** (e.g. CP-2):
```
Phase tasks done → /checkpoint
   → independent-reviewer subagent reads the diff with fresh eyes → fixes blocking issues
   → checkpoint summary written to report.md → Claude STOPS
You review → reply "approved, accept D-014, reject D-015 because…" or "changes: …"
   → Claude logs your calls in decisions.md → next phase
```

**What each piece is:**
| Piece | Plain-language meaning |
|---|---|
| `CLAUDE.md` | The rulebook Claude re-reads every turn |
| Skill | A saved procedure Claude can follow (e.g. "how to log a decision"). Plugins like superpowers add skills; we wrote 3 of our own. |
| Subagent | A separate Claude with a fresh context and a narrow job (review only). Good for unbiased checks. |
| Plugin | A bundle of skills, agents or tools you install (superpowers, code-review, …) |
| `/clear` + resume prompt | Wipes the conversation; Claude picks up again from report.md |

**Why all the logging:** Kuku asks how you used AI and where it went wrong. `report.md`, `decisions.md` and `ai_log.md` answer that with evidence, and they let you resume after any break.

---

## Process 11: Submission
```
real runs (A, B) → eval reports → Claude drafts doc → YOU rewrite (≤2 pages) → PDF on Drive
outputs/ (unedited) → Drive folder              repo + app → incognito test
video (≤3 min, your voice) → brief-auditor check → form from YOUR account → submit early
```

---

## Quick glossary
| Term | Meaning here |
|---|---|
| Block | One timestamped line of the script (a shot, an action, a sound or a line of dialogue) |
| Hook | The moment in the first 3 s that stops a scrolling viewer |
| Cliffhanger | The unresolved moment the clip ends on |
| Snap | Moving a cut to the nearest camera-shot boundary |
| Jump-cut promo | Two or more pieces of one episode, with the slow middle removed |
| Arc promo | Pieces from different episodes joined together |
| Gold set | Your hand-picked "correct" promos, used to test the tool |
| IoU | Overlap ÷ combined span of two clips; ≥ 0.5 counts as a match |
| Cache | Saved LLM answers, so re-running costs nothing |
| Manifest | The run's record: models, prompts, counts, tokens, time, cost |