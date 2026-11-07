# PRD: Kuku Promo Finder

**Owner:** Harshit · **Status:** v1 (take-home) · **Problem:** Kuku assignment, Problem 1

---

## 1. Problem
Today a Kuku editor **watches every episode and picks promo moments by hand, one show at a time**, and Kuku releases new shows every week. Kuku TV releases 150+ shows a month and is targeting about 1,000 (see RESEARCH.md §1).

Why it matters: in FY26 Kuku spent **₹1,105 Cr on marketing, 77.7% of all expenses**. Microdrama audiences are almost entirely acquired through paid ads, and the ads are promo clips cut from the show. Finding more and better hooks, faster, affects the largest cost line in the business. International revenue is still about 1%. This English, US-facing show belongs to the push into a market where ReelShort and DramaBox set the bar for promos.

Why it's hard (and why a naive "paste the script into ChatGPT" fails):
- **Timestamps:** LLMs invent or misread times, and a promo with wrong timestamps is useless to an editor.
- **Constraints conflict:** the hook must come in the first 3 seconds, yet the clip must make sense on its own. Starting on the hook removes the setup.
- **Cliff vs. resolution:** one line too many and the cliffhanger is resolved inside the clip.
- **Visual hooks:** a slap, an explosion or a strike live in ACTION/CAMERA lines, not dialogue.
- **Scale:** 50 episodes × ~75 blocks is too much to judge by eye per show, and too slow at 150+ shows a month.
- **Taste:** "best promo" is subjective. The real ground truth is ad performance (CTR, installs), which we don't have.

## 2. Users
- **Primary: performance-marketing video editor.** Needs a shortlist they can verify in minutes and cut directly in their NLE (video editor), with exact timestamps per segment.
- **Secondary: growth/UA manager.** Needs many varied hooks per show for A/B testing, plus a rough priority order.
- **Tertiary: content team.** A cheap signal on which scenes are "promo-able", which can feed back into writing.

## 3. Goals
| ID | Goal | Measure |
|---|---|---|
| G1 | Produce a usable ranked shortlist for a whole show automatically | 15–25 promos per show; 100% structurally valid |
| G2 | Find the moments a human editor would pick | Recall of Harshit's hand-labelled gold promos (temporal IoU ≥ 0.5) ≥ 70% target |
| G3 | The top of the list is good | Blind human precision@10 ("would post") ≥ 6/10 target |
| G4 | Cheap and fast enough for every show | Measured cost and time per 50-episode show; target < $1 at paid-API prices, < 15 min |
| G5 | Re-runnable on new shows and new models | One command or one upload; model swap is one flag; parser handles format variants |
| G6 | Honest about failure | Failure gallery with ≥ 3 concrete cases and causes |

Targets are our own bars, set before running. Report the actual numbers either way.

## 4. Non-goals
- Video editing, rendering, music, captions, overlays (excluded by the brief)
- Analysing the video itself. We work from scripts only (a future step, §10).
- Auto-posting. A human picks and trims.
- Predicting actual CTR. Without performance data we only *rank by proxy*.

## 5. User stories
1. *As an editor*, I upload a show's script pack and get a ranked table of promos with episode and segment timestamps, so I can jump straight to them in my timeline.
2. *As an editor*, for each promo I see the hook line, the cliff line and the script excerpt, so I can judge it in seconds without watching.
3. *As an editor*, I see risk flags (needs context, cliff may resolve, graphic violence, mid-shot cut), so I know which ones to double-check.
4. *As a UA manager*, I get varied promos (different episodes, scene types and promo types), so I can A/B test different hooks.
5. *As the AI Lab*, I can swap in a stronger model for any stage without code changes, and compare runs.
6. *As a reviewer at Kuku*, I can see raw outputs, prompts and an evaluation report for any run.

## 6. Assumptions (the brief is silent on these, so we decided)
| ID | Assumption | Why it's reasonable | Risk if wrong |
|---|---|---|---|
| A1 | Script timestamps ≈ final video timestamps (±1 s) | In an AI-native pipeline the script is the shot list; every block has 0.1 s timing | Editor trims by hand; a future video-alignment step would fix it |
| A2 | Good cuts land on CAMERA shot boundaries | Cutting mid-shot looks amateur | Some cuts may be slightly loose; flagged |
| A3 | Duration = sum of all segments; sweet spot 30–45 s | Brief says 20–60; ReelShort-style ads are usually ~30–45 s | Weight is tunable |
| A4 | Target audience: cold US viewers on TikTok/Reels/Shorts who don't know the characters | Show is English, made for US audiences | Standalone scoring could be stricter or looser |
| A5 | Spoilers are allowed (a late identity reveal can be a hook), with a mild bonus for early episodes | Category leaders use payoff moments as hooks; early-episode promos land viewers at the start of the funnel | Weights are tunable |
| A6 | Output is a shortlist for a human, not a single answer | Kuku A/B tests creatives; taste varies | n/a |
| A7 | Graphic violence (e.g. torture scenes) may break ad-platform policies | Meta and TikTok restrict graphic violence in ads | Flag only, never auto-exclude |

## 7. Functional requirements
| ID | Requirement |
|---|---|
| FR1 | Parse a folder or zip of episode `.txt` scripts in the given format; tolerate casing, whitespace and missing optional sections. Report a parse summary. |
| FR2 | Canonicalise speaker names through an editable alias map (e.g. a character first credited by description, such as "MYSTERIOUS STRANGER", then later by name) |
| FR3 | For each episode, an LLM proposes 2–4 promo candidates as **block IDs** (hook block, cliff block, start/end block) with reasoning |
| FR4 | Code converts IDs to timestamps, snaps to shot boundaries, enforces 20–60 s and hook ≤ 3 s, and builds jump-cuts for overlong spans |
| FR5 | An arc pass proposes 3–8 cross-episode promos (setup in an early episode → payoff later), built and validated by code |
| FR6 | A judge model scores every candidate on the rubric (hook, cliff, standalone, trope pull, pacing) with reasons, hook text, cliff text and a one-line "why" |
| FR7 | Ranker produces a final ordered list with a diversity constraint and a posting-order rationale |
| FR8 | Outputs: `promos.csv`, `promos.json`, `review.md`, `manifest.json`, raw LLM responses, logs, all in `outputs/<run_id>/` |
| FR9 | Evaluation script compares a run to the gold set and produces `eval_report.md` |
| FR10 | Streamlit app: upload pack → choose model(s) → run → ranked table with excerpts and flags → download CSV/JSON |
| FR11 | Mock mode runs the full pipeline with no API key (canned responses), for tests and demos |

## 8. Non-functional requirements
| ID | Requirement |
|---|---|
| NFR1 | **Model-agnostic:** any LiteLLM-supported model or OpenAI-compatible endpoint, per stage, via config or flags |
| NFR2 | **Reproducible:** temperature 0, prompt versions recorded, cache keyed by model + prompt version + input hash, manifest per run |
| NFR3 | **Free to run:** default config uses free tiers only; handles rate limits with backoff and resumes from cache |
| NFR4 | **Confidential:** no Kuku content in the repo, deployed app, tests or logs committed to git |
| NFR5 | **Robust:** invalid LLM JSON → validate, retry once, skip with a logged error; one bad episode never kills a run |
| NFR6 | **Readable:** simple code that Harshit can explain line by line |
| NFR7 | **Measured:** every run logs tokens, calls, wall time and estimated cost per stage |

## 9. Rollout and adoption (the JD values this; it goes in the doc's "next steps")
1. Week 1: shadow an editor on one show and time the manual process (baseline).
2. Ship as a **pre-filled shortlist sheet** per show, where the editor marks ✓/✗ and trims.
3. Track the **adoption metric**: % of the editor's final posted promos that came from the tool's shortlist, and minutes saved per show.
4. Track the **quality metric**: join promo IDs to ad performance (CTR, CPI, 3-second hold rate), then retune ranker weights or fine-tune the judge on what actually performs.
5. Generalise: the same block-ID approach works for trailers, recap clips, thumbnails (pick frame moments) and per-market variants.

## 10. Future work (not in v1)
- Align with the rendered video (ASR/shot detection) to correct timestamp drift
- Visual hook check on the first 3 s (face, motion, contrast)
- Per-market variants (US, LatAm, India) and language versions
- Learn ranker weights from real ad performance

## 11. Release scope
- **MVP (must):** FR1–FR4, FR6–FR9, FR11, CLI, full run on all 50 episodes, eval report
- **Should:** FR5 (arc promos), FR10 (Streamlit), second-model comparison
- **Could:** posting-order rationale written by an LLM, walkthrough notebook
