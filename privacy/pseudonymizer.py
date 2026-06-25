"""Consistent pseudonymisation.

Redaction here is *pseudonymisation*, not deletion (GDPR Art. 4(5)): every PII
value is replaced by a stable placeholder token, and the **same** value always
maps to the **same** token. That preserves the analytic utility the WhatsApp
analyser needs — you can still count messages per person, build per-user
timelines and see who talks to whom — while the underlying identities are gone.

Tokens are word-character only (``Person_1``, ``Phone_2`` …) on purpose: they
survive the analyser's ``user: message`` parser unchanged and read cleanly in a
word cloud, where ``<PERSON_1>`` style brackets would be split or mangled.

Two numbering modes:

* sequential (default) — ``Person_1``, ``Person_2`` … in first-seen order.
* stable — a short salted HMAC of the value, so the same person gets the same
  token across *different* exports without ever storing the mapping. Use this
  when you need to correlate redacted chats; keep the salt secret.
"""
from __future__ import annotations

import hashlib
import hmac
import os
import re
from typing import Dict, List, Sequence, Tuple

from .engines import (
    CARD,
    CNIC,
    EMAIL,
    IBAN,
    IP,
    LOCATION,
    PERSON,
    PHONE,
    Span,
    URL,
    resolve_overlaps,
)

# Human-readable token prefix per entity type.
TOKEN_PREFIX = {
    PERSON: "Person",
    PHONE: "Phone",
    EMAIL: "Email",
    CARD: "Card",
    CNIC: "CNIC",
    IBAN: "IBAN",
    URL: "Link",
    IP: "IP",
    LOCATION: "Place",
}


def _normalise(entity_type: str, value: str) -> str:
    """Collapse surface variants so they share one token."""
    value = value.strip()
    if entity_type == PHONE:
        return re.sub(r"\D", "", value)  # ignore spaces/dashes/parens
    if entity_type in (EMAIL, PERSON, URL):
        return value.lower()
    return value


class Pseudonymizer:
    def __init__(self, stable: bool = False, salt: str | None = None) -> None:
        self.stable = stable
        self._salt = (salt or os.environ.get("REDACT_SALT", "")).encode()
        self._maps: Dict[str, Dict[str, str]] = {}      # type -> {norm: token}
        self._counters: Dict[str, int] = {}             # type -> next index
        self._examples: Dict[str, str] = {}             # token -> first surface form

    def token_for(self, entity_type: str, value: str) -> str:
        key = _normalise(entity_type, value)
        bucket = self._maps.setdefault(entity_type, {})
        token = bucket.get(key)
        if token is None:
            prefix = TOKEN_PREFIX.get(entity_type, "Redacted")
            if self.stable:
                digest = hmac.new(self._salt, f"{entity_type}:{key}".encode(), hashlib.sha256)
                token = f"{prefix}_{digest.hexdigest()[:8]}"
            else:
                idx = self._counters.get(entity_type, 0) + 1
                self._counters[entity_type] = idx
                token = f"{prefix}_{idx}"
            bucket[key] = token
            self._examples.setdefault(token, value.strip())
        return token

    def replace(self, text: str, spans: Sequence[Span]) -> Tuple[str, List[Span]]:
        """Apply ``spans`` to ``text``; return (redacted_text, accepted_spans)."""
        accepted = resolve_overlaps(spans)
        out: List[str] = []
        last = 0
        for s in accepted:
            out.append(text[last : s.start])
            out.append(self.token_for(s.entity_type, s.text))
            last = s.end
        out.append(text[last:])
        return "".join(out), accepted

    def unique_counts(self) -> Dict[str, int]:
        return {etype: len(bucket) for etype, bucket in self._maps.items()}
