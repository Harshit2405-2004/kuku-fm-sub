# Brief compliance matrix

Every instruction in Kuku's assignment PDF ("Kuku — AI Generalist Assignment", 6 pages) is listed here, with how we satisfy it and where. **If anything else in this repo conflicts with this file, this file wins.**
Status: ☐ not started · ◐ in progress · ☑ done (with evidence path)

## A. Process rules (brief page 1)

| # | Brief says (verbatim or close) | How we satisfy it | Where / evidence | Status |
|---|---|---|---|---|
| A1 | "Pick one problem, spend about 2 to 3 hours on it and submit within 48 hours" | Problem 1 only. The core pipeline is time-boxed; eval and polish are extra. **Submit before the deadline**, since late work isn't reviewed. | decisions.md D-001; PLAN.md timeline | ☐ |
| A2 | "Make assumptions instead of asking… note it in your doc and keep going" | Every assumption goes in decisions.md, and the top 5–6 go in the solution doc | decisions.md; docs/PRD.md §6; solution doc §3 | ☐ |
| A3 | "Use AI freely, and tell us how… which tools you used and one place where they got it wrong" | ai_log.md records every AI mistake as it happens. The solution doc has an "AI tools used" section with the best example. | ai_log.md; solution doc §8 | ☐ |
| A4 | "Free tiers are enough… If a paid API would help, tell us how you'd use it and build a smaller version for free" | Free Gemini Flash plus a free Groq model. The doc explains how a stronger paid model would slot in (per-stage config) and what it would cost. | config.yaml; TECH_SPEC §5; solution doc §7 | ☐ |
| A5 | "Build something you can run again… you'll run your solution on a new input during your interview" | One CLI command and a Streamlit upload that accept any pack. The parser is tolerant of format variants and tested against synthetic variants. | run.py; app.py; tests/test_parser_variants.py | ☐ |
| A6 | "We may also connect stronger models through APIs we provide, so a solution where the model is easy to swap will shine" | LiteLLM layer. The model is chosen per stage in config or by flags (`--model`, `--api-base`, `--api-key-env`). Any OpenAI-compatible endpoint works. Rehearsed in PLAN T8.2. | promo_finder/llm.py; README "Swap the model" | ☐ |
| A7 | "Make it your own… submit only work you understand" | Harshit owns the decisions (checkpoints), hand-labels the gold set, writes the final doc, and reads every module. Code is kept simple on purpose. | PLAN checkpoints; private/EXPLANATION.md | ☐ |

## B. Problem 1 requirements (brief page 2)

**Verbatim source: the brief's promo definition** (supplied by Harshit at CP-2, 2026-11-07; quoted word for word in `promo_finder/prompts/proposer.md` (proposer_v3) and `promo_finder/prompts/judge.md`):

> A promo is a 20 to 60-second clip taken from the show itself and posted on Instagram, TikTok or YouTube to pull new viewers in. It's usually one continuous stretch, but it can also join a few moments, from one episode or across several. A good promo: opens on a hook: something in the first 3 seconds that makes a scrolling viewer stop, like a slap, a reveal or a shocking line; ends on a cliffhanger: it cuts at an unresolved moment, so the viewer needs to know what happens next; makes sense on its own to someone who has never seen the show.

| # | Requirement | How we satisfy it | Evidence | Status |
|---|---|---|---|---|
| B1 | A promo is a 20–60 s clip from the show | Code enforces 20 ≤ total duration ≤ 60 s. 100% of outputs are validated. | build.py validity checks; eval report "validity" | ☐ |
| B2 | "usually one continuous stretch, but can also join a few moments, from one episode or across several" | Three promo types: `single` (one stretch), `jumpcut` (same-episode multi-segment), and `arc` (cross-episode multi-segment) | TECH_SPEC §4.3–4.4 | ☐ |
| B3 | Opens on a hook in the **first 3 seconds** | Code check: the hook block starts within 3.0 s of promo start. The judge also scores hook strength. | build.py; scored.json `hook_offset_s` | ☐ |
| B4 | Ends on a cliffhanger: "cuts at an unresolved moment" | The LLM picks the cliff block. Code ends on that block's shot and checks that no resolving dialogue is included. The judge scores "unresolved". A risk flag is raised when the cliff may be resolved. | build.py; judge rubric | ☐ |
| B5 | "makes sense on its own to someone who has never seen the show" | `standalone` rubric score plus a `needs_context` flag | judge prompt; EVAL failure taxonomy | ☐ |
| B6 | Only find promos; no editing, music or overlays | Out of scope (PRD non-goals) | PRD §4 | ☑ |
| B7 | "Find the promos across **all** episodes" | Proposer runs on all 50 episodes, and the arc pass covers the whole show | outputs/<run>/manifest.json shows 50/50 episodes | ☐ |
| B8 | For each promo: episode, start/end of **every segment, in order**, plus hook, cliffhanger, one line on why it works | promos.csv / promos.json schema | TECH_SPEC §7 | ☐ |
| B9 | "Rank them. Which promos would you post first, and why?" | Ranker (weighted rubric, bonuses, diversity) plus a "posting order rationale" section in review.md | rank.py; review.md | ☐ |
| B10 | "Check quality. Where does your tool pick badly?" | EVAL_PLAN: gold-set recall, blind precision@10, judge-vs-human agreement, model agreement, validity, and a failure gallery | outputs/<run>/eval_report.md | ☐ |
| B11 | "look at how apps like ReelShort and DramaBox promote their shows" | Harshit watches about 10 real ads before labelling and puts 3 observed hook patterns in the prompt and doc | gold/ad_observations.md | ☐ |

## C. Submission items (brief page 4)

| # | Item | Plan | Status |
|---|---|---|---|
| C1 | Form with name, roll number, **branch**, **problem chosen**, links | The form lacks branch and problem fields, so put them in the PDF header. Submit from Harshit's own Google account (the form is already in it). | ☐ |
| C2 | **Solution doc, PDF, up to 2 pages** | docs/SUBMISSION.md outline. Draft from real results; Harshit writes the final. | ☐ |
| C3 | **Prototype link** "anything we can open" | Streamlit Community Cloud app plus a public GitHub repo with clear run steps (no confidential data) | ☐ |
| C4 | **Raw outputs**: "a folder of unedited outputs from running your solution on the full input pack" | A Google Drive folder, viewable by anyone with the link, holding untouched `outputs/<run_id>/` for both model runs | ☐ |
| C5 | Walkthrough video, optional and recommended: up to 3 min, own voice, solution running | Loom or unlisted YouTube, using the script in docs/SUBMISSION.md | ☐ |
| C6 | "Make sure every link opens for anyone who has it" | Test every link in an incognito window | ☐ |
| C7 | The doc must cover: which problem and why; assumptions; how it works; how it scales to every show; how you know it's good, including where it fails | SUBMISSION.md section map, checked against this row | ☐ |

## D. The five evaluation lenses (brief page 5)

| Lens | What they want | Our evidence |
|---|---|---|
| Problem choice and framing | Why this problem, scope, assumptions | D-001 (marketing is ~78% of cost), PRD, assumptions list |
| Approach and scale | What went to AI vs code vs human; real-world volume and cost | AI/code/human split table, measured tokens per show, cost formula, parallelism |
| Quality checking | "backed by real runs and honest failures" | eval_report.md, failure gallery, two-model comparison |
| The prototype | "runs on real inputs and produces output someone could actually use" | Full 50-episode run, editor-ready CSV and review.md, Streamlit app |
| Communication | "clear, specific and short" | 2-page PDF, under-3-minute video |

"Polish and length won't earn extra credit; clear thinking will." Don't gold-plate the UI.

## E. Fine print

| # | Rule | How we comply |
|---|---|---|
| E1 | Confidentiality: "please don't publish or share" the input pack | `input/`, `outputs/`, `private/`, `config/aliases.yaml`, `gold/*.csv` and `.cache/` are git-ignored; `scripts/leak_check.py` runs before every push; the app needs an upload; tests and prompt examples use a synthetic show. Raw outputs are shared only through the Drive link in the form (D-008). |
| E2 | Integrity: keep work your own; similar submissions are reviewed | Own gold set, own weights, own failure analysis. All decisions are logged with Harshit as owner. |
| E3 | One problem, one submission | Problem 1, one form |
| E4 | "Can AI write my solution doc? It can help, but the decisions should be yours" | Claude drafts from results; Harshit rewrites and owns it |
| E5 | "Half works? Submit, tell us what works, what doesn't and why" | Honest "Limitations" section in the doc |

## F. JD signals to show (from the JD PDF)

| JD says | Where we show it |
|---|---|
| "figure out why something is hard before jumping to a solution" | PRD problem analysis; gold labelling done before prompting |
| "test whether the output is good, and know when a simpler solution is the better one" | Code does parsing, snapping, validation and ranking; the LLM only does judgement |
| "Drive adoption… improving based on feedback" | PRD §9 rollout: editor shortlist sheet, feedback loop from real ad CTR/CPI |
| "Share what you learn so patterns… help the rest of the company" | Doc "next steps": the same block-ID approach works for trailers, thumbnails, recap clips |
