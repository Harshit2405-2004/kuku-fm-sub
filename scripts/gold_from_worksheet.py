"""Turn Harshit's filled gold worksheet into gold/gold_labels.csv (EVAL_PLAN §1 format).

Part of the gold-set workflow: scripts/make_gold_worksheet.py writes the worksheet, Harshit fills in
the answer slots, and this script looks up block times in the parsed pack so no time is typed by hand.
Hard errors (unknown IDs, wrong order, missing quality) stop it before anything is written; a length
outside 20–60 s is only a warning, because the human label is the ground truth.
"""

from __future__ import annotations

import argparse
import csv
import re
import sys
from dataclasses import dataclass, field
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from promo_finder.compact import format_tc  # noqa: E402
from promo_finder.parse import Block, Episode, load_pack  # noqa: E402

MIN_S, MAX_S = 20.0, 60.0
CSV_COLUMNS = ["gold_id", "episode", "segments", "hook_block", "cliff_block", "quality", "notes"]

SECTION = re.compile(r"^###\s*My picks for E(\d+)\s*$", re.IGNORECASE)
PROMO = re.compile(r"^\s*-?\s*promo:\s*(.*)$", re.IGNORECASE)
ARC = re.compile(r"^\s*-?\s*arc:\s*(.*)$", re.IGNORECASE)
NONE = re.compile(r"^\s*-?\s*none\b\s*(?:note=)?(.*)$", re.IGNORECASE)
# key=value pairs; note= swallows the rest of the line so notes can contain spaces and "=".
FIELD = re.compile(r"(start|hook|cliff|end|quality)\s*=\s*(\S+)", re.IGNORECASE)
NOTE = re.compile(r"\bnote\s*=\s*(.*)$", re.IGNORECASE)
ARC_SEGMENT = re.compile(r"^E(\d+)\s*:\s*(\S+?)\s*-\s*(\S+)$", re.IGNORECASE)
ARC_POINT = re.compile(r"(hook|cliff)\s*=\s*E(\d+)\s*:\s*(\S+)", re.IGNORECASE)


@dataclass
class Result:
    rows: list[dict] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    per_episode: dict[int, dict[str, int]] = field(default_factory=dict)


def full_id(ep: int, text: str) -> str | None:
    """'B11', 'B011', '11' or 'E01-B011' -> 'E01-B011'; None if it isn't a block ID."""
    m = re.fullmatch(r"(?:E(\d+)-)?B?(\d+)", text.strip(), re.IGNORECASE)
    if not m:
        return None
    return f"E{int(m.group(1) or ep):02d}-B{int(m.group(2)):03d}"


def _note(text: str) -> str:
    m = NOTE.search(text)
    return m.group(1).strip() if m else ""


def _quality(raw: str | None, where: str, result: Result) -> int | None:
    if raw is None or not raw.isdigit() or int(raw) not in (1, 2, 3):
        result.errors.append(f"{where}: quality must be 1, 2 or 3 (got {raw!r})")
        return None
    return int(raw)


def _segment(start: Block, end: Block) -> tuple[int, float, float]:
    return start.ep, start.start, end.end


def _fmt_segments(segments: list[tuple[int, float, float]]) -> str:
    return ";".join(f"E{ep:02d} {format_tc(a)}-{format_tc(b)}" for ep, a, b in segments)


def _check_length(segments: list[tuple[int, float, float]], where: str, result: Result) -> None:
    total = sum(b - a for _, a, b in segments)
    if not MIN_S - 1e-6 <= total <= MAX_S + 1e-6:
        result.warnings.append(f"{where}: length {total:.1f} s is outside 20–60 s")


def _count(result: Result, ep: int, kind: str) -> None:
    result.per_episode.setdefault(ep, {"promo": 0, "arc": 0, "none": 0})[kind] += 1


def _parse_promo(ep: int, text: str, where: str, blocks: dict[str, Block], result: Result) -> dict | None:
    fields = {k.lower(): v for k, v in FIELD.findall(text.split("note=")[0])}
    ids = {k: fields.get(k, "") for k in ("start", "hook", "cliff", "end")}
    if all("_" in v or not v for v in ids.values()):
        return None  # untouched template line
    resolved = {}
    for key, raw in ids.items():
        bid = full_id(ep, raw) if raw and "_" not in raw else None
        if bid is None:
            result.errors.append(f"{where}: {key}={raw or '(missing)'} is not a block ID")
        elif bid not in blocks:
            result.errors.append(f"{where}: {key}={bid} does not exist")
        elif blocks[bid].ep != ep:
            result.errors.append(f"{where}: {key}={bid} is not in episode {ep}")
        else:
            resolved[key] = blocks[bid]
    quality = _quality(fields.get("quality"), where, result)
    if len(resolved) < 4 or quality is None:
        return None
    s, h, c, e = resolved["start"], resolved["hook"], resolved["cliff"], resolved["end"]
    # By time, not ID: real scripts list some lines before the shot they sit under. The end block
    # may be the shot holding the cliff, which starts before it, so it is checked by its end (D-025).
    if not (s.start <= h.start <= c.start and c.end <= e.end):
        result.errors.append(f"{where}: order must be start ≤ hook ≤ cliff ≤ end "
                             f"(times {s.start}, {h.start}, {c.start}–{c.end}, end {e.end})")
        return None
    segments = [_segment(s, e)]
    _check_length(segments, where, result)
    return {"episode": ep, "segments": _fmt_segments(segments), "hook_block": h.id, "cliff_block": c.id,
            "quality": quality, "notes": _note(text)}


def _parse_arc(text: str, where: str, blocks: dict[str, Block], result: Result) -> dict | None:
    head = re.split(r"\b(?:quality|note|hook|cliff)\s*=", text, maxsplit=1, flags=re.IGNORECASE)[0]
    parts = [p.strip() for p in head.split("+") if p.strip()]
    if not parts or any("_" in p for p in parts):
        result.errors.append(f"{where}: arc needs segments like E01:B010-B030 + E42:B005-B020")
        return None
    segments, seg_blocks = [], []
    for part in parts:
        m = ARC_SEGMENT.match(part)
        if not m:
            result.errors.append(f"{where}: can't read arc segment {part!r}")
            return None
        ep = int(m.group(1))
        a, b = full_id(ep, m.group(2)), full_id(ep, m.group(3))
        bad = [x for x in (a, b) if x is None or x not in blocks]
        if bad:
            result.errors.append(f"{where}: arc segment {part!r} has unknown block(s)")
            return None
        if blocks[a].start >= blocks[b].end:
            result.errors.append(f"{where}: arc segment {part!r} ends before it starts")
            return None
        segments.append(_segment(blocks[a], blocks[b]))
        seg_blocks.append((blocks[a], blocks[b]))
    # Optional hook=E01:B012 / cliff=E42:B019; default to the first block and the last block.
    points = {k.lower(): full_id(int(ep), b) for k, ep, b in ARC_POINT.findall(text)}
    hook = points.get("hook") or seg_blocks[0][0].id
    cliff = points.get("cliff") or seg_blocks[-1][1].id
    for name, bid in (("hook", hook), ("cliff", cliff)):
        inside = bid in blocks and any(a.ep == blocks[bid].ep and a.start <= blocks[bid].start <= b.end
                                       for a, b in seg_blocks)
        if not inside:
            result.errors.append(f"{where}: arc {name}={bid} is not inside any segment")
            return None
    quality = _quality(dict((k.lower(), v) for k, v in FIELD.findall(text.split("note=")[0])).get("quality"),
                       where, result)
    if quality is None:
        return None
    _check_length(segments, where, result)
    return {"episode": segments[0][0], "segments": _fmt_segments(segments), "hook_block": hook,
            "cliff_block": cliff, "quality": quality, "notes": _note(text)}


def parse_worksheet(text: str, episodes: list[Episode]) -> Result:
    blocks = {b.id: b for e in episodes for b in e.blocks}
    known_eps = {e.ep for e in episodes}
    result = Result()
    ep = None
    answered: dict[int, bool] = {}
    for lineno, line in enumerate(text.splitlines(), start=1):
        m = SECTION.match(line)
        if m:
            ep = int(m.group(1))
            answered.setdefault(ep, False)
            if ep not in known_eps:
                result.errors.append(f"line {lineno}: episode {ep} is not in the pack")
            continue
        if ep is None:
            continue  # rules and script text above the first answer block
        where = f"line {lineno} (E{ep:02d})"
        if (m := ARC.match(line)):
            row = _parse_arc(m.group(1), where, blocks, result)
            if row:
                result.rows.append(row)
                answered[ep] = True
                _count(result, row["episode"], "arc")
        elif (m := PROMO.match(line)):
            row = _parse_promo(ep, m.group(1), where, blocks, result)
            if row:
                result.rows.append(row)
                answered[ep] = True
                _count(result, ep, "promo")
        elif (m := NONE.match(line)):
            result.rows.append({"episode": ep, "segments": "NONE", "hook_block": "", "cliff_block": "",
                                "quality": 0, "notes": m.group(1).strip()})
            answered[ep] = True
            _count(result, ep, "none")
        elif line.startswith("## "):
            ep = None  # next episode's script starts; ignore its lines until its answer block
    for num, done in answered.items():
        if not done:
            result.warnings.append(f"E{num:02d}: no picks and no 'none'; episode left out of the CSV")
    for num, counts in result.per_episode.items():
        if counts["none"] and (counts["promo"] or counts["arc"]):
            result.warnings.append(f"E{num:02d}: marked 'none' but also has picks")
    for i, row in enumerate(result.rows, start=1):
        row["gold_id"] = f"G{i:02d}"
    return result


def write_csv(rows: list[dict], path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=CSV_COLUMNS)
        writer.writeheader()
        writer.writerows({k: row[k] for k in CSV_COLUMNS} for row in rows)


def summary(result: Result) -> str:
    lines = [f"rows: {len(result.rows)}  (promos {sum(c['promo'] for c in result.per_episode.values())}, "
             f"arcs {sum(c['arc'] for c in result.per_episode.values())}, "
             f"none {sum(c['none'] for c in result.per_episode.values())})"]
    for num in sorted(result.per_episode):
        c = result.per_episode[num]
        lines.append(f"  E{num:02d}: promo {c['promo']}  arc {c['arc']}  none {c['none']}")
    lines.append(f"warnings: {len(result.warnings)}")
    lines += [f"  WARN {w}" for w in result.warnings]
    lines.append(f"errors: {len(result.errors)}")
    lines += [f"  ERROR {e}" for e in result.errors]
    return "\n".join(lines)


def main() -> int:
    parser = argparse.ArgumentParser(description="Filled gold worksheet -> gold/gold_labels.csv")
    parser.add_argument("--worksheet", default="private/gold_worksheet.md")
    parser.add_argument("--input", required=True, help="pack folder or .zip")
    parser.add_argument("--out", default="gold/gold_labels.csv")
    parser.add_argument("--force", action="store_true", help="overwrite an existing CSV")
    args = parser.parse_args()

    out = Path(args.out)
    if out.exists() and not args.force:
        print(f"{out} already exists; use --force to overwrite it")
        return 1
    episodes, _ = load_pack(args.input)
    result = parse_worksheet(Path(args.worksheet).read_text(encoding="utf-8"), episodes)
    print(summary(result))
    if result.errors:
        print("not written: fix the errors above and run again")
        return 1
    write_csv(result.rows, out)
    print(f"wrote {out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
