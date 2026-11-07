# AI usage and mistakes log

The brief asks: "In your doc, tell us which tools you used and **one place where they got it wrong**." Log every case as it happens. At the end, pick the most instructive one for the doc: one where you caught the mistake *because of a check you designed*.

## Tools in use
| Tool | Version / model | Role |
|---|---|---|
| Claude Code | Opus 5.5 (claude-opus-5-5) | Primary builder |
| Plugins/skills | (from docs/SKILLS_AND_TOOLS.md) | Workflow: planning, TDD, review |
| Runtime proposer | (from config.yaml) | Proposes promo candidates |
| Runtime judge | (from config.yaml) | Scores candidates |
| Second AI (browser) | (fill in) | Independent critique |

## Mistakes log
| # | When | Tool | What it got wrong | How it was caught | Fix | Lesson |
|---|---|---|---|---|---|---|
| 1 | 2026-11-07 kickoff | Claude Code (Opus 5.5) | First confidentiality scan reported only two show-specific lines in tracked docs; it cut each grep hit to 220 characters and missed a plot summary later on the same line of a research doc | Re-reading the line while applying Harshit's fixes | Sentence moved to private/; built scripts/leak_check.py, which scans whole lines against three word lists | A truncated grep is a sampling check, not a guarantee: confidentiality needs a script with no output limits |

| 2 | 2026-11-07 CP-1 | Claude Code (Opus 5.5) | Claimed in D-018 and the parser docstring that bad input 'never crashes', but a malformed timestamp raised an exception that stopped the whole pack, and two format variants were dropped with no warning | independent-reviewer subagent probed mutated synthetic input | Bad times now warn and skip; added a line-coverage counter; 21 regression tests | A robustness claim needs a test for each failure class, not just the happy-path variants |

Examples of things worth logging:
- The alias map draft merged two different characters, or split one into two
- The runtime LLM returned a block ID that doesn't exist, or a hook block after the cliff block
- The judge rated a slow monologue highly (caught by blind human rating)
- Claude Code used an outdated LiteLLM or model name (caught by the 1-token test call)
- A test passed for the wrong reason
