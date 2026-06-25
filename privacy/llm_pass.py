"""Optional LLM-assisted detection pass (OFF by default).

The local engines catch structured PII and known participant names. They cannot
catch *context-dependent* identifiers — a name that never appears as a sender,
a home address, an employer — because that needs language understanding.

This module adds that, by asking an LLM to flag the spans pattern-matching
missed. It is deliberately **opt-in**:

    ⚠️  PRIVACY TRADE-OFF. Sending the chat to a third-party model to find PII
        means the very data you are trying to protect leaves your machine. That
        defeats the purpose of a privacy tool for most use cases. The local
        engines run fully offline; reach for this pass only when you have a
        lawful basis and a data-processing agreement that covers sending the
        content to the model provider, and prefer it on already-pseudonymised
        text. It is never enabled unless you pass ``--llm`` *and* set
        ``ANTHROPIC_API_KEY``.

The pass returns extra spans that flow through the same overlap-resolution and
pseudonymisation path as everything else, so a name the LLM finds gets the same
``Person_N`` token as the local engine would have used.
"""
from __future__ import annotations

import json
import os
import re
from typing import Dict, List, Optional, Sequence

from .engines import LOCATION, PERSON, DetectionEngine, Span

# Small, fast, low-cost model is the right default for short-message span
# extraction; override with REDACT_LLM_MODEL if you want a more capable one.
_DEFAULT_MODEL = "claude-haiku-4-5"

_SYSTEM = (
    "You are a PII detection assistant. Given a single chat message, identify "
    "substrings that are personally identifiable information a simple regex "
    "would miss: people's names, physical addresses, place names, employers/"
    "organisations, or other directly identifying details. Do NOT flag phone "
    "numbers, emails, URLs or ID numbers (those are handled separately). "
    'Return ONLY a JSON array of objects {"text": <exact substring>, "type": '
    '<one of PERSON, LOCATION, ORG, OTHER>}. Return [] if there is none.'
)

_TYPE_MAP = {"PERSON": PERSON, "LOCATION": LOCATION, "ORG": LOCATION, "OTHER": PERSON}


class LLMRecognizer:
    """Calls the Anthropic API to find context-dependent PII in a message."""

    def __init__(self, model: Optional[str] = None) -> None:
        import anthropic  # imported lazily so the package has no hard dep

        self._client = anthropic.Anthropic()
        self._model = model or os.environ.get("REDACT_LLM_MODEL", _DEFAULT_MODEL)
        self._cache: Dict[str, List[dict]] = {}

    def _ask(self, text: str) -> List[dict]:
        if text in self._cache:
            return self._cache[text]
        msg = self._client.messages.create(
            model=self._model,
            max_tokens=512,
            system=_SYSTEM,
            messages=[{"role": "user", "content": text}],
        )
        raw = "".join(b.text for b in msg.content if b.type == "text")
        found = _parse_json_array(raw)
        self._cache[text] = found
        return found

    def detect(self, text: str) -> List[Span]:
        spans: List[Span] = []
        for item in self._ask(text):
            value = (item.get("text") or "").strip()
            if not value:
                continue
            etype = _TYPE_MAP.get(str(item.get("type", "")).upper(), PERSON)
            for m in re.finditer(re.escape(value), text):
                spans.append(Span(m.start(), m.end(), etype, m.group(), 0.8))
        return spans


class LLMAugmentedEngine(DetectionEngine):
    """Wraps a local engine and adds the LLM recognizer's spans on top."""

    def __init__(self, base: DetectionEngine, recognizer: LLMRecognizer) -> None:
        self.base = base
        self.recognizer = recognizer
        self.name = f"{base.name}+llm"

    def detect(self, text: str, names: Optional[Sequence[str]] = None) -> List[Span]:
        spans = list(self.base.detect(text, names=names))
        try:
            spans.extend(self.recognizer.detect(text))
        except Exception:
            # A flaky API call must never drop the deterministic local result.
            pass
        return spans


def _parse_json_array(raw: str) -> List[dict]:
    """Defensively pull the first JSON array out of the model's reply."""
    start, end = raw.find("["), raw.rfind("]")
    if start == -1 or end <= start:
        return []
    try:
        data = json.loads(raw[start : end + 1])
        return [d for d in data if isinstance(d, dict)]
    except (ValueError, TypeError):
        return []


def wrap_with_llm(engine: DetectionEngine, model: Optional[str] = None) -> DetectionEngine:
    """Wrap ``engine`` with the optional LLM pass.

    Raises a clear error if prerequisites are missing — the caller explicitly
    asked for the LLM pass (``--llm``), so failing loudly beats silently doing
    nothing.
    """
    if not os.environ.get("ANTHROPIC_API_KEY"):
        raise RuntimeError(
            "The --llm pass needs ANTHROPIC_API_KEY set. It is off by default "
            "because it sends chat content to a third-party model; see PRIVACY.md."
        )
    try:
        import anthropic  # noqa: F401
    except ImportError as exc:
        raise RuntimeError(
            "The --llm pass needs the 'anthropic' package (pip install anthropic)."
        ) from exc
    return LLMAugmentedEngine(engine, LLMRecognizer(model=model))
