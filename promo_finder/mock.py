"""Mock mode (--mock): deterministic canned LLM replies, so the whole pipeline runs with no API key.

Pipeline position: llm.call_llm returns these instead of calling a model. Replies are built from the
compact block lines inside the prompt, so they always reference real block IDs and validate like a
real reply. Used by tests and by the demo app when no key is available.
"""

from __future__ import annotations

import json
import re

# One compact line: [E03-B011 00:13.0–00:14.8] MARA (Stunned): "You sold the house?"
LINE = re.compile(r"^\[(?P<id>E\d+-B\d+) (?P<start>\d+:\d+\.\d)–(?P<end>\d+:\d+\.\d)\] (?P<who>[^:]+): (?P<text>.*)$")
NON_DIALOGUE = {"CAM", "ACT", "SFX"}


def _seconds(tc: str) -> float:
    minutes, seconds = tc.split(":")
    return int(minutes) * 60 + float(seconds)


def _lines(messages: list[dict]) -> list[dict]:
    text = messages[-1]["content"] if messages else ""
    out = []
    for line in text.splitlines():
        m = LINE.match(line.strip())
        if m:
            out.append({"id": m["id"], "start": _seconds(m["start"]), "end": _seconds(m["end"]),
                        "dialogue": m["who"] not in NON_DIALOGUE, "text": m["text"]})
    return out


def mock_proposer(messages: list[dict]) -> dict:
    """Hook = first questioning/exclaiming line (else any line) that has a later line 15–45 s after it
    to cut on; cliff = the last such line. Simple, deterministic, and always buildable."""
    text = messages[-1]["content"] if messages else ""
    ep_match = re.search(r"EPISODE (\d+)", text)
    episode = int(ep_match.group(1)) if ep_match else 0
    dialogue = [l for l in _lines(messages) if l["dialogue"]]
    punchy = [l for l in dialogue if "?" in l["text"] or "!" in l["text"]]
    for hook in punchy + dialogue:
        later = [l for l in dialogue if hook["start"] + 15 <= l["start"] <= hook["start"] + 45]
        if later:
            cliff = later[-1]
            return {"episode": episode, "candidates": [{
                "reasoning": "mock: first punchy line, cut on the last line 15–45 s later",
                "start_block": hook["id"], "hook_block": hook["id"], "cliff_block": cliff["id"],
                "end_block": cliff["id"], "beat_type": "other",
                "hook_summary": hook["text"][:80], "cliff_summary": cliff["text"][:80]}]}
    return {"episode": episode, "candidates": []}


CLIP_HEADER = re.compile(r"^CLIP (?P<id>\S+) ·")


def mock_judge(messages: list[dict]) -> dict:
    """Score each clip in the prompt: hook 4 if a `>>` line has ? or !, else 2; the rest fixed.
    Deterministic, so ranking tests and the demo give the same order every time."""
    text = messages[-1]["content"] if messages else ""
    scores, current = [], None
    for line in text.splitlines() + ["CLIP END ·"]:
        header = CLIP_HEADER.match(line)
        if header:
            if current:
                scores.append(current)
            current = None if header["id"] == "END" else {
                "id": header["id"], "hook_text": "none", "cliff_text": "", "reasons": "mock judge",
                "hook": 2, "cliff": 3, "standalone": 3, "trope_pull": 3, "pacing": 3,
                "why": "mock score", "risk_flags": []}
        elif current and LINE.match(line.removeprefix(">> ").strip()):
            body = LINE.match(line.removeprefix(">> ").strip())["text"]
            if line.startswith(">> ") and ("?" in body or "!" in body):
                current["hook"], current["hook_text"] = 4, body[:80]
            current["cliff_text"] = body[:80]
    return {"scores": scores}


ARC_LINE = re.compile(r"^(?P<id>\S+) \| episode (?P<ep>\d+) \|")


def mock_arcs(messages: list[dict]) -> dict:
    """Pair the first candidate of the earliest episode with the first of the latest episode."""
    text = messages[-1]["content"] if messages else ""
    firsts: dict[int, str] = {}
    for line in text.splitlines():
        m = ARC_LINE.match(line.strip())
        if m:
            firsts.setdefault(int(m["ep"]), m["id"])
    if len(firsts) < 2:
        return {"arcs": []}
    eps = sorted(firsts)
    return {"arcs": [{"reasoning": "mock: earliest opener, latest closer", "opener": firsts[eps[0]],
                      "closer": firsts[eps[-1]], "hook_summary": "mock hook", "cliff_summary": "mock cliff"}]}


def respond(stage: str, messages: list[dict]) -> str:
    """Return the raw JSON text a model would have returned for this stage."""
    if stage == "proposer":
        return json.dumps(mock_proposer(messages))
    if stage == "judge":
        return json.dumps(mock_judge(messages))
    if stage == "arc":
        return json.dumps(mock_arcs(messages))
    raise NotImplementedError(f"mock reply for stage '{stage}' not built yet")
