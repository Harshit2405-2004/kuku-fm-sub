# Claude Code skills, plugins and tools for this project

Researched 7 Nov 2026. Plugin names and marketplaces change, so **if an install command fails with "plugin not found", open `/plugin` → Discover and search for the name.** Plugins can run code and hooks, so install only from the official marketplace or repos you've checked.

**Principle: install few, use them well.** Every plugin adds context to each turn. Kuku grades "how well you use [AI tools]", not how many. The set below is chosen to support a specific workflow: plan → test-first → build → independent review → verify.

---

## 1. Recommended set

| Priority | Plugin / skill | Source | What it does for *this* project |
|---|---|---|---|
| ★ Must | **superpowers** | `obra/superpowers` (also in the official marketplace) | Skills: `brainstorming`, `writing-plans`, `executing-plans`, `test-driven-development`, `systematic-debugging`, `verification-before-completion`, `requesting-code-review`, `subagent-driven-development`. Enforces test-first for build.py/metrics.py and "prove it works before saying done". |
| ★ Must | **Project skills in this kit** (`.claude/skills/`) | ours | `/log-decision`, `/checkpoint`, `/run-pipeline`: keep report.md and decisions.md disciplined and make runs repeatable |
| ★ Must | **Project subagents in this kit** (`.claude/agents/`) | ours | `independent-reviewer` (fresh-context code review against the spec) and `brief-auditor` (checks everything against Kuku's brief) |
| ◆ Should | **example-skills** → `webapp-testing` | `anthropics/skills` | Playwright-based checking of the Streamlit app (does the upload → table flow work?) |
| ◆ Should | **document-skills** → `pdf` | `anthropics/skills` | Helps turn the final doc into a clean ≤2-page PDF |
| ◆ Should | **code-review** | `anthropics/claude-plugins-official` | Multi-agent review of a diff with confidence scores. Use it before CP-5. |
| ○ Optional | **claude-md-management** | `anthropics/claude-plugins-official` | Audits and improves CLAUDE.md as the project evolves |
| ○ Optional | **Context7 MCP** | Upstash | Fetches *current* library docs (LiteLLM, Streamlit, Pydantic), which reduces outdated-API mistakes. Check the install command at context7.com. |
| ✕ Skip | feature-dev | official | Overlaps with superpowers; pick one workflow, not two |
| ✕ Skip | Big "1,000 skills" collections | various | Noise, context bloat, unreviewed code |

## 2. Install (inside Claude Code)

```text
# superpowers (official marketplace)
/plugin install superpowers@claude-plugins-official
#   fallback: /plugin marketplace add obra/superpowers-marketplace
#             /plugin install superpowers@superpowers-marketplace

# Anthropic skills marketplace
/plugin marketplace add anthropics/skills
/plugin install example-skills@anthropic-agent-skills
/plugin install document-skills@anthropic-agent-skills

# official plugins
/plugin install code-review@claude-plugins-official
/plugin install claude-md-management@claude-plugins-official   # optional
```
Then restart Claude Code. Check with `/plugin` (installed list) and `/agents` (should show `independent-reviewer` and `brief-auditor`).

The project skills and subagents in `.claude/` load automatically when you start Claude Code in the repo folder.

## 3. How superpowers fits our docs (avoid two competing plans)
superpowers wants to brainstorm → write a plan → execute. **We already have the spec and plan**, so the kickoff prompt tells Claude Code to:
- skip open-ended brainstorming and treat `docs/PRD.md` + `docs/TECH_SPEC.md` as the approved spec;
- use `writing-plans` only to break a PLAN.md *phase* into small steps, saved under `docs/phase_plans/phase-<n>.md`;
- use `test-driven-development` for deterministic modules (parse, build, rank, metrics);
- use `verification-before-completion` before every report.md "done";
- use `systematic-debugging` when a run fails, rather than random retries.

## 4. Built-in Claude Code features we use (no install)
| Feature | Where in the plan |
|---|---|
| `CLAUDE.md` project memory | Always loaded: rules, commands, sources of truth |
| Plan mode (Shift+Tab to cycle modes) | At the start of each phase: Claude proposes steps before editing |
| Subagents (`.claude/agents/*.md`) | Independent review at the end of each phase; brief audit at CP-6 |
| Skills / slash commands (`.claude/skills/*/SKILL.md`) | `/log-decision`, `/checkpoint`, `/run-pipeline` |
| `/clear` + resume from report.md | When context gets long between phases |

## 5. Showing this to Kuku (the evidence)
Kuku asked which tools you used and how well. Make the evidence visible in the repo:
1. `.claude/` folder: committed agents and skills show a deliberate AI workflow.
2. `report.md`: a task-by-task build log with real command output.
3. `decisions.md`: every choice, alternatives and owner, showing that you made the decisions.
4. `ai_log.md`: AI mistakes caught, and by which check.
5. In the doc: a 5-row "AI tools used" table plus the best mistake story.
6. In the interview: open `report.md` and walk through one CP review where you overrode Claude.

Say it plainly: *"Claude Code built most of the code under my specs and checkpoints; I wrote the gold set, made the calls at each checkpoint, and here's where the AI was wrong."* That's what the brief is asking for.

## Sources
- obra/superpowers: https://github.com/obra/superpowers
- anthropics/skills: https://github.com/anthropics/skills
- anthropics/claude-plugins-official: https://github.com/anthropics/claude-plugins-official
- Claude Code docs, subagents: https://code.claude.com/docs/en/sub-agents
- Claude Code docs, skills: https://code.claude.com/docs/en/skills
- Best Claude Code skills 2026 (developersdigest): https://developersdigest.tech/blog/best-claude-code-skills-2026
- LiteLLM JSON / structured outputs: https://docs.litellm.ai/docs/completion/json_mode
