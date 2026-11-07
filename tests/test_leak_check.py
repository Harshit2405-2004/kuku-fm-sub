"""leak_check tests, run in a throwaway git repo with a made-up keyword ('Zorblax').

Covers the CP-1 findings: staged content, past commits and commit messages must all be scanned.
"""

import subprocess
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))
import leak_check  # noqa: E402

WORDS = ["Zorblax"]


def git(repo, *args):
    subprocess.run(["git", "-c", "user.name=t", "-c", "user.email=t@t", *args], cwd=repo,
                   check=True, capture_output=True)


@pytest.fixture
def repo(tmp_path):
    git(tmp_path, "init", "-q")
    (tmp_path / "a.md").write_text("clean\n", encoding="utf-8")
    git(tmp_path, "add", "a.md")
    git(tmp_path, "commit", "-q", "-m", "first")
    return tmp_path


def test_clean_repo_has_no_hits(repo):
    assert leak_check.scan_working_tree(repo, WORDS, []) == []
    assert leak_check.scan_history(repo, WORDS, []) == []


def test_working_tree_hit(repo):
    (repo / "b.md").write_text("the Zorblax returns\n", encoding="utf-8")
    hits = leak_check.scan_working_tree(repo, WORDS, [])
    assert hits and "b.md:1" in hits[0]


def test_staged_version_is_scanned_even_if_working_copy_is_fixed(repo):
    (repo / "a.md").write_text("Zorblax\n", encoding="utf-8")
    git(repo, "add", "a.md")
    (repo / "a.md").write_text("clean\n", encoding="utf-8")   # fixed on disk, not re-staged
    hits = leak_check.scan_staged(repo, WORDS, [])
    assert hits and "staged a.md" in hits[0]


def test_history_finds_leak_removed_in_a_later_commit(repo):
    (repo / "a.md").write_text("Zorblax\n", encoding="utf-8")
    git(repo, "commit", "-q", "-am", "oops")
    (repo / "a.md").write_text("clean\n", encoding="utf-8")
    git(repo, "commit", "-q", "-am", "fix")
    assert leak_check.scan_working_tree(repo, WORDS, []) == []
    hits = leak_check.scan_history(repo, WORDS, [])
    assert any("a.md" in h for h in hits)


def test_history_scans_commit_messages(repo):
    git(repo, "commit", "-q", "--allow-empty", "-m", "about the Zorblax scene")
    hits = leak_check.scan_history(repo, WORDS, [])
    assert any("commit message" in h for h in hits)


def test_dialogue_phrase_matches_case_insensitively(repo):
    (repo / "c.md").write_text("quote: I NEVER SAW THE HARBOR LIGHTS AGAIN\n", encoding="utf-8")
    hits = leak_check.scan_working_tree(repo, [], ["I never saw the harbor lights again"])
    assert hits and "dialogue" in hits[0]


def test_non_utf8_file_is_still_scanned(repo):
    (repo / "d.txt").write_bytes(b"\xff\xfe bad bytes Zorblax\n")
    assert leak_check.scan_working_tree(repo, WORDS, [])


def test_alias_override_key_contributes_the_bare_label(tmp_path):
    path = tmp_path / "aliases.yaml"
    path.write_text('aliases:\n  THE STRANGER: Ellis\n  "E02:THE STRANGER": Old Fisherman\n', encoding="utf-8")
    names = leak_check.names_from_aliases(path)
    assert "THE STRANGER" in names and "Old Fisherman" in names
    assert not any(n.startswith("E02:") for n in names)
