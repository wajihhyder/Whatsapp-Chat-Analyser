"""Detection engines.

A *detection engine* takes a string and returns the PII spans it found. Two
implementations are provided:

* :class:`RegexEngine` — pure-Python, no heavy dependencies. Always available,
  so the tool runs out-of-the-box. Catches structured PII (email, phone, card,
  CNIC, IBAN, IP, URL) plus any names passed in via a deny-list.
* :class:`PresidioEngine` — wraps Microsoft Presidio (``presidio-analyzer`` +
  spaCy NER) for context-aware detection of free-text names and locations on
  top of the same structured recognisers. Used automatically when installed.

Both return the same :class:`Span` objects, and overlap resolution is shared,
so the redactor behaves identically regardless of which engine is active — the
only difference is how many free-text names/places get caught.
"""
from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import List, Optional, Sequence
import re

from . import patterns

# Entity type names deliberately match Presidio's, so spans from either engine
# share a vocabulary and the same token prefixes.
PERSON = "PERSON"
PHONE = "PHONE_NUMBER"
EMAIL = "EMAIL_ADDRESS"
CARD = "CREDIT_CARD"
CNIC = "PK_CNIC"
IBAN = "IBAN"
URL = "URL"
IP = "IP_ADDRESS"
LOCATION = "LOCATION"

# Higher wins when two detections overlap. CNIC outranks PHONE/CARD so a 13-digit
# national ID is never mislabelled as a phone number.
ENTITY_PRIORITY = {
    CNIC: 95,
    IBAN: 92,
    EMAIL: 90,
    CARD: 88,
    URL: 85,
    IP: 80,
    PHONE: 70,
    PERSON: 60,
    LOCATION: 50,
}


@dataclass(frozen=True)
class Span:
    """A detected PII occurrence: ``text[start:end]`` is ``text``-of-type."""

    start: int
    end: int
    entity_type: str
    text: str
    score: float = 1.0


def resolve_overlaps(spans: Sequence[Span]) -> List[Span]:
    """Drop overlapping spans, keeping the highest-priority/longest one.

    Returns the survivors sorted left-to-right, ready for replacement.
    """
    ordered = sorted(
        spans,
        key=lambda s: (-ENTITY_PRIORITY.get(s.entity_type, 0), -(s.end - s.start), s.start),
    )
    accepted: List[Span] = []
    for s in ordered:
        if any(not (s.end <= a.start or s.start >= a.end) for a in accepted):
            continue
        accepted.append(s)
    accepted.sort(key=lambda s: s.start)
    return accepted


def _name_spans(text: str, names: Sequence[str]) -> List[Span]:
    """Whole-word, case-insensitive matches of known names (the sender list)."""
    spans: List[Span] = []
    for name in names:
        name = name.strip()
        if len(name) < 2:
            continue
        for m in re.finditer(rf"(?<!\w){re.escape(name)}(?!\w)", text, re.IGNORECASE):
            spans.append(Span(m.start(), m.end(), PERSON, m.group()))
    return spans


class DetectionEngine(ABC):
    name = "base"

    @abstractmethod
    def detect(self, text: str, names: Optional[Sequence[str]] = None) -> List[Span]:
        ...


class RegexEngine(DetectionEngine):
    """Dependency-free engine. Structured PII via regex + names via deny-list."""

    name = "regex"

    def detect(self, text: str, names: Optional[Sequence[str]] = None) -> List[Span]:
        spans: List[Span] = []
        for m in patterns.EMAIL_RE.finditer(text):
            spans.append(Span(m.start(), m.end(), EMAIL, m.group()))
        for m in patterns.URL_RE.finditer(text):
            spans.append(Span(m.start(), m.end(), URL, m.group()))
        for m in patterns.CNIC_RE.finditer(text):
            spans.append(Span(m.start(), m.end(), CNIC, m.group()))
        for m in patterns.IBAN_RE.finditer(text):
            spans.append(Span(m.start(), m.end(), IBAN, m.group()))
        for m in patterns.IP_RE.finditer(text):
            spans.append(Span(m.start(), m.end(), IP, m.group()))
        for start, end in patterns.find_cards(text):
            spans.append(Span(start, end, CARD, text[start:end]))
        for start, end in patterns.find_phones(text):
            spans.append(Span(start, end, PHONE, text[start:end]))
        if names:
            spans.extend(_name_spans(text, names))
        return spans


class PresidioEngine(DetectionEngine):
    """Presidio NER layered on the deterministic structured detection.

    Composition, not replacement: the regex engine still supplies all structured
    PII (email, phone — including local Pakistani formats — card, CNIC, IBAN, IP,
    URL) and exact participant-name matches, and Presidio's spaCy model adds
    PERSON / LOCATION spans for names and places that appear in free text. So the
    Presidio engine is a strict superset of the regex engine — it can only catch
    *more*. Recall on free-text names/places depends on the spaCy model size
    (the light ``en_core_web_sm`` here; ``en_core_web_lg`` is stronger).
    """

    name = "presidio"

    def __init__(self) -> None:
        from presidio_analyzer import AnalyzerEngine
        from presidio_analyzer.nlp_engine import NlpEngineProvider

        nlp_engine = NlpEngineProvider(
            nlp_configuration={
                "nlp_engine_name": "spacy",
                "models": [{"lang_code": "en", "model_name": "en_core_web_sm"}],
            }
        ).create_engine()
        self._analyzer = AnalyzerEngine(nlp_engine=nlp_engine, supported_languages=["en"])
        # Presidio is used ONLY for the NER entities the regex engine can't do.
        self._ner_entities = [PERSON, LOCATION]
        # Structured PII (and exact participant-name matches) come from the same
        # deterministic layer the offline engine uses, so Presidio never has
        # *lower* recall than regex on localised phone / card / CNIC formats.
        self._structured = RegexEngine()

    def detect(self, text: str, names: Optional[Sequence[str]] = None) -> List[Span]:
        spans = self._structured.detect(text, names=names)
        results = self._analyzer.analyze(
            text=text,
            language="en",
            entities=self._ner_entities,  # only PERSON/LOCATION → no networked URL recognizer
            score_threshold=0.4,
        )
        spans.extend(
            Span(r.start, r.end, r.entity_type, text[r.start : r.end], r.score)
            for r in results
        )
        return spans


def build_engine(prefer_presidio: bool = True) -> DetectionEngine:
    """Return the best available engine.

    Tries Presidio first (better recall on free-text names/places); falls back
    to the always-available regex engine if Presidio or its spaCy model is not
    installed. Set ``prefer_presidio=False`` to force the offline engine.
    """
    if prefer_presidio:
        try:
            return PresidioEngine()
        except Exception:
            pass
    return RegexEngine()
