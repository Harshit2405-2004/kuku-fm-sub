"""Mock mode (--mock): deterministic canned LLM replies, so the whole pipeline runs with no API key.

Pipeline position: llm.call_llm returns these instead of calling a model. Replies are built from the
compact block lines inside the prompt, so they always reference real block IDs and validate like a
real reply. Used by tests and by the demo app when no key is available.
"""

from __future__ import annotations


def respond(stage: str, messages: list[dict]) -> str:
    """Return the raw JSON text a model would have returned for this stage."""
    raise NotImplementedError(f"mock reply for stage '{stage}' not built yet")
