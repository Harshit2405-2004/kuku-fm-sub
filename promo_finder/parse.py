"""Parse episode script files into Episode / Scene / Block data with stable block IDs.

Pipeline position: stage 1 (code only). Everything later points at blocks by ID (`E01-B037`),
so IDs and times must be right. The parser is tolerant on purpose (any header casing, MM:SS or
HH:MM:SS, CRLF, missing optional parts): oddities become warnings, never crashes. Every
non-empty line is either used or reported as "unassigned", so nothing is dropped silently.
"""

from __future__ import annotations

import argparse
import json
import logging
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
    lines_total: int = 0        # non-empty lines in the file
    lines_unassigned: int = 0   # non-empty lines the parser could not place (target: 0)


# Labels that are not speakers. Anything else in **LABEL:** is treated as a speaker (DIALOGUE).
NON_DIALOGUE_LABELS = {"CAMERA": "CAMERA", "ACTION": "ACTION", "SOUND FX": "SOUND_FX", "SFX": "SOUND_FX"}
# Spelling variants writers use for the same flag -> one canonical flag.
FLAG_VARIANTS = {
    "O.S.": "O.S.", "O.S": "O.S.", "OS": "O.S.", "OFF-SCREEN": "O.S.", "OFF SCREEN": "O.S.",
    "V.O.": "V.O.", "V.O": "V.O.", "VO": "V.O.", "VOICE-OVER": "V.O.", "VOICE OVER": "V.O.",
    "O.C.": "O.C.", "O.C": "O.C.",
    "CONT'D": "CONT'D", "CONTD": "CONT'D",
}
# Real packs give block times to 0.01 s; allow a little slack before calling a block "outside its scene".
SCENE_TOLERANCE_S = 0.1

# Accepts **LABEL:** and the variant **LABEL**:
BLOCK_HEADER = re.compile(r"^\*\*(?P<label>[^*]+?)(?::\*\*|\*\*:)\s*$")
# Captures whatever is inside the parens, so a malformed time is reported instead of read as text.
TIME_LINE = re.compile(r"start:\s*\((?P<start>[^)]*)\)\s*\|\s*end:\s*\((?P<end>[^)]*)\)", re.IGNORECASE)
HEADER_KEY = re.compile(r"^(episode number|episode logline|continuity notes)\s*:\s*(.*)$", re.IGNORECASE)
ANY_HEADER_KEY = re.compile(r"^[A-Za-z][A-Za-z ]{0,40}:\s")   # e.g. "WRITTEN BY: ..."
SCENE_NUMBER = re.compile(r"^scene\s+(\d+)$", re.IGNORECASE)
SCENE_HEADING = re.compile(r"^scene heading\s*:\s*(.*)$", re.IGNORECASE)
SCENE_START = re.compile(r"scene start\s*:\s*(\S+)", re.IGNORECASE)
SCENE_END = re.compile(r"scene end\s*:\s*(\S+)", re.IGNORECASE)
ACTIONS_MARKER = re.compile(r"^actions and dialogue\s*:?$", re.IGNORECASE)
SCRIPT_START = re.compile(r"^-+\s*script start\s*-+$", re.IGNORECASE)
SCRIPT_END = re.compile(r"^-+\s*script end\s*-+$", re.IGNORECASE)
EP_FROM_FILENAME = re.compile(r"episode[-_ ]?0*(\d+)", re.IGNORECASE)


def parse_time(text: str) -> float:
    """'MM:SS(.fff)' or 'HH:MM:SS(.fff)' -> seconds. Raises ValueError on anything else."""
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
            flag = FLAG_VARIANTS.get(part.upper().replace("’", "'"))
            if flag:
                if flag not in flags:
                    flags.append(flag)
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


def _safe_time(text: str, where: str, warnings: list[str]) -> float | None:
    try:
        return parse_time(text)
    except ValueError:
        warnings.append(f"{where}: bad time {text.strip()!r}")
        return None


def _dialogue_text(text_lines: list[str]) -> tuple[str, bool]:
    """Strip the quotes around spoken text. Returns (text, was_quoted).

    Quotes are stripped per line first, so a line spoken across two quoted lines joins cleanly.
    """
    if text_lines and all(len(t) >= 2 and t[0] == '"' and t[-1] == '"' for t in text_lines):
        return " ".join(t[1:-1].strip() for t in text_lines), True
    joined = " ".join(text_lines)
    if len(joined) >= 2 and joined[0] == '"' and joined[-1] == '"':
        return joined[1:-1].strip(), True
    return joined, False


def _read_lines(lines: list[str]) -> dict:
    """First pass: walk the lines once and sort each non-empty one into headers, scenes, blocks,
    or "unassigned". No IDs or validation yet."""
    out = {"headers": {}, "scenes": [], "blocks": [], "unassigned": [], "warnings": [],
           "lines_total": 0, "has_marker": any(SCRIPT_START.match(l.strip()) for l in lines)}
    current_header = None   # header key whose value may wrap onto the next line
    in_script = False
    after_end = False
    pending = None          # the block being read

    def close_block():
        nonlocal pending
        if pending is not None:
            out["blocks"].append(pending)
        pending = None

    for lineno, line in enumerate(lines, start=1):
        s = line.strip()
        if not s:
            current_header = None
            if pending is not None and pending["text"]:
                pending["text_done"] = True   # a blank line ends the block's text
            continue
        out["lines_total"] += 1

        if after_end:
            out["unassigned"].append((lineno, s))
            continue
        if not in_script:
            if SCRIPT_START.match(s):
                in_script = True
                continue
            starts_script = SCENE_NUMBER.match(s) or BLOCK_HEADER.match(s)
            if out["has_marker"] or not starts_script:
                key = HEADER_KEY.match(s)
                if key:
                    current_header = key.group(1).lower()
                    out["headers"][current_header] = key.group(2).strip()
                elif ANY_HEADER_KEY.match(s):
                    current_header = None
                    out["warnings"].append(f"unknown header line {lineno}: {s[:60]}")
                    out["unassigned"].append((lineno, s))
                elif current_header:
                    out["headers"][current_header] += " " + s   # wrapped header value
                else:
                    out["unassigned"].append((lineno, s))
                continue
            in_script = True   # no marker: the first SCENE / block line starts the script

        if SCRIPT_END.match(s):
            close_block()
            after_end = True
            continue
        header = BLOCK_HEADER.match(s)
        if header:
            close_block()
            pending = {"label": header.group("label").strip(), "time_text": None, "text": [],
                       "text_done": False, "scene_idx": len(out["scenes"]) - 1}
            continue
        scene_num = SCENE_NUMBER.match(s)
        if scene_num:
            close_block()
            out["scenes"].append({"num": int(scene_num.group(1)), "heading": "", "start": None, "end": None,
                                  "start_text": None, "end_text": None})
            continue
        if pending is None:
            scene = out["scenes"][-1] if out["scenes"] else None
            heading, start, end = SCENE_HEADING.match(s), SCENE_START.search(s), SCENE_END.search(s)
            if scene is not None and (heading or start or end):
                if heading:
                    scene["heading"] = heading.group(1).strip()
                if start:
                    scene["start_text"] = start.group(1)
                if end:
                    scene["end_text"] = end.group(1)
            elif not ACTIONS_MARKER.match(s):
                out["unassigned"].append((lineno, s))
            continue
        times = TIME_LINE.search(s)
        if times and pending["time_text"] is None and not pending["text"]:
            pending["time_text"] = (times.group("start"), times.group("end"))
        elif pending["text_done"]:
            out["unassigned"].append((lineno, s))   # text after the block's blank-line end
        else:
            pending["text"].append(s)
    close_block()
    return out


def parse_episode_text(
    text: str, source_file: str, aliases: dict[str, str] | None = None
) -> tuple[Episode, list[str]]:
    """Parse one episode file's text. Returns the episode and a list of warnings."""
    lines = text.replace("\r\n", "\n").replace("\r", "\n").lstrip("﻿").split("\n")
    raw = _read_lines(lines)
    ep_num = _episode_number(raw["headers"].get("episode number"), source_file)
    tag = f"E{ep_num:02d}"
    warnings = [f"{tag} {w}" for w in raw["warnings"]]
    if not raw["has_marker"]:
        warnings.append(f"{tag}: no script start marker; script taken to start at the first SCENE/block line")

    # Blocks: assign IDs only to timed blocks, so every ID maps to a real time range (D-018).
    blocks: list[Block] = []
    block_scene_idx: list[int] = []
    for rb in raw["blocks"]:
        where = f"{tag} block {len(blocks) + 1} ({rb['label']})"
        if rb["time_text"] is None:
            warnings.append(f"{where}: missing times, block skipped")
            continue
        start = _safe_time(rb["time_text"][0], where, warnings)
        end = _safe_time(rb["time_text"][1], where, warnings)
        if start is None or end is None:
            warnings.append(f"{where}: block skipped")
            continue
        block_id = f"{tag}-B{len(blocks) + 1:03d}"
        label_upper = rb["label"].upper()
        speaker_raw = speaker = emotion = None
        flags: list[str] = []
        if label_upper in NON_DIALOGUE_LABELS:
            block_type = NON_DIALOGUE_LABELS[label_upper]
            text_value = " ".join(rb["text"])
        else:
            block_type = "DIALOGUE"
            speaker_raw, emotion, flags = parse_speaker_label(rb["label"])
            speaker = canonical_speaker(speaker_raw, aliases, ep_num)
            text_value, quoted = _dialogue_text(rb["text"])
            if not quoted:
                # Real dialogue is always quoted; an unquoted one is probably an unknown label.
                warnings.append(f"{block_id}: unquoted text under label '{rb['label']}', treated as DIALOGUE")
        if end < start:
            warnings.append(f"{block_id}: end < start ({end} < {start})")
        scene_num = raw["scenes"][rb["scene_idx"]]["num"] if rb["scene_idx"] >= 0 else 0
        blocks.append(Block(id=block_id, ep=ep_num, scene=scene_num, type=block_type,
                            speaker_raw=speaker_raw, speaker=speaker, emotion=emotion, flags=flags,
                            start=start, end=end, text=text_value))
        block_scene_idx.append(rb["scene_idx"])

    # Scenes: times, fallbacks, and the "outside its scene" check (by scene position, so a
    # duplicated scene number doesn't mix two scenes' blocks).
    scene_models: list[Scene] = []
    seen_nums: set[int] = set()
    for idx, s in enumerate(raw["scenes"]):
        if s["num"] in seen_nums:
            warnings.append(f"{tag}: duplicate scene number {s['num']}")
        seen_nums.add(s["num"])
        where = f"{tag} scene {s['num']}"
        start = _safe_time(s["start_text"], where, warnings) if s["start_text"] else None
        end = _safe_time(s["end_text"], where, warnings) if s["end_text"] else None
        in_scene = [b for b, i in zip(blocks, block_scene_idx) if i == idx]
        if start is None or end is None:
            warnings.append(f"{where}: missing start/end, taken from its blocks")
            start = start if start is not None else min((b.start for b in in_scene), default=0.0)
            end = end if end is not None else max((b.end for b in in_scene), default=0.0)
        scene_models.append(Scene(ep=ep_num, num=s["num"], heading=s["heading"], start=start, end=end))
        for b in in_scene:
            if b.start < start - SCENE_TOLERANCE_S or b.end > end + SCENE_TOLERANCE_S:
                warnings.append(f"{b.id}: outside scene {s['num']} range ({b.start}-{b.end} vs {start}-{end})")

    if not blocks:
        warnings.append(f"{tag}: 0 blocks parsed")
    if not any(b.type == "DIALOGUE" for b in blocks):
        warnings.append(f"{tag}: episode has no dialogue")
    for lineno, s in raw["unassigned"]:
        warnings.append(f"{tag} unassigned line {lineno}: {s[:60]}")

    duration = max([b.end for b in blocks] + [s.end for s in scene_models] + [0.0])
    episode = Episode(ep=ep_num, source_file=source_file, logline=raw["headers"].get("episode logline", ""),
                      continuity=raw["headers"].get("continuity notes", ""), duration=duration,
                      scenes=scene_models, blocks=blocks,
                      lines_total=raw["lines_total"], lines_unassigned=len(raw["unassigned"]))
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
        "lines_total": sum(e.lines_total for e in episodes),
        "lines_unassigned": sum(e.lines_unassigned for e in episodes),
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
    print(f"line coverage: {stats['lines_total'] - stats['lines_unassigned']}/{stats['lines_total']} "
          f"non-empty lines placed, {stats['lines_unassigned']} unassigned (target 0)")
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
