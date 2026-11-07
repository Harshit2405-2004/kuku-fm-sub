# INSTRUCTIONS: run everything in order

Follow these steps top to bottom. Each step says **who** does it (🧑 you, 🤖 Claude Code), the **exact commands**, and how you know it's **done**. Windows commands are for **PowerShell**; Mac/Linux commands are for bash/zsh.

To understand *what* each process does, read `docs/PROCESS_GUIDE.md`. For *why* we chose it, read `private/EXPLANATION.md`.

> ⏰ **Deadline:** `TBD — Harshit to fill in (DATE TIME IST)` (48 hours from when Kuku's email arrived). **Submit by:** `deadline − 3 h`.

---

## PART A: One-time setup (🧑 about 45 min)

### Step 1: Install the basics
| Tool | Windows (PowerShell) | Mac / Linux | Check |
|---|---|---|---|
| Python 3.11+ | `winget install Python.Python.3.11` (3.13 also works) | `brew install python@3.11` / `sudo apt install python3.11 python3.11-venv` | `python --version` (Windows: `py -3.11 --version`) |
| Git | `winget install Git.Git` | `brew install git` / `sudo apt install git` | `git --version` |
| GitHub CLI (optional, makes repo creation easier) | `winget install GitHub.cli` | `brew install gh` | `gh --version`, then `gh auth login` |
| **Claude Code** | `irm https://claude.ai/install.ps1 \| iex` | `curl -fsSL https://claude.ai/install.sh \| bash` | Open a **new** terminal: `claude --version` |

Claude Code needs a Pro, Max, Team or Enterprise plan (or Console API credits). The free claude.ai plan doesn't include it. If something looks wrong, run `claude doctor`.

**Done when:** all four "Check" commands print versions.

### Step 2: Create the project folder from the kit
```bash
# unzip kuku-promo-finder-kit.zip somewhere sensible, then:
cd kuku-promo-finder
git init
python scripts/leak_check.py   # must pass BEFORE the first commit (nothing show-specific in tracked files)
git add .
git status          # MUST NOT list anything under private/, input/ (except README), outputs/, gold/*.csv
git commit -m "T0.2: project kit (specs, plan, Claude Code config)"
```
**Done when:** `git status` is clean and `private/` was not committed. Check with `git ls-files | grep private` (Windows: `git ls-files | Select-String private`), which must print nothing.

### Step 3: Create the public GitHub repo and push
```bash
python scripts/leak_check.py --pre-push   # always, before any push (scans all commits + messages)
gh repo create kuku-promo-finder --public --source . --remote origin --push
```
Without gh: create an empty **public** repo on github.com, then `git remote add origin <url>`, `git branch -M main`, `git push -u origin main`.

The repo must be public because Kuku must be able to open it. That's why nothing from the show ever goes in it.

### Step 4: Add the input pack
Unzip Kuku's zip **into `input/`**, so you get `input/<show folder>/episode-001-....txt` and so on.
```bash
git status          # must show NO changes. input/ is git-ignored.
```

### Step 5: API keys (free)
1. Gemini: https://aistudio.google.com → **Get API key**
2. Groq: https://console.groq.com → **API Keys**
3. Copy `.env.example` to `.env` and paste both keys:
```bash
cp .env.example .env          # Windows: Copy-Item .env.example .env
```
**Done when:** `.env` has both keys and `git status` still doesn't show `.env`.

### Step 6: Python virtual environment
```bash
# Mac/Linux
python3.11 -m venv .venv && source .venv/bin/activate
# Windows PowerShell
py -3.11 -m venv .venv ; .\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
```
If PowerShell blocks activation, run `Set-ExecutionPolicy -Scope CurrentUser RemoteSigned` once.

`requirements.txt` lists exactly the TECH_SPEC §9 packages, pinned. **Always start Claude Code from a terminal where the venv is active.**

### Step 7: Install the Claude Code plugins and skills (one command)
From the repo root:
```bash
# Mac/Linux
bash setup/install_claude_plugins.sh --all
# Windows PowerShell
powershell -ExecutionPolicy Bypass -File setup\install_claude_plugins.ps1 -All
```
This adds the two marketplaces and installs, at **project scope**: `superpowers`, `code-review`, `example-skills`, `document-skills`, `claude-md-management` and `context7`. Leave out `--all` / `-All` to skip the last two.

This script was tested end to end on Claude Code 2.1.319, and all 6 installed. Then:
```bash
git add .claude/settings.json && git commit -m "T0.5: project plugins" && git push
```
(`settings.json` only lists plugin names. It's public-safe and shows Kuku your setup.)

**Alternative: let Claude run it.** Inside a Claude Code session, type `!` followed by the command, e.g. `! bash setup/install_claude_plugins.sh --all`, then run `/reload-plugins`.

**Manual fallback, one plugin at a time inside Claude Code:**
```text
/plugin marketplace add anthropics/skills
/plugin install superpowers@claude-plugins-official
/plugin install code-review@claude-plugins-official
/plugin install example-skills@anthropic-agent-skills
/plugin install document-skills@anthropic-agent-skills
/plugin install claude-md-management@claude-plugins-official
/plugin install context7@claude-plugins-official
```

### Step 8: Start Claude Code and check the setup
```bash
claude
```
Inside Claude Code:
- Type `/` and you should see `superpowers:` skills, plus our `log-decision`, `checkpoint` and `run-pipeline`.
- Run `/agents` and you should see `independent-reviewer` and `brief-auditor`.
- Run `/plugin` → **Installed** tab and you should see 6 plugins enabled.

**Done when:** all three checks pass. If one fails, see Troubleshooting at the end.

---

## PART B: Build with Claude Code (follow the checkpoints)

How every phase works: **you paste a prompt → Claude plans the phase → builds task by task (tests, report.md, commit) → stops at a checkpoint → you review → you reply with a checkpoint message from `KICKOFF_PROMPT.md`.**

**Public vs private logs:** `report.md`, `decisions.md`, `ai_log.md` and `docs/phase_plans/` are public. They hold only counts, block IDs, run IDs, timings and generic descriptions. Anything with script text, speaker names or plot goes in `private/` with a one-line pointer from the public file.

### Step 9: Kickoff (🧑 2 min, 🤖 5 min)
Paste **Prompt 1** from `KICKOFF_PROMPT.md`.
Claude reads all the docs and replies with a summary, any contradictions it found, and its Phase 1 task list. **Read the contradictions carefully.** Answer them, then type `go`.

### Step 10: Phase 1, Parser (🤖 about 45 min)
Claude writes the fictional sample show, the parser and tests, parses the real pack, and drafts the character alias map.
While it works, you can start **Step 12a** (watching ads).

### Step 11: CP-1, check the parser and fix the aliases (🧑 about 15 min)
When Claude stops at CP-1:
1. Read its stats in `report.md` (counts) and `private/parse_stats_T1.3.md` (details). There should be **50 episodes**, sensible durations (about 1–3.5 min each), and few warnings.
2. Open `config/aliases.yaml` and fix it by hand. Use `private/INPUT_PACK_NOTES.md` ("Character-name aliases") as your guide. Expect mistakes: they're your "AI got it wrong" evidence.
3. Review `private/leak_keywords.txt` (the keyword list `scripts/leak_check.py` uses).
4. Paste the **CP-1 reply** from `KICKOFF_PROMPT.md`. It tells Claude to log its alias mistakes and continue with Phase 3, and **not** to read gold/.

### Step 12: Phase 2, Gold labels (🧑 about 60 min). Do it now, before any model output exists.
- **12a** (15 min): watch about 10 microdrama ads (TikTok; Meta Ad Library, search "ReelShort" or "DramaBox"). Fill in `gold/ad_observations.md`.
- **12b** (45 min): copy `gold/gold_labels.template.csv` to `gold/gold_labels.csv`. Pick about 10 episodes (7 dramatic, 3 quiet). To see an episode with block IDs, run `python -m promo_finder.compact --input "input/<show folder>" --ep 3` (exists after T1.4). Write 12–20 promos you'd actually post. Rules are in `docs/EVAL_PLAN.md` §1.
- **12c:** choose 3 of those episodes as held-out and write their numbers in `gold/holdout.txt` (one per line).
- **12d:** tell Claude: `Gold labels done. Gold episodes are: <list>. Held-out: <3 of them>. Use only OTHER episodes for smoke tests and prompt iteration. You may now read gold/ad_observations.md (not gold_labels.csv) and use its patterns in the proposer prompt.`

### Step 13: Phase 3, LLM layer, proposer, builder (🤖 about 90 min)
Claude finds the current free model IDs and tests them, builds the LLM layer (cache, retries, model swap) and the cut builder, and writes prompt v1. **It waits for your Step 12d message**, then runs a **smoke test on 3 non-gold episodes** (details in `private/smoke_T3.5.md`).

### Step 14: CP-2, prompt review (🧑 about 20 min)
For each smoke-test promo, open the script and check:
- Does the hook really start within 3 s of the clip start?
- Does the clip end before the answer is revealed?
- Would a stranger follow it?

Optionally paste the proposer prompt into ChatGPT or Gemini and ask "how would this prompt fail?". Log anything useful in `ai_log.md` (generic) / `private/ai_log_details.md` (specifics).
Reply with the **CP-2 reply** from `KICKOFF_PROMPT.md`, including your notes.

### Step 15: Phase 4, arcs, judge, ranking, outputs, full run A (🤖 about 75 min)
Claude finishes the pipeline and runs **all 50 episodes**. Output goes to `outputs/<run_id>-A/`.

### Step 16: CP-3, skim the results (🧑 about 15 min)
Open `outputs/<run_id>-A/review.md`. Is it something an editor would use? Is anything obviously broken?
Reply `CP-3 approved` or ask for one round of changes.

### Step 17: Phase 5, evaluation (🤖 about 45 min, 🧑 about 45 min)
1. Claude builds the eval and creates `gold/precision_ratings.csv` (shuffled, no scores shown).
2. **You rate it blind** (2 = would post, 1 = maybe, 0 = no), then tell Claude `ratings done`.
3. Claude runs **run B** (one model swapped) and a stability check, then writes `eval_report.md` for both runs.
4. Claude proposes 6–8 failure cases. **You pick 3–5** and write them in your own words.

### Step 18: CP-4, decide the final config (🧑 about 15 min)
Read both eval reports. Are the numbers believable? Choose the final config. Claude logs the decision.

### Step 19: Phase 6, app, README, deploy (🤖 about 60 min, 🧑 about 20 min)
1. Claude builds the Streamlit app and the README, and runs `scripts/leak_check.py` (built at kickoff).
2. 🧑 Test locally: `streamlit run app.py` → try the synthetic sample, then upload the real pack.
3. 🧑 Push: `python scripts/leak_check.py --pre-push`, then `git push` (only if it passes).
4. 🧑 Deploy: https://share.streamlit.io → **New app** → pick your repo, branch `main`, file `app.py` → **Advanced settings → Secrets**, then paste:
   ```toml
   GEMINI_API_KEY = "..."
   GROQ_API_KEY = "..."
   ```
5. 🧑 Open the app URL in an **incognito window** and run the synthetic sample.

**Done when (CP-5):** the repo and app links both open in incognito, and a run works.

---

## PART C: Write, record, submit (🧑 about 2 hours)

### Step 20: Solution doc (2 pages, max)
1. Ask Claude: `Draft private/solution_doc_draft.md following docs/SUBMISSION.md §2, using only numbers from the final runs. Cite run IDs.`
2. **Rewrite it in your own words** in Google Docs. Header line: Name · Roll No · Branch · Problem 1 · links.
3. File → Download → PDF. Check it's **≤ 2 pages**.
4. Upload to Google Drive → Share → **Anyone with the link → Viewer** → copy the link.

### Step 21: Raw outputs folder
Create a Drive folder `Kuku-raw-outputs`. Upload the whole `outputs/<run A>/` and `outputs/<run B>/` folders **unedited**, plus both eval reports. Share it as *Anyone with the link → Viewer*.

### Step 22: Walkthrough video (≤ 3 min)
Use the script in `docs/SUBMISSION.md` §3. Record with Loom (free) or OBS, then upload as an **unlisted** YouTube video or a Loom link. Your own voice, and show a real run.

### Step 23: Final audit (CP-6)
Paste the **Final audit** prompt from `KICKOFF_PROMPT.md`. Fix every blocking gap it reports.

### Step 24: Submit
1. Open **every** link in an incognito window: PDF, app, repo, outputs folder, video.
2. Open the Google Form (already in your own account).
3. Fill in: email, name, roll no, college email, PDF link, prototype link (the app; the repo link is in the PDF), raw outputs link, video link.
4. Submit and **screenshot the confirmation.**

---

## PART D: Interview prep (after submitting)
| Step | Do | How |
|---|---|---|
| 25 | Model-swap rehearsal | Paste the **Model-swap rehearsal** prompt from `KICKOFF_PROMPT.md` |
| 26 | New-format robustness | Ask Claude: `Do PLAN T8.1: make 2 mutated copies of the pack in input/mutations/ and run them. Fix only crashes.` |
| 27 | Know your code | Read `promo_finder/build.py` and `rank.py` yourself. Explain the snapping rule and the score formula out loud. |
| 28 | Rehearse answers | `private/EXPLANATION.md` §8, 12 questions |

---

## Troubleshooting
| Problem | Fix |
|---|---|
| `claude` not found after installing | Open a **new** terminal. Still missing? Run `claude doctor`, then see https://code.claude.com/docs/en/troubleshoot-install |
| Plugin install fails with "not found" | In Claude Code: `/plugin` → **Discover** → search the name → install. Or run `claude plugin marketplace update` and retry. |
| Skills don't appear after install | Run `/reload-plugins`, or restart `claude` from the repo root |
| `/agents` doesn't show our agents | You started `claude` outside the repo folder. `cd` into it and restart. |
| PowerShell blocks scripts | `powershell -ExecutionPolicy Bypass -File setup\install_claude_plugins.ps1` |
| 429 / rate-limit errors during the full run | Normal on free tiers. The pipeline backs off and resumes from cache, so just re-run the same command. |
| Groq daily token cap reached | Wait for the reset, or move the judge to Gemini for that run (`--judge-model`). Log it as a decision. |
| Claude starts the next phase without asking | Say: `Stop. CLAUDE.md says checkpoints are blocking. Revert to the checkpoint state and wait.` |
| Claude's context gets long or slow | Make sure report.md is up to date, run `/clear`, then paste **Prompt 2** (resume) |
| You accidentally committed something from `private/` or `input/` | **Don't push.** `git rm --cached -r <path>`, commit, and check `.gitignore`. If it was already pushed, tell Claude and rewrite history before the deadline. |
