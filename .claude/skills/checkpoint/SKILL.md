---
name: checkpoint
description: Stop at a PLAN.md checkpoint (CP-1 … CP-6), run the phase review, and write a checkpoint summary to report.md for Harshit's approval. Use when a phase's tasks are complete, or when the user runs /checkpoint.
disable-model-invocation: false
---

You've reached a checkpoint. Do the following, in order, and then **stop and wait** for Harshit.

1. Identify the checkpoint from `docs/PLAN.md` (argument if given: $ARGUMENTS).
2. Confirm that every task in the phase has a report.md entry. Write any missing ones now, with real command output.
3. Run `pytest -q` and capture the summary.
4. Run the `independent-reviewer` subagent on this phase's diff. At CP-6, run `brief-auditor` instead. Fix all **Blocking** findings, then re-run the reviewer once. Leave "Should fix" items for Harshit to decide on.
5. Update the status board at the top of `report.md`.
6. Append a **Checkpoint entry** (template in report.md) with:
   - Summary for Harshit: what's built, with key numbers from real runs
   - Please review: the exact files, sections or output rows he should look at, and what to look for (from the CP-x row in PLAN.md)
   - Proposed decisions awaiting approval: the D-0xx list
   - Reviewer verdict and what was fixed
7. Commit: `CP-<n>: checkpoint summary`.
8. Print the checkpoint summary to the chat and end with: **"Waiting for your go-ahead (or changes) before Phase <n+1>."** Don't start the next phase.
