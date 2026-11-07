"""Proposer stage: one LLM call per episode that returns promo candidates as block IDs only.

Pipeline position: stage 2, after parse/compact and before build.py. The model sees the compact view
(IDs + times) and answers with IDs (D-002). Code checks every ID exists in this episode and is in a
sensible order; bad candidates get one repair round, then are dropped and logged (TECH_SPEC §4.2).
"""

from __future__ import annotations

from pathlib import Path
from typing import Callable, Literal

from pydantic import BaseModel, Field

from promo_finder.compact import compact_episode
from promo_finder.llm import call_llm, load_prompt
from promo_finder.parse import Episode

BeatType = Literal["slap_or_violence", "humiliation", "betrayal_reveal", "identity_reveal", "threat_ultimatum",
                   "rescue", "proposal_or_romance", "accusation_or_framing", "death_or_danger", "twist", "other"]


class ProposalCandidate(BaseModel):
    reasoning: str        # first, so the model explains before it commits to IDs
    start_block: str
    hook_block: str
    cliff_block: str
    end_block: str
    beat_type: BeatType
    hook_summary: str
    cliff_summary: str


class EpisodeProposals(BaseModel):
    episode: int
    candidates: list[ProposalCandidate] = Field(default_factory=list, max_length=4)


def build_messages(ep: Episode, cast: dict[str, str] | None, prompt_name: str = "proposer") -> list[dict]:
    _version, sections = load_prompt(prompt_name)
    # str.replace, not str.format: script text can contain braces.
    user = sections["user"].replace("{episode}", str(ep.ep)).replace("{compact}", compact_episode(ep, cast))
    return [{"role": "system", "content": sections["system"]}, {"role": "user", "content": user}]


def validate_proposals(ep: Episode, proposals: EpisodeProposals) -> dict[int, str]:
    """Map candidate index -> problem. Index -1 is an episode-level problem."""
    by_id = {b.id: b for b in ep.blocks}
    errors: dict[int, str] = {}
    if proposals.episode != ep.ep:
        errors[-1] = f"episode is {proposals.episode}, expected {ep.ep}"
    for i, c in enumerate(proposals.candidates):
        ids = {"start_block": c.start_block, "hook_block": c.hook_block,
               "cliff_block": c.cliff_block, "end_block": c.end_block}
        missing = [f"{k}={v}" for k, v in ids.items() if v not in by_id]
        if missing:
            errors[i] = f"unknown block ID(s) for episode {ep.ep}: {', '.join(missing)}"
            continue
        start, hook, cliff, end = (by_id[v] for v in ids.values())
        # end_block may be the shot the cliff sits in, which starts before the cliff line,
        # so it is checked by where it ends, not where it starts.
        if not (start.start <= hook.start <= cliff.start and end.end >= cliff.end):
            errors[i] = (f"bad order: need start ≤ hook ≤ cliff in time and end_block ending at or after the cliff "
                         f"(got {c.start_block}, {c.hook_block}, {c.cliff_block}, {c.end_block})")
    return errors


def _save_raw(raw_dir: Path | None, name: str, raw: str) -> None:
    if raw_dir is not None:
        Path(raw_dir).mkdir(parents=True, exist_ok=True)
        (Path(raw_dir) / name).write_text(raw, encoding="utf-8")   # unedited, as the model sent it


def propose_episode(ep: Episode, cast: dict[str, str] | None, cfg: dict, usage: list[dict],
                    raw_dir: Path | None = None, completion_fn: Callable | None = None,
                    prompt_name: str = "proposer") -> tuple[EpisodeProposals, list[dict]]:
    """Returns (valid proposals, dropped candidates with reasons)."""
    version, _ = load_prompt(prompt_name)
    messages = build_messages(ep, cast, prompt_name)
    proposals, raw = call_llm("proposer", messages, EpisodeProposals, cfg, version, usage, completion_fn=completion_fn)
    _save_raw(raw_dir, f"E{ep.ep:02d}.json", raw)

    errors = validate_proposals(ep, proposals)
    if errors:
        problems = "\n".join(f"- candidate {i}: {e}" if i >= 0 else f"- {e}" for i, e in sorted(errors.items()))
        repair = messages + [
            {"role": "assistant", "content": raw},
            {"role": "user", "content": f"Some candidates have problems:\n{problems}\n"
                                        f"Use only block IDs from episode {ep.ep} as listed. Reply with the full corrected JSON."},
        ]
        proposals, raw = call_llm("proposer", repair, EpisodeProposals, cfg, version, usage, completion_fn=completion_fn)
        _save_raw(raw_dir, f"E{ep.ep:02d}.repair.json", raw)
        errors = validate_proposals(ep, proposals)

    # After the repair round, drop what is still broken; a wrong episode field alone is harmless
    # because every ID was already checked against this episode.
    dropped = [{"ep": ep.ep, "index": i, "error": e, "candidate": proposals.candidates[i].model_dump()}
               for i, e in sorted(errors.items()) if i >= 0]
    keep = [c for i, c in enumerate(proposals.candidates) if i not in errors]
    return EpisodeProposals(episode=ep.ep, candidates=keep), dropped
