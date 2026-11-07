# AI usage and mistakes log

The brief asks: "In your doc, tell us which tools you used and **one place where they got it wrong**." Log every case as it happens. At the end, pick the most instructive one for the doc: one where you caught the mistake *because of a check you designed*.

## Tools in use
| Tool | Version / model | Role |
|---|---|---|
| Claude Code | Opus 5.5 (claude-opus-5-5) | Primary builder |
| Plugins/skills | (from docs/SKILLS_AND_TOOLS.md) | Workflow: planning, TDD, review |
| Runtime proposer | gemini/gemini-3.5-flash (D-022) | Proposes promo candidates |
| Runtime judge | groq/openai/gpt-oss-120b (D-022) | Scores candidates |
| Second AI (browser) | (fill in) | Independent critique |

## Mistakes log
| # | When | Tool | What it got wrong | How it was caught | Fix | Lesson |
|---|---|---|---|---|---|---|
| 1 | 2026-11-07 kickoff | Claude Code (Opus 5.5) | First confidentiality scan reported only two show-specific lines in tracked docs; it cut each grep hit to 220 characters and missed a plot summary later on the same line of a research doc | Re-reading the line while applying Harshit's fixes | Sentence moved to private/; built scripts/leak_check.py, which scans whole lines against three word lists | A truncated grep is a sampling check, not a guarantee: confidentiality needs a script with no output limits |

| 2 | 2026-11-07 CP-1 | Claude Code (Opus 5.5) | Claimed in D-018 and the parser docstring that bad input 'never crashes', but a malformed timestamp raised an exception that stopped the whole pack, and two format variants were dropped with no warning | independent-reviewer subagent probed mutated synthetic input | Bad times now warn and skip; added a line-coverage counter; 21 regression tests | A robustness claim needs a test for each failure class, not just the happy-path variants |
| 3 | 2026-11-07 T3.1 | Web search (used by Claude Code) | Third-party pages gave contradictory free-tier limits and named model versions that couldn't be confirmed | Listing models from the providers' own APIs and making a 1-token call to each | Took IDs only from the live API lists plus test calls | For model IDs, the provider's API is the source of truth; blogs are leads, not facts |
| 4 | 2026-11-07 T1.3 → CP-1 | Second AI (wrote Harshit's private pack notes) + Claude Code (Opus 5.5) | The notes guessed one mapping for a descriptive speaker label. Claude's T1.3 alias draft rejected that guess but mapped the label to one character across the whole pack. In fact the script uses the label for **two different characters**: one in a single early episode (2 blocks), another in 9 later episodes (51 blocks). The draft also left 1 label unmapped that belongs to an existing character (2 blocks); this was a gap, not a wrong mapping | An alias evidence sheet built for every VERIFY line: episodes, first appearances with line numbers, name mentions in the same shot. Harshit made the final call after reading the script lines | Per-episode alias override (D-026, 3 tests); 1 label re-pointed in 1 episode, 1 label mapped, 2 labels confirmed as separate speakers, 2 kept but marked "likely, not proven"; canonical speakers 52 → 51; details in private/ai_log_details.md | A descriptive label ("the man in X") is a costume, not an identity: check every episode it appears in, not the first one. One global map cannot express "same label, different person" |
| 5 | 2026-11-07 CP-1 leftovers → T3.5 | Claude Code (Opus 5.5) | Recommended the proposer's `reasoning_effort: low` (D-027) from 3 synthetic episodes and wrote "no loss in clip validity". On real episodes, `low` gave 1 valid clip from 3 proposals (2 too short); the default setting gave 2 of 2 on the episode that ran both | The follow-up check written into D-027 itself (rerun on real episodes at T3.5 against the default) | Recommendation withdrawn in a D-027 update; config change left for Harshit at CP-2 | A cost setting tested on 3 short synthetic episodes says little about long real ones; write the real-data check into the decision, as was done here |
| 6 | 2026-11-07 T3.1 → T3.5 | Claude Code (Opus 5.5) | Chose a default proposer model (D-022) without confirming its free daily request quota, then spent 12 of that day's Gemini calls on experiments (6 effort comparison, 5 smoke incl. 1 repair, 1 grid). The quota is 20/day, too small for a 50-episode run | HTTP 429 with the quota details in the error body during the T3.5 grid | D-029: limits now read from provider responses (Gemini error body, Groq rate-limit headers); model plan pending Harshit | Check a model's quota against the full run's call count before making it the default; "verified with a 1-token call" proves the ID, not the capacity |

Examples of things worth logging:
- The alias map draft merged two different characters, or split one into two
- The runtime LLM returned a block ID that doesn't exist, or a hook block after the cliff block
- The judge rated a slow monologue highly (caught by blind human rating)
- Claude Code used an outdated LiteLLM or model name (caught by the 1-token test call)
- A test passed for the wrong reason
