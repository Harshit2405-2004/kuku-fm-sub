"""Shared test fixtures. Everything here uses the fictional synthetic show, never the real pack."""

from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
SYNTH_DIR = ROOT / "samples" / "synthetic_show"


@pytest.fixture
def synth_dir() -> Path:
    return SYNTH_DIR


@pytest.fixture
def synth_text():
    """Return the raw text of synthetic episode n (1–3)."""
    def _read(n: int) -> str:
        path = next(SYNTH_DIR.glob(f"episode-{n:03d}-*.txt"))
        return path.read_text(encoding="utf-8")
    return _read
