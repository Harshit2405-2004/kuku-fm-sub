"""Speaker aliases: map the raw speaker labels in a script to one canonical name per character.

Pipeline position: used by parse.py while building blocks. The map is show-specific data in
config/aliases.yaml (git-ignored), never Python code, so a brand-new show works with no map at all.
"""

from __future__ import annotations


def canonical_speaker(raw: str, aliases: dict[str, str] | None) -> str:
    """Look up the upper-cased raw label; unknown names keep their raw value, title-cased."""
    key = raw.strip().upper()
    if aliases and key in aliases:
        return aliases[key]
    return raw.strip().title()
