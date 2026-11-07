---
name: log-decision
description: Append a new entry to decisions.md in the project's ADR format. Use whenever a choice is made that the spec does not dictate (a threshold, a library behaviour, a prompt change, a scope cut, an assumption about unclear input), or when the user runs /log-decision.
---

Append one decision to `decisions.md`.

1. Read `decisions.md` and find the highest `D-0xx` number. The new ID is the next number.
2. Write the entry using the template at the top of `decisions.md`:
   - Date: today. Owner: `Claude` unless the user is stating their own decision, in which case `Harshit`.
   - Status: `Proposed` for Claude's own choices; `Accepted` only if the user said so explicitly.
   - Context, Decision, Alternatives (at least one, with why not), Consequences (cost and benefit, plus how it shows up in eval or the interview), Reversible?
3. Keep it to 6–10 lines. No show-specific script text or character names (decisions.md is committed to a public repo).
4. Append it below the `<!-- Claude Code: append new decisions below -->` marker, in ID order.
5. If the decision changes the spec, also note the affected TECH_SPEC/PRD section in Consequences. Don't edit the spec silently; mention it in the next report.md entry.
6. Reply with one line: `Logged D-0xx: <title> (Proposed)`.

Decision to log (if provided): $ARGUMENTS
