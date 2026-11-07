# Build plan: Kuku Promo Finder

**Owners:** 🧑 Harshit · 🤖 Claude Code · 🔁 second AI (ChatGPT or Gemini in the browser, as an independent reviewer)
**CP-x = checkpoint.** Claude Code stops, summarises in report.md, and waits for Harshit's "go".
Time estimates are working time. Claude Code's run time overlaps with Harshit's tasks.

**Deadline:** 48 hours from the brief email = `TBD — Harshit to fill in (DATE TIME IST)`. **Submit at least 3 hours early.** Late submissions aren't reviewed.

```
Phase 0 Setup (🧑 45m)
Phase 1 Parser (🤖 45m) ──CP-1──┐
Phase 2 Gold labels (🧑 60m)     │  ← in parallel with Phase 3a
Phase 3 LLM + propose + build (🤖 90m) ──CP-2 (prompt review)
Phase 4 Arcs + judge + rank + outputs + FULL RUN A (🤖 75m) ──CP-3
Phase 5 Eval + Run B + failure gallery (🤖 45m + 🧑 45m) ──CP-4
Phase 6 App + README + deploy + leak check (🤖 60m + 🧑 20m) ──CP-5
Phase 7 Doc + video + submit (🧑 2h, 🤖 drafts) ──CP-6 (brief audit) → SUBMIT
Phase 8 Interview prep (after submitting)
```
Total: about 4.5–5 hours of Harshit's time, about 6 hours of Claude Code time, spread over the 48 hours.

---

## Phase 0: Setup (🧑 about 45 min)
| ID | Task | Owner |
|---|---|---|
| T0.1 | Note the deadline at the top of this file and at the top of INSTRUCTIONS.md. | 🧑 |
| T0.2 | Create a **public** GitHub repo `kuku-promo-finder`. Copy this kit into it. Run `git init`, then commit the kit (check that `.gitignore` is there first). | 🧑 |
| T0.3 | Put the input zip in `input/` and unzip it there. Confirm `git status` doesn't show it. | 🧑 |
| T0.4 | Get free API keys: Google AI Studio (Gemini) and Groq. Put them in `.env` (copied from `.env.example`). | 🧑 |
| T0.5 | Install Claude Code plugins and skills with one command: `bash setup/install_claude_plugins.sh --all` (Windows: `powershell -ExecutionPolicy Bypass -File setup\install_claude_plugins.ps1 -All`). Commit `.claude/settings.json`. Restart Claude Code. | 🧑 |
| T0.6 | Python 3.11+ venv. Mac/Linux: `python3.11 -m venv .venv && source .venv/bin/activate`. Windows: `py -3.11 -m venv .venv ; .\.venv\Scripts\Activate.ps1`. Then `pip install -r requirements.txt`. | 🧑 |
| T0.7 | Start Claude Code in the repo and paste `KICKOFF_PROMPT.md` | 🧑 |

## Phase 1: Parser and data (🤖 about 45 min)
| ID | Task | Done when |
|---|---|---|
| T1.1 | Write `samples/synthetic_show/` with 3 short fictional episodes in the exact pack format. Include edge cases: capitalised headers, `(O.S.)`, multi-line text, a scene with no SOUND FX. Use original characters and story only. | Files exist; story is clearly original |
| T1.2 | `parse.py` and the Pydantic models, plus `tests/test_parser.py` and `tests/test_parser_variants.py` (TECH_SPEC §3, §10) | `pytest -q` passes |
| T1.3 | Parse the real pack. Print the stats: episodes, blocks by type, durations, warnings. List unique raw speakers and **draft** `config/aliases.yaml` from them plus the loglines. | Counts in report.md, details (speakers, warnings) in `private/parse_stats_T1.3.md`; alias draft written |
| T1.4 | `compact.py`, plus a CLI to print one episode's compact view, and token counts per episode | Token table in report.md |
| **CP-1** | 🧑 **Review:** parse stats look right (50 episodes, runtimes match); **fix the alias map by hand** (expect AI errors, and log them in ai_log.md); skim one compact view. | Harshit says "go" |

## Phase 2: Gold labels (🧑 about 60 min). **Do this before looking at any model output.**
| ID | Task |
|---|---|
| T2.1 | Watch about 10 real ReelShort or DramaBox ads. Write `gold/ad_observations.md` (EVAL_PLAN §1). |
| T2.2 | Label 12–20 gold promos across about 10 episodes in `gold/gold_labels.csv`, including 2–3 quiet episodes. Pick 3 gold episodes as the **held-out test set** and write their numbers in `gold/holdout.txt`. |
| T2.3 | 🔁 Optional: ask a second AI to read the brief's promo definition and critique your rubric anchors. You decide what to keep. |

## Phase 3: LLM layer, proposer, builder (🤖 about 90 min, can run in parallel with Phase 2)
| ID | Task | Done when |
|---|---|---|
| T3.1 | Look up the **current** free-tier model IDs (Gemini Flash, and a Groq model with JSON support). Run a 1-token test call for each and record them in decisions.md and `config.yaml`. | Both calls succeed |
| T3.2 | `llm.py` + `cache.py` + `config.py` + `mock.py`: LiteLLM, per-stage config, CLI overrides, `api_base`, retries, JSON validation and repair, usage accounting | Unit tests with mocks pass |
| T3.3 | `build.py` + `tests/test_build.py`: snapping, duration rules, jump-cuts, dedupe, validity flags (TECH_SPEC §4.3) | Tests pass |
| T3.4 | `prompts/proposer.md` v1 (with examples from the synthetic show only, plus patterns from ad_observations.md once T2.1 exists) and `propose.py` | Mock pipeline runs |
| T3.5 | **Wait** until Harshit says gold labels are done and gives the gold episode numbers. Then run the **smoke test**: the real proposer on 3 **non-gold** episodes. Write the candidates (timestamps, hook/cliff, excerpts) to `private/smoke_T3.5.md`; report.md gets counts, run ID and a pointer. | Output shown |
| **CP-2** | 🧑 **Prompt review:** read the 3-episode output against the scripts. Is the hook really in the first 3 s? Is the cliff unresolved? Request prompt changes. 🔁 Optionally paste the prompt into a second AI: "how would this prompt fail?" Log the useful critiques. | Harshit says "go" |

## Phase 4: Arcs, judge, ranker, outputs, full run A (🤖 about 75 min)
| ID | Task | Done when |
|---|---|---|
| T4.1 | `arcs.py` + `prompts/arc.md`; arc validation in build.py | Tests and mock pass |
| T4.2 | `judge.py` + `prompts/judge.md` (rubric anchors, reasons before scores, risk flags), using a different model family from the proposer | Mock passes |
| T4.3 | `rank.py` + tests (weights, bonuses, diversity) | Tests pass |
| T4.4 | `report.py`: promos.csv, promos.json, review.md, manifest.json (TECH_SPEC §7) | Schema test passes |
| T4.5 | `run.py` CLI tied together; `--mock` end-to-end test | `pytest -q` green |
| T4.6 | **FULL RUN A** on all 50 episodes with the default free config. Save to `outputs/<run_id>-A/`. Log the token, time and cost table. Don't edit outputs. | 50/50 episodes; manifest complete |
| **CP-3** | 🧑 Skim review.md. Is it something an editor would use? Approve or request one round of changes. **Don't tune on gold episodes, except as EVAL_PLAN §7 allows.** | Harshit says "go" |

## Phase 5: Evaluation (🤖 about 45 min + 🧑 about 45 min)
| ID | Task | Owner |
|---|---|---|
| T5.1 | `metrics.py` + `evaluate.py` + tests (IoU, matching, recall, Spearman, Jaccard) | 🤖 |
| T5.2 | `evaluate.py --make-blind-sheet`, then Harshit rates `gold/precision_ratings.csv` blind | 🤖 then 🧑 |
| T5.3 | **Run B:** swap one stage's model family. Run the full pack again. Also do one repeat of run A with the cache off on 10 episodes (stability). | 🤖 |
| T5.4 | Generate `eval_report.md` for A and B, plus the comparison table | 🤖 |
| T5.5 | **Failure gallery:** Claude proposes 6–8 candidate failures with evidence; Harshit confirms and picks the 3–5 best, in his own words | 🤖 + 🧑 |
| **CP-4** | 🧑 Read the eval report. Are the numbers believable? Decide the final config and record the decision. | 🧑 |

## Phase 6: Prototype packaging (🤖 about 60 min + 🧑 about 20 min)
| ID | Task | Owner |
|---|---|---|
| T6.1 | `app.py` Streamlit (TECH_SPEC §8), tested locally on the synthetic show and on the real pack | 🤖 |
| T6.2 | README: what it is, 3-step quickstart, **"Swap the model"** section with exact flags, mock mode, outputs explained, limitations, confidentiality note | 🤖 |
| T6.3 | Optional `notebooks/walkthrough.ipynb`: run each stage step by step on the synthetic show, in simple Colab style | 🤖 |
| T6.4 | Run `scripts/leak_check.py` (built at kickoff), then `git status`, then push | 🤖 + 🧑 |
| T6.5 | Deploy to Streamlit Community Cloud. Add the key in app secrets. Test in incognito: synthetic sample and an upload of the real pack. | 🧑 |
| **CP-5** | The app link and repo link open for anyone; mock and real runs both work | 🧑 |

## Phase 7: Doc, video, submit (🧑 about 2 hrs; 🤖 drafts)
| ID | Task | Owner |
|---|---|---|
| T7.1 | Claude drafts `private/solution_doc_draft.md` from **real results only**, following docs/SUBMISSION.md | 🤖 |
| T7.2 | Harshit rewrites it in his own words. Max 2 pages. Export to PDF and upload to Drive (anyone with the link can view). | 🧑 |
| T7.3 | Upload `outputs/<run A>` and `outputs/<run B>` **unedited** to a Drive folder (anyone with the link can view) | 🧑 |
| T7.4 | Record the walkthrough video (≤ 3 min, script in SUBMISSION.md). Loom or unlisted YouTube. | 🧑 |
| **CP-6** | 🤖 Run the `brief-auditor` subagent over the repo, doc draft and links list. Fix any gaps. | 🤖 + 🧑 |
| T7.5 | Open every link in incognito, fill the form from your own account, submit, and screenshot the confirmation | 🧑 |

## Phase 8: Interview prep (after submitting)
| ID | Task |
|---|---|
| T8.1 | Robustness: make 2 mutated copies of the pack (rename speakers, reformat timestamps, drop the CONTINUITY line) and run them. Fix crashes only. |
| T8.2 | **Model-swap rehearsal:** run with `--model openai/<x> --api-base <url> --api-key-env <VAR>` against any OpenAI-compatible endpoint (e.g. Groq's OpenAI-compatible URL) so the flag path is proven. Time a fresh, uncached run on a new 10-episode pack. |
| T8.3 | Read `private/EXPLANATION.md` §8 (interview Q&A). Be able to explain build.py snapping and the ranker formula on a whiteboard. |
| T8.4 | Prepare 2 "what I'd do next" answers with numbers from the eval. |

---

## Where each AI tool is used (for the doc's "AI tools used" section)
| Tool | Used for | Not used for |
|---|---|---|
| Claude Code (CLI) + plugins/skills | Building, tests, refactors, running the pipeline, drafting reports | Gold labels, final decisions, final doc wording |
| Claude Code subagents (`independent-reviewer`, `brief-auditor`) | Fresh-context review of diffs and brief compliance | — |
| Second AI in the browser (ChatGPT/Gemini) | Independent critique of the rubric, prompts and doc | Writing code that you then don't read |
| Runtime LLMs (Gemini Flash, Groq model, later Kuku's) | Proposer, arc, judge stages in the product | Timestamps (code owns them) |
| Cursor | **Optional**, only if you actually use it (e.g. reading code with inline AI explain). Don't list a tool you didn't really use. | — |