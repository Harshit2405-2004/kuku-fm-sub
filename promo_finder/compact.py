"""Compact view: one line per block, the text the LLM stages read.

Pipeline position: between parse.py and the LLM stages (propose, arcs, judge). The model sees
block IDs *and* times so it can reason about length, but it may only answer with IDs (D-002).
Run as a CLI to print one episode, or a token table for the whole pack.
"""

from __future__ import annotations

import argparse
import math
from pathlib import Path

from promo_finder.aliases import load_aliases
from promo_finder.parse import Block, Episode, load_pack

TYPE_PREFIX = {"CAMERA": "CAM", "ACTION": "ACT", "SOUND_FX": "SFX"}


def format_tc(seconds: float) -> str:
    """Seconds -> 'MM:SS.s', rounded half up to the nearest tenth.

    Works in whole tenths so 59.96 s becomes 01:00.0, not 00:60.0. Python's round() rounds
    halves to even (0.25 -> 0.2), so we add 0.5 and floor instead; the tiny epsilon absorbs
    float error such as 1.25 * 10 = 12.499999...
    """
    tenths = math.floor(seconds * 10 + 0.5 + 1e-9)
    minutes, rest = divmod(tenths, 600)
    return f"{minutes:02d}:{rest / 10:04.1f}"


def compact_block(block: Block) -> str:
    stamp = f"[{block.id} {format_tc(block.start)}–{format_tc(block.end)}]"
    if block.type in TYPE_PREFIX:
        return f"{stamp} {TYPE_PREFIX[block.type]}: {block.text}"
    who = (block.speaker or block.speaker_raw or "UNKNOWN").upper()
    if block.emotion:
        who += f" ({block.emotion})"
    if block.flags:
        who += " [" + ", ".join(block.flags) + "]"
    return f'{stamp} {who}: "{block.text}"'


def compact_episode(ep: Episode, cast: dict[str, str] | None = None) -> str:
    """Header lines (episode, logline, continuity, optional cast) then scenes and blocks in file order."""
    lines = [f"EPISODE {ep.ep} · duration {format_tc(ep.duration)}",
             f"LOGLINE: {ep.logline}",
             f"CONTINUITY: {ep.continuity}"]
    if cast:
        lines.append("CAST: " + "; ".join(f"{name} ({role})" for name, role in cast.items()))
    scenes = {s.num: s for s in ep.scenes}
    current_scene = None
    for block in ep.blocks:
        if block.scene != current_scene and block.scene in scenes:
            s = scenes[block.scene]
            lines.append(f"## SCENE {s.num} · {s.heading} · {format_tc(s.start)}–{format_tc(s.end)}")
            current_scene = block.scene
        lines.append(compact_block(block))
    return "\n".join(lines)


def estimate_tokens(text: str) -> int:
    """Rough token count (~4 characters per token for English). Good enough for budgeting."""
    return len(text) // 4


def main() -> None:
    parser = argparse.ArgumentParser(description="Print an episode's compact view, or a token table.")
    parser.add_argument("--input", required=True, help="pack folder or .zip")
    parser.add_argument("--aliases", default="config/aliases.yaml")
    parser.add_argument("--ep", type=int, help="episode number to print")
    parser.add_argument("--tokens", action="store_true", help="print estimated tokens per episode")
    args = parser.parse_args()
    if args.ep is None and not args.tokens:
        parser.error("give --ep N and/or --tokens")

    aliases, cast = load_aliases(Path(args.aliases))
    episodes, _ = load_pack(args.input, aliases)
    if args.ep is not None:
        match = [e for e in episodes if e.ep == args.ep]
        if not match:
            raise SystemExit(f"episode {args.ep} not found")
        print(compact_episode(match[0], cast))
    if args.tokens:
        total = 0
        print("ep | blocks | chars | est_tokens")
        for e in episodes:
            text = compact_episode(e, cast)
            total += estimate_tokens(text)
            print(f"{e.ep:2d} | {len(e.blocks):6d} | {len(text):5d} | {estimate_tokens(text):6d}")
        print(f"total est_tokens: {total}")


if __name__ == "__main__":
    main()
