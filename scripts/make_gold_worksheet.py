"""Print a gold-labelling worksheet: every block of the chosen episodes, plus empty answer slots.

Part of the gold-set workflow (EVAL_PLAN §1): Harshit reads this, writes his picks into the answer
slots, then runs scripts/gold_from_worksheet.py to turn them into gold/gold_labels.csv.
The worksheet is deliberately neutral: blocks in file order, nothing marked, ranked or suggested,
so the labels can't be anchored by the tool. Real-pack output belongs in private/ (git-ignored).
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from promo_finder.aliases import load_aliases  # noqa: E402
from promo_finder.compact import format_tc  # noqa: E402
from promo_finder.parse import Block, Episode, load_pack  # noqa: E402

CAMERA_MAX_CHARS = 70

RULES = """\
**Rules (6 lines)**
1. A promo is a 20–60 s clip.
2. hook = the line or action that grabs in the first 3 s (the clip starts at most 3 s before it).
3. cliff = the last unresolved moment; end the clip before the answer.
4. start / end = the first and last block of the clip (end may be the shot the cliff sits in).
5. quality: 3 = would post first, 2 = solid, 1 = usable. Write "none" if an episode has nothing promo-worthy.
6. Optional cross-episode arc, on its own line under any episode: `arc: E01:B010-B030 + E42:B005-B020 quality=_ note=`
"""

ANSWER_TEMPLATE = """\
### My picks for E{ep:02d}
- promo: start=B___ hook=B___ cliff=B___ end=B___ quality=_ note=
- promo: start=B___ hook=B___ cliff=B___ end=B___ quality=_ note=
- (write "none" if nothing is promo-worthy)
"""


def _short_id(block: Block) -> str:
    # "E03-B011" -> "B011": the episode is already in the section header.
    return block.id.split("-", 1)[1]


def block_line(block: Block) -> str:
    stamp = f"{_short_id(block)} {format_tc(block.start)}"
    text = " ".join(block.text.split())
    if block.type == "CAMERA":
        if len(text) > CAMERA_MAX_CHARS:
            text = text[:CAMERA_MAX_CHARS - 1].rstrip() + "…"
        return f"{stamp} cam: {text}"
    if block.type == "ACTION":
        return f"{stamp} ACT: {text}"
    if block.type == "SOUND_FX":
        return f"{stamp} SFX: {text}"
    who = (block.speaker or block.speaker_raw or "UNKNOWN").upper()
    if block.emotion:
        who += f" ({block.emotion})"
    if block.flags:
        who += " [" + ", ".join(block.flags) + "]"
    return f"{stamp} {who}: {text}"


def episode_section(ep: Episode) -> str:
    lines = [f"## E{ep.ep:02d} · duration {format_tc(ep.duration)}", "", f"**Logline:** {ep.logline}", "", "```"]
    scenes = {s.num: s for s in ep.scenes}
    current = None
    for block in ep.blocks:
        if block.scene != current and block.scene in scenes:
            s = scenes[block.scene]
            lines.append(f"--- SCENE {s.num} · {s.heading} · {format_tc(s.start)}–{format_tc(s.end)} ---")
            current = block.scene
        lines.append(block_line(block))
    lines += ["```", "", ANSWER_TEMPLATE.format(ep=ep.ep)]
    return "\n".join(lines)


def make_worksheet(episodes: list[Episode], wanted: list[int]) -> str:
    by_num = {e.ep: e for e in episodes}
    missing = [n for n in wanted if n not in by_num]
    if missing:
        raise ValueError(f"episodes not in the pack: {missing}")
    head = [f"# Gold worksheet: episodes {', '.join(str(n) for n in sorted(wanted))}", "",
            "Fill in only the answer blocks. Block IDs can be written as B11, B011 or E01-B011.", "", RULES]
    return "\n".join(head + [episode_section(by_num[n]) for n in sorted(wanted)])


def main() -> None:
    parser = argparse.ArgumentParser(description="Write a neutral gold-labelling worksheet.")
    parser.add_argument("--input", required=True, help="pack folder or .zip")
    parser.add_argument("--episodes", required=True, help="comma-separated episode numbers, e.g. 1,3,8")
    parser.add_argument("--aliases", default="config/aliases.yaml")
    parser.add_argument("--out", required=True, help="e.g. private/gold_worksheet.md (keep real-pack output private)")
    parser.add_argument("--force", action="store_true", help="overwrite an existing worksheet (it may hold your picks!)")
    args = parser.parse_args()

    out = Path(args.out)
    if out.exists() and not args.force:
        sys.exit(f"{out} already exists and may contain your picks; use --force to overwrite")
    aliases, _ = load_aliases(args.aliases)
    episodes, _ = load_pack(args.input, aliases)
    wanted = [int(x) for x in args.episodes.split(",") if x.strip()]
    text = make_worksheet(episodes, wanted)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(text, encoding="utf-8")
    blocks = sum(len(e.blocks) for e in episodes if e.ep in wanted)
    print(f"wrote {out}: {len(wanted)} episodes, {blocks} blocks")


if __name__ == "__main__":
    main()
