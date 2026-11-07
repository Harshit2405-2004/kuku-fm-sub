"""Confidentiality check: fail if any file git would publish mentions the confidential show.

Run before every commit that touches public logs and before every push (CLAUDE.md hard rule 3).
It checks every tracked or about-to-be-tracked file (git ls-files, including untracked files
that aren't ignored) against three lists: character names from config/aliases.yaml, show
keywords from private/leak_keywords.txt, and a sample of real dialogue lines from input/.
"""

from __future__ import annotations

import random
import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
ALIASES_FILE = ROOT / "config" / "aliases.yaml"
KEYWORDS_FILE = ROOT / "private" / "leak_keywords.txt"
INPUT_DIR = ROOT / "input"
DIALOGUE_SAMPLE_SIZE = 20
# A quoted line this long is specific enough that finding it in a tracked file means a leak.
MIN_DIALOGUE_CHARS = 25


def files_git_would_publish() -> list[Path]:
    """Tracked files plus untracked files that .gitignore doesn't exclude."""
    result = subprocess.run(
        ["git", "ls-files", "--cached", "--others", "--exclude-standard"],
        cwd=ROOT, capture_output=True, text=True, encoding="utf-8",
    )
    if result.returncode != 0:
        sys.exit(f"leak_check: git ls-files failed: {result.stderr.strip()}")
    return [ROOT / line for line in result.stdout.splitlines() if line.strip()]


def names_from_aliases() -> list[str]:
    """Raw labels and canonical names from config/aliases.yaml (missing file = empty list)."""
    if not ALIASES_FILE.exists():
        return []
    import yaml  # only needed when the alias file exists

    data = yaml.safe_load(ALIASES_FILE.read_text(encoding="utf-8")) or {}
    names: set[str] = set()
    for raw, canonical in (data.get("aliases") or {}).items():
        names.add(str(raw))
        names.add(str(canonical))
    names.update(str(name) for name in (data.get("cast") or {}))
    return sorted(names)


def keywords_from_file() -> list[str]:
    if not KEYWORDS_FILE.exists():
        return []
    lines = KEYWORDS_FILE.read_text(encoding="utf-8").splitlines()
    return [line.strip() for line in lines if line.strip() and not line.lstrip().startswith("#")]


def sample_dialogue_lines() -> list[str]:
    """A fixed-seed sample of long quoted lines from the pack, so the check is repeatable."""
    lines: list[str] = []
    for path in sorted(INPUT_DIR.rglob("*.txt")):
        for line in path.read_text(encoding="utf-8", errors="replace").splitlines():
            match = re.fullmatch(r'\s*"(.+)"\s*', line)
            if match and len(match.group(1)) >= MIN_DIALOGUE_CHARS:
                lines.append(match.group(1))
    random.Random(0).shuffle(lines)
    return lines[:DIALOGUE_SAMPLE_SIZE]


def find_hits(files: list[Path], words: list[str], phrases: list[str]) -> list[str]:
    """Words match case-insensitively on word boundaries; dialogue phrases match as substrings."""
    word_patterns = [(w, re.compile(rf"\b{re.escape(w)}\b", re.IGNORECASE)) for w in words]
    hits = []
    for path in files:
        if path.resolve() == Path(__file__).resolve() or not path.is_file():
            continue
        try:
            text = path.read_text(encoding="utf-8")
        except (UnicodeDecodeError, OSError):
            continue  # binary files can't hold a readable leak we care about
        rel = path.relative_to(ROOT).as_posix()
        for lineno, line in enumerate(text.splitlines(), start=1):
            for word, pattern in word_patterns:
                if pattern.search(line):
                    hits.append(f"{rel}:{lineno}: keyword '{word}'")
            for phrase in phrases:
                if phrase.lower() in line.lower():
                    hits.append(f"{rel}:{lineno}: dialogue line from input/")
    return hits


def main() -> int:
    files = files_git_would_publish()
    names = names_from_aliases()
    keywords = keywords_from_file()
    dialogue = sample_dialogue_lines()
    print(f"leak_check: {len(files)} publishable files; {len(names)} alias names, "
          f"{len(keywords)} keywords, {len(dialogue)} dialogue lines")
    if not names:
        print("  warning: config/aliases.yaml missing or empty (names checked only via keywords)")
    if not keywords:
        print("  warning: private/leak_keywords.txt missing or empty")

    hits = find_hits(files, sorted(set(names) | set(keywords)), dialogue)
    for hit in hits:
        print("  LEAK", hit)
    print("leak_check: FAIL" if hits else "leak_check: PASS")
    return 1 if hits else 0


if __name__ == "__main__":
    sys.exit(main())
