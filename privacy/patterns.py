"""Deterministic PII patterns shared by the regex engine and the Presidio
custom recognizers.

These are pure, dependency-free building blocks: compiled regular expressions
plus a couple of validators (Luhn for card numbers). Keeping them in one place
means the offline fallback engine and the Presidio-backed engine detect exactly
the same structured entities, so swapping engines never silently changes which
card or CNIC formats are caught.

Localisation note: the law-firm brief is Karachi-based, so the recognisers
include Pakistani identifiers that off-the-shelf NER misses — the CNIC national
ID number and Pakistani IBAN / mobile formats — alongside the usual email, URL
and credit-card patterns.
"""
from __future__ import annotations

import re
from typing import Iterator, Tuple

# --- Email ----------------------------------------------------------------
EMAIL_RE = re.compile(r"\b[A-Za-z0-9._%+\-]+@[A-Za-z0-9.\-]+\.[A-Za-z]{2,}\b")

# --- URLs -----------------------------------------------------------------
URL_RE = re.compile(r"\b(?:https?://|www\.)[^\s<>()]+", re.IGNORECASE)

# --- Pakistani CNIC (national ID): 13 digits as 5-7-1 ----------------------
CNIC_RE = re.compile(r"\b\d{5}-\d{7}-\d\b")

# --- IBAN (incl. Pakistani PKxx...) ---------------------------------------
IBAN_RE = re.compile(r"\b[A-Z]{2}\d{2}[A-Z0-9]{11,30}\b")

# --- IPv4 -----------------------------------------------------------------
IP_RE = re.compile(
    r"\b(?:(?:25[0-5]|2[0-4]\d|1?\d?\d)\.){3}(?:25[0-5]|2[0-4]\d|1?\d?\d)\b"
)

# --- Candidate numeric runs (resolved into CARD vs PHONE below) ------------
# A loose grab of digit groups that may carry separators; we validate length
# and Luhn afterwards so we don't redact times ("9:01") or short codes.
_NUMERIC_RUN_RE = re.compile(r"(?<!\w)\+?\d[\d\s\-().]{6,}\d")


def luhn_ok(digits: str) -> bool:
    """Return True if ``digits`` (a string of 0-9) passes the Luhn checksum."""
    total = 0
    parity = len(digits) % 2
    for i, ch in enumerate(digits):
        d = ord(ch) - 48
        if i % 2 == parity:
            d *= 2
            if d > 9:
                d -= 9
        total += d
    return total % 10 == 0


def _iter_runs(text: str) -> Iterator[Tuple[int, int, str]]:
    for m in _NUMERIC_RUN_RE.finditer(text):
        raw = m.group()
        end = m.end()
        # trim trailing separators the greedy class may have eaten
        while raw and raw[-1] in " -().":
            raw = raw[:-1]
            end -= 1
        yield m.start(), end, raw


def find_cards(text: str) -> Iterator[Tuple[int, int]]:
    """Yield (start, end) spans of Luhn-valid 13-19 digit card numbers."""
    for start, end, raw in _iter_runs(text):
        digits = re.sub(r"\D", "", raw)
        if 13 <= len(digits) <= 19 and luhn_ok(digits):
            yield start, end


def find_phones(text: str) -> Iterator[Tuple[int, int]]:
    """Yield (start, end) spans of plausible phone numbers.

    A run qualifies if, once separators are stripped, it is a +-prefixed 8-15
    digit number or a bare 10-15 digit number. That window keeps real numbers
    (incl. Pakistani ``+92 3xx xxxxxxx`` and local ``03xx-xxxxxxx``) while
    excluding dates, times and short order numbers.
    """
    for start, end, raw in _iter_runs(text):
        plus = raw.lstrip().startswith("+")
        digits = re.sub(r"\D", "", raw)
        if plus and 8 <= len(digits) <= 15:
            yield start, end
        elif not plus and 10 <= len(digits) <= 15:
            yield start, end
