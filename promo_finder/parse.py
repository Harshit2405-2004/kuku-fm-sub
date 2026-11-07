"""Parse episode script files into Episode / Scene / Block data with stable block IDs.

Pipeline position: stage 1 (code only). Everything later points at blocks by ID (`E01-B037`),
so IDs and times must be right. The parser is tolerant on purpose (any header casing, MM:SS or
HH:MM:SS, CRLF, missing optional parts): oddities become warnings, never crashes.
"""

from __future__ import annotations

import argparse
import logging
import json
import re
import zipfile
from collections import Counter
from pathlib import Path
from typing import Literal

from pydantic import BaseModel

from promo_finder.aliases import canonical_speaker, load_aliases

BlockType = Literal["CAMERA", "ACTION", "SOUND_FX", "DIALOGUE"]


class Block(BaseModel):
    id: str              # "E01-B037"
    ep: int
    scene: int
    type: BlockType
    speaker_raw: str | None = None
    speaker: str | None = None   # canonical, after aliases
    emotion: str | None = None
    flags: list[str] = []        # O.S., V.O., O.C., CONT'D
    start: float                 # seconds from episode start
    end: float
    text: str


class Scene(BaseModel):
    ep: int
    num: int
    heading: str
    start: float
    end: float


class Episode(BaseModel):
    ep: int
    source_file: str
    logline: str
    continuity: str
    duration: float
    scenes: list[Scene]
    blocks: list[Block]


# Labels that are not speakers. Anything else in **LABEL:** is treated as a speaker (DIALOGUE).
NON_DIALOGUE_LABELS = {"CAMERA": "CAMERA", "ACTION": "ACTION", "SOUND FX": "SOUND_FX", "SFX": "SOUND_FX"}
SPEAKER_FLAGS = {"O.S.", "V.O.", "O.C.", "CONT'D"}
# Real packs give block times to 0.01 s; allow a little slack before calling a block "outside its scene".
SCENE_TOLERANCE_S = 0.1

BLOCK_HEADER = re.compile(r"^\*\*(?P<label>[^*]+?):\*\*\s*$")
TIME_LINE = re.compile(
    r"start:\s*\(\s*(?P<start>[\d:.]+)\s*\)\s*\|\s*end:\s*\(\s*(?P<end>[\d:.]+)\s*\)", re.IGNORECASE
)
HEADER_KEY = re.compile(r"^\s*(episode number|episode logline|continuity notes)\s*:\s*(.*)$", re.IGNORECASE)
SCENE_NUMBER = re.compile(r"^\s*scene\s+(\d+)\s*$", re.IGNORECASE)
SCENE_HEADING = re.compile(r"^\s*scene heading\s*:\s*(.*)$", re.IGNORECASE)
SCENE_START = re.compile(r"scene start\s*:\s*([\d:.]+)", re.IGNORECASE)
SCENE_END = re.compile(r"scene end\s*:\s*([\d:.]+)", re.IGNORECASE)
SCRIPT_START = re.compile(r"^\s*-+\s*script start\s*-+\s*$", re.IGNORECASE)
SCRIPT_END = re.compile(r"^\s*-+\s*script end\s*-+\s*$", re.IGNORECASE)
EP_FROM_FILENAME = re.compile(r"episode[-_ ]?0*(\d+)", re.IGNORECASE)


def parse_time(text: str) -> float:
    """'MM:SS(.fff)' or 'HH:MM:SS(.fff)' -> seconds."""
    parts = text.strip().split(":")
    if len(parts) == 2:
        minutes, seconds = parts
        return int(minutes) * 60 + float(seconds)
    if len(parts) == 3:
        hours, minutes, seconds = parts
        return int(hours) * 3600 + int(minutes) * 60 + float(seconds)
    raise ValueError(f"unrecognised time {text!r}")


def parse_speaker_label(label: str) -> tuple[str, str | None, list[str]]:
    """'VERA (O.S. / Low, Threatening)' -> ('VERA', 'Low, Threatening', ['O.S.']).

    Flags like O.S. can sit in their own parens or inside the emotion parens, so every
    comma- or slash-separated part of every paren group is checked.
    """
    name = label.split("(", 1)[0].strip()
    emotions: list[str] = []
    flags: list[str] = []
    for group in re.findall(r"\(([^)]*)\)", label):
        for part in re.split(r"[,/]", group):
            part = part.strip()
            if not part:
                continue
            if part.upper() in SPEAKER_FLAGS:
                if part.upper() not in flags:
                    flags.append(part.upper())
            else:
                emotions.append(part)
    return name, (", ".join(emotions) or None), flags


def _episode_number(header_value: str | None, source_file: str) -> int:
    if header_value:
        digits = re.search(r"\d+", header_value)
        if digits:
            return int(digits.group())
    from_name = EP_FROM_FILENAME.search(source_file)
    if from_name:
        return int(from_name.group(1))
    raise ValueError(f"{source_file}: no episode number in header or filename")


def parse_episode_text(
    text: str, source_file: str, aliases: dict[str, str] | None = None
) -> tuple[Episode, list[str]]:
    """Parse one episode file's text. Returns the episode and a list of warnings."""
    lines = text.replace("\r\n", "\n").replace("\r", "\n").lstrip("﻿").split("\n")
    warnings: list[str] = []
    headers: dict[str, str] = {}
    scenes: list[dict] = []
    raw_blocks: list[dict] = []   # blocks before IDs are assigned
    current_header = None
    in_script = False
    pending: dict | None = None   # the block being read

    def close_block():
        nonlocal pending
        if pending is not None:
            raw_blocks.append(pending)
        pending = None

    for line in lines:
        stripped = line.strip()
        if not in_script:
            if SCRIPT_START.match(stripped):
                in_script = True
                continue
            key_match = HEADER_KEY.match(line)
            if key_match:
                current_header = key_match.group(1).lower()
                headers[current_header] = key_match.group(2).strip()
            elif stripped and current_header:
                # A header value that wraps onto the next line.
                headers[current_header] += " " + stripped
            elif not stripped:
                current_header = None
            continue

        if SCRIPT_END.match(stripped):
            break
        header = BLOCK_HEADER.match(stripped)
        if header:
            close_block()
            pending = {"label": header.group("label").strip(), "times": None, "text": [],
                       "scene": scenes[-1]["num"] if scenes else 0, "text_done": False}
            continue
        if SCENE_NUMBER.match(stripped):
            close_block()
            scenes.append({"num": int(SCENE_NUMBER.match(stripped).group(1)), "heading": "",
                           "start": None, "end": None})
            continue
        if scenes and pending is None:
            heading = SCENE_HEADING.match(stripped)
            if heading:
                scenes[-1]["heading"] = heading.group(1).strip()
            if SCENE_START.search(stripped):
                scenes[-1]["start"] = parse_time(SCENE_START.search(stripped).group(1))
            if SCENE_END.search(stripped):
                scenes[-1]["end"] = parse_time(SCENE_END.search(stripped).group(1))
            continue
        if pending is None:
            continue  # e.g. "Actions and dialogue:"
        times = TIME_LINE.search(stripped)
        if times and pending["times"] is None and not pending["text"]:
            pending["times"] = (parse_time(times.group("start")), parse_time(times.group("end")))
        elif not stripped:
            # A blank line ends the block's text (but blank lines before any text are padding).
            if pending["text"]:
                pending["text_done"] = True
        elif not pending["text_done"]:
            pending["text"].append(stripped)
    close_block()

    ep_num = _episode_number(headers.get("episode number"), source_file)
    blocks: list[Block] = []
    for raw in raw_blocks:
        label_desc = f"block {len(blocks) + 1} ({raw['label']})"
        if raw["times"] is None:
            warnings.append(f"E{ep_num:02d} {label_desc}: missing times, block skipped")
            continue
        block_id = f"E{ep_num:02d}-B{len(blocks) + 1:03d}"
        text_value = " ".join(raw["text"])
        label_upper = raw["label"].upper()
        speaker_raw = speaker = emotion = None
        flags: list[str] = []
        if label_upper in NON_DIALOGUE_LABELS:
            block_type = NON_DIALOGUE_LABELS[label_upper]
        else:
            block_type = "DIALOGUE"
            speaker_raw, emotion, flags = parse_speaker_label(raw["label"])
            speaker = canonical_speaker(speaker_raw, aliases)
            if len(text_value) >= 2 and text_value[0] == '"' and text_value[-1] == '"':
                text_value = text_value[1:-1].strip()
            else:
                # Real dialogue is always quoted; an unquoted one is probably an unknown label.
                warnings.append(f"{block_id}: unquoted text under label '{raw['label']}', treated as DIALOGUE")
        start, end = raw["times"]
        if end < start:
            warnings.append(f"{block_id}: end < start ({end} < {start})")
        blocks.append(Block(id=block_id, ep=ep_num, scene=raw["scene"], type=block_type,
                            speaker_raw=speaker_raw, speaker=speaker, emotion=emotion, flags=flags,
                            start=start, end=end, text=text_value))

    scene_models: list[Scene] = []
    for s in scenes:
        in_scene = [b for b in blocks if b.scene == s["num"]]
        if s["start"] is None or s["end"] is None:
            warnings.append(f"E{ep_num:02d} scene {s['num']}: missing start/end, taken from its blocks")
            s["start"] = s["start"] if s["start"] is not None else min((b.start for b in in_scene), default=0.0)
            s["end"] = s["end"] if s["end"] is not None else max((b.end for b in in_scene), default=0.0)
        scene_models.append(Scene(ep=ep_num, num=s["num"], heading=s["heading"], start=s["start"], end=s["end"]))
        for b in in_scene:
            if b.start < s["start"] - SCENE_TOLERANCE_S or b.end > s["end"] + SCENE_TOLERANCE_S:
                warnings.append(f"{b.id}: outside scene {s['num']} range "
                                f"({b.start}-{b.end} vs {s['start']}-{s['end']})")

    if not any(b.type == "DIALOGUE" for b in blocks):
        warnings.append(f"E{ep_num:02d}: episode has no dialogue")

    duration = max([b.end for b in blocks] + [s.end for s in scene_models] + [0.0])
    episode = Episode(ep=ep_num, source_file=source_file, logline=headers.get("episode logline", ""),
                      continuity=headers.get("continuity notes", ""), duration=duration,
                      scenes=scene_models, blocks=blocks)
    return episode, warnings


def _read_pack_files(path: Path) -> list[tuple[str, str]]:
    """(file name, text) for every .txt episode file in a folder (recursive) or a .zip."""
    if path.is_file() and path.suffix.lower() == ".zip":
        files = []
        with zipfile.ZipFile(path) as zf:
            for name in zf.namelist():
                if name.lower().endswith(".txt") and "__MACOSX" not in name:
                    files.append((Path(name).name, zf.read(name).decode("utf-8-sig", errors="replace")))
        return files
    if path.is_dir():
        return [(p.name, p.read_text(encoding="utf-8-sig", errors="replace")) for p in sorted(path.rglob("*.txt"))]
    raise ValueError(f"{path}: not a folder or .zip")


def load_pack(path: Path | str, aliases: dict[str, str] | None = None) -> tuple[list[Episode], list[str]]:
    """Parse every episode in a pack, sorted by episode number. Returns (episodes, warnings)."""
    files = _read_pack_files(Path(path))
    if not files:
        raise ValueError(f"{path}: no episode .txt files found")
    episodes: list[Episode] = []
    warnings: list[str] = []
    for name, text in files:
        episode, ep_warnings = parse_episode_text(text, name, aliases)
        episodes.append(episode)
        warnings.extend(f"{name}: {w}" for w in ep_warnings)
    episodes.sort(key=lambda e: e.ep)
    seen: set[int] = set()
    for e in episodes:
        if e.ep in seen:
            warnings.append(f"duplicate episode number {e.ep} ({e.source_file})")
        seen.add(e.ep)
    return episodes, warnings


def pack_stats(episodes: list[Episode]) -> dict:
    """Summary numbers for a parsed pack (printed by the CLI, checked at CP-1)."""
    durations = [e.duration for e in episodes]
    blocks = [b for e in episodes for b in e.blocks]
    return {
        "episodes": len(episodes),
        "blocks": len(blocks),
        "blocks_by_type": dict(Counter(b.type for b in blocks)),
        "scenes": sum(len(e.scenes) for e in episodes),
        "duration_min": min(durations),
        "duration_max": max(durations),
        "duration_total": round(sum(durations), 2),
        "raw_speakers": dict(Counter(b.speaker_raw for b in blocks if b.type == "DIALOGUE")),
        "speakers": dict(Counter(b.speaker for b in blocks if b.type == "DIALOGUE")),
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Parse a script pack and print its stats.")
    parser.add_argument("--input", required=True, help="pack folder or .zip")
    parser.add_argument("--aliases", default="config/aliases.yaml", help="alias map (optional)")
    parser.add_argument("--out", help="write episodes JSON here")
    parser.add_argument("--speakers", action="store_true", help="also list raw speaker labels")
    args = parser.parse_args()
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")

    aliases, _cast = load_aliases(args.aliases)
    episodes, warnings = load_pack(args.input, aliases)
    stats = pack_stats(episodes)
    print(f"episodes: {stats['episodes']}  scenes: {stats['scenes']}  blocks: {stats['blocks']}")
    print("blocks by type:", stats["blocks_by_type"])
    print(f"duration: min {stats['duration_min']:.1f}s  max {stats['duration_max']:.1f}s  "
          f"total {stats['duration_total'] / 60:.1f} min")
    print(f"distinct raw speakers: {len(stats['raw_speakers'])}  canonical: {len(stats['speakers'])}")
    print(f"warnings: {len(warnings)}")
    for w in warnings:
        print("  ", w)
    if args.speakers:
        for name, count in sorted(stats["raw_speakers"].items(), key=lambda kv: -kv[1]):
            print(f"  {count:4d}  {name}")
    if args.out:
        out = Path(args.out)
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(json.dumps([e.model_dump() for e in episodes], indent=1), encoding="utf-8")
        print("wrote", out)


if __name__ == "__main__":
    main()
