"""Confidentiality check: fail if anything git would publish mentions the confidential show.

Run before every commit that touches public logs (default mode) and before EVERY push
(`--pre-push`), per CLAUDE.md hard rule 3. Word lists: character names from config/aliases.yaml,
show keywords from private/leak_keywords.txt, and a fixed sample of real dialogue lines from input/.
Default mode scans the working tree plus staged blobs; --pre-push also scans every line ever
added in any commit on any branch, and every commit message, because a push publishes history.
"""

from __future__ import annotations

import argparse
import random
import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DIALOGUE_SAMPLE_SIZE = 20
# A quoted line this long is specific enough that finding it in a tracked file means a leak.
MIN_DIALOGUE_CHARS = 25


def git(repo: Path, *args: str) -> str:
    result = subprocess.run(["git", *args], cwd=repo, capture_output=True)
    if result.returncode != 0:
        sys.exit(f"leak_check: git {' '.join(args)} failed: {result.stderr.decode(errors='replace').strip()}")
    return result.stdout.decode("utf-8", errors="replace")


# --- word lists

def names_from_aliases(path: Path) -> list[str]:
    """Raw labels and canonical names from the alias file (missing file = empty list)."""
    if not path.exists():
        return []
    import yaml  # only needed when the alias file exists

    data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    names: set[str] = set()
    for raw, canonical in (data.get("aliases") or {}).items():
        names.update([str(raw), str(canonical)])
    names.update(str(name) for name in (data.get("cast") or {}))
    return sorted(names)


def keywords_from_file(path: Path) -> list[str]:
    if not path.exists():
        return []
    lines = path.read_text(encoding="utf-8").splitlines()
    return [line.strip() for line in lines if line.strip() and not line.lstrip().startswith("#")]


def sample_dialogue_lines(input_dir: Path) -> list[str]:
    """A fixed-seed sample of long quoted lines from the pack, so the check is repeatable."""
    lines: list[str] = []
    for path in sorted(input_dir.rglob("*.txt")):
        for line in path.read_text(encoding="utf-8", errors="replace").splitlines():
            match = re.fullmatch(r'\s*"(.+)"\s*', line)
            if match and len(match.group(1)) >= MIN_DIALOGUE_CHARS:
                lines.append(match.group(1))
    random.Random(0).shuffle(lines)
    return lines[:DIALOGUE_SAMPLE_SIZE]


# --- matching

def hits_in_text(text: str, where: str, words: list[str], phrases: list[str]) -> list[str]:
    """Words match case-insensitively on word boundaries; dialogue phrases as substrings."""
    patterns = [(w, re.compile(rf"\b{re.escape(w)}\b", re.IGNORECASE)) for w in words]
    lowered_phrases = [p.lower() for p in phrases]
    hits = []
    for lineno, line in enumerate(text.splitlines(), start=1):
        for word, pattern in patterns:
            if pattern.search(line):
                hits.append(f"{where}:{lineno}: keyword '{word}'")
        lowered = line.lower()
        for phrase in lowered_phrases:
            if phrase in lowered:
                hits.append(f"{where}:{lineno}: dialogue line from input/")
    return hits


# --- what to scan

def scan_working_tree(repo: Path, words: list[str], phrases: list[str]) -> list[str]:
    """Tracked files plus untracked files that .gitignore doesn't exclude (what `git add .` would add)."""
    hits = []
    for rel in git(repo, "ls-files", "--cached", "--others", "--exclude-standard").splitlines():
        path = repo / rel
        if path.is_file():
            text = path.read_bytes().decode("utf-8", errors="replace")
            hits += hits_in_text(text, rel, words, phrases)
    return hits


def scan_staged(repo: Path, words: list[str], phrases: list[str]) -> list[str]:
    """The staged version of each changed file: that is what the next commit contains."""
    hits = []
    for rel in git(repo, "diff", "--cached", "--name-only", "--diff-filter=ACMR").splitlines():
        text = git(repo, "show", f":{rel}")
        hits += hits_in_text(text, f"staged {rel}", words, phrases)
    return hits


def scan_history(repo: Path, words: list[str], phrases: list[str]) -> list[str]:
    """Every commit message and every line ever added, on all branches.

    A leak fixed in a later commit is still published by a push, so the fix doesn't count.
    """
    hits = []
    for commit in git(repo, "rev-list", "--all").split():
        short = commit[:8]
        message = git(repo, "log", "-1", "--format=%B", commit)
        hits += hits_in_text(message, f"commit message {short}", words, phrases)
        diff = git(repo, "show", "--format=", "--unified=0", "--no-color", commit)
        current_file = "?"
        added = []
        for line in diff.splitlines():
            if line.startswith("+++ "):
                current_file = line[6:] if line.startswith("+++ b/") else line[4:]
            elif line.startswith("+") and not line.startswith("+++"):
                added.append((current_file, line[1:]))
        for file_name, line in added:
            hits += [h.replace(":1:", ":", 1) for h in hits_in_text(line, f"commit {short} {file_name}", words, phrases)]
    return hits


def main() -> int:
    parser = argparse.ArgumentParser(description="Fail if anything publishable mentions the confidential show.")
    parser.add_argument("--pre-push", action="store_true",
                        help="also scan all commits (content + messages) on all branches: run before every push")
    args = parser.parse_args()

    names = names_from_aliases(ROOT / "config" / "aliases.yaml")
    keywords = keywords_from_file(ROOT / "private" / "leak_keywords.txt")
    dialogue = sample_dialogue_lines(ROOT / "input")
    words = sorted(set(names) | set(keywords))
    print(f"leak_check: {len(names)} alias names, {len(keywords)} keywords, {len(dialogue)} dialogue lines"
          + ("  [pre-push: + full history]" if args.pre_push else ""))
    if not names:
        print("  warning: config/aliases.yaml missing or empty (names checked only via keywords)")
    if not keywords:
        print("  warning: private/leak_keywords.txt missing or empty")

    hits = scan_working_tree(ROOT, words, dialogue) + scan_staged(ROOT, words, dialogue)
    if args.pre_push:
        hits += scan_history(ROOT, words, dialogue)
    for hit in hits:
        print("  LEAK", hit)
    print("leak_check: FAIL" if hits else "leak_check: PASS")
    return 1 if hits else 0


if __name__ == "__main__":
    sys.exit(main())
