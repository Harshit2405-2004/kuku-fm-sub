"""Speaker aliases: map the raw speaker labels in a script to one canonical name per character.

Pipeline position: used by parse.py while building blocks. The map is show-specific data in
config/aliases.yaml (git-ignored), never Python code, so a brand-new show works with no map at all.
A key like "E02:LABEL" overrides LABEL in that one episode, for scripts that reuse a descriptive label
for two different people (D-026).
"""

from __future__ import annotations

import logging
import re
from pathlib import Path

import yaml

log = logging.getLogger(__name__)


# "E2:LABEL" or "E02:LABEL" -> per-episode override key, normalised to "E02:LABEL".
_EPISODE_KEY = re.compile(r"^E(\d+):\s*(.+)$")


def canonical_speaker(raw: str, aliases: dict[str, str] | None, ep: int | None = None) -> str:
    """Look up the upper-cased raw label; unknown names keep their raw value, title-cased.

    An episode override ("E02:LABEL") wins over the global entry for that episode only.
    """
    key = raw.strip().upper()
    if aliases:
        if ep is not None and f"E{ep:02d}:{key}" in aliases:
            return aliases[f"E{ep:02d}:{key}"]
        if key in aliases:
            return aliases[key]
    return raw.strip().title()


def _normalise_key(raw: object) -> str:
    key = str(raw).strip().upper()
    match = _EPISODE_KEY.match(key)
    return f"E{int(match.group(1)):02d}:{match.group(2).strip()}" if match else key


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
    aliases = {_normalise_key(raw): str(name).strip() for raw, name in (data.get("aliases") or {}).items()}
    cast = {str(name).strip(): str(role).strip() for name, role in (data.get("cast") or {}).items()}
    return aliases, cast
