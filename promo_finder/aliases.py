"""Speaker aliases: map the raw speaker labels in a script to one canonical name per character.

Pipeline position: used by parse.py while building blocks. The map is show-specific data in
config/aliases.yaml (git-ignored), never Python code, so a brand-new show works with no map at all.
"""

from __future__ import annotations

import logging
from pathlib import Path

import yaml

log = logging.getLogger(__name__)


def canonical_speaker(raw: str, aliases: dict[str, str] | None) -> str:
    """Look up the upper-cased raw label; unknown names keep their raw value, title-cased."""
    key = raw.strip().upper()
    if aliases and key in aliases:
        return aliases[key]
    return raw.strip().title()


def load_aliases(path: Path | str | None) -> tuple[dict[str, str], dict[str, str]]:
    """Read an alias file -> (raw label -> canonical name, canonical name -> one-line role).

    A missing file is normal for a brand-new show: we warn and carry on with raw names.
    """
    if path is None:
        return {}, {}
    path = Path(path)
    if not path.exists():
        log.warning("no alias file at %s; using raw speaker names (title-cased)", path)
        return {}, {}
    data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    aliases = {str(raw).strip().upper(): str(name).strip() for raw, name in (data.get("aliases") or {}).items()}
    cast = {str(name).strip(): str(role).strip() for name, role in (data.get("cast") or {}).items()}
    return aliases, cast
