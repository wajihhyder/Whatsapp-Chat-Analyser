"""The redactor: orchestrates detection + pseudonymisation over a WhatsApp chat.

Two entry points share one consistent pseudonym mapping and one running report:

* :meth:`Redactor.redact_text` — sanitise a raw exported ``.txt`` into a
  shareable, identity-free transcript (used by the CLI and to produce safe
  sample data for a public repo).
* :meth:`Redactor.redact_dataframe` — sanitise the analyser's parsed
  DataFrame in place (used to wire privacy-by-design into ``app.py`` with a
  single call, so every chart, the word cloud and the "busy users" table run on
  pseudonymised data).

Sender names get special treatment: they are collected up front, pseudonymised
to ``Person_N`` tokens, and added to the engine's deny-list so the *same* token
is reused wherever that person is addressed by name inside message bodies.
"""
from __future__ import annotations

import re
from collections import Counter
from typing import List, Optional, Sequence

from .engines import PERSON, DetectionEngine, build_engine
from .pseudonymizer import Pseudonymizer
from .report import PrivacyReport

# Matches a WhatsApp message header up to and including the " - " separator,
# tolerating the AM/PM narrow-no-break-space some exports use. Group 1 is the
# timestamp prefix; group 2 is the remainder ("Sender: text" or a system note).
_HEADER_RE = re.compile(
    r"^(\d{1,2}/\d{1,2}/\d{2,4},\s\d{1,2}:\d{2}[\s ]?(?:[AaPp][Mm])?[\s ]?-\s)(.*)$"
)
# "Sender: message" within the remainder. Sender has no colon and is short.
_SENDER_RE = re.compile(r"^([^:\n]{1,60}?):\s(.*)$")


class Redactor:
    def __init__(
        self,
        engine: Optional[DetectionEngine] = None,
        stable: bool = False,
        salt: str | None = None,
    ) -> None:
        self.engine = engine or build_engine()
        self.pseudo = Pseudonymizer(stable=stable, salt=salt)
        self._names: List[str] = []
        self._counts: Counter = Counter()
        self._messages_total = 0
        self._messages_with_pii = 0

    # -- name handling -----------------------------------------------------
    def register_names(self, names: Sequence[str]) -> None:
        """Add known names (chat participants) and pre-assign their tokens.

        Pre-assigning in sorted order makes ``Person_N`` numbering deterministic
        regardless of who happens to speak first.
        """
        merged = {n.strip() for n in self._names}
        merged.update(n.strip() for n in names if n and n.strip())
        # longest-first so "Ali Raza" matches before a bare "Ali"
        self._names = sorted(merged, key=len, reverse=True)
        for name in sorted(merged):
            self.pseudo.token_for(PERSON, name)

    # -- core --------------------------------------------------------------
    def redact_message(self, text: str) -> str:
        """Redact a single message body, updating the running report."""
        spans = self.engine.detect(text, names=self._names or None)
        redacted, accepted = self.pseudo.replace(text, spans)
        self._messages_total += 1
        if accepted:
            self._messages_with_pii += 1
            for s in accepted:
                self._counts[s.entity_type] += 1
        return redacted

    # -- text mode ---------------------------------------------------------
    def redact_text(self, raw: str) -> str:
        lines = raw.split("\n")
        # Pass 1: discover participants so their tokens are stable.
        senders = set()
        for line in lines:
            h = _HEADER_RE.match(line)
            if h:
                s = _SENDER_RE.match(h.group(2))
                if s:
                    senders.add(s.group(1).strip())
        self.register_names(senders)

        # Pass 2: rebuild the transcript with senders + bodies redacted.
        out: List[str] = []
        for line in lines:
            h = _HEADER_RE.match(line)
            if not h:
                # continuation line of a multi-line message
                out.append(self.redact_message(line))
                continue
            prefix, rest = h.group(1), h.group(2)
            s = _SENDER_RE.match(rest)
            if s:
                sender, body = s.group(1).strip(), s.group(2)
                token = self.pseudo.token_for(PERSON, sender)
                out.append(f"{prefix}{token}: {self.redact_message(body)}")
            else:
                out.append(f"{prefix}{self.redact_message(rest)}")
        return "\n".join(out)

    # -- dataframe mode ----------------------------------------------------
    def redact_dataframe(self, df, user_col: str = "user", message_col: str = "message"):
        """Return a copy of ``df`` with the user and message columns redacted."""
        out = df.copy()
        participants = [
            u for u in out[user_col].unique().tolist() if u != "group_notification"
        ]
        self.register_names(participants)
        out[user_col] = out[user_col].map(
            lambda u: u if u == "group_notification" else self.pseudo.token_for(PERSON, u)
        )
        out[message_col] = out[message_col].map(lambda m: self.redact_message(str(m)))
        return out

    # -- report ------------------------------------------------------------
    def report(self) -> PrivacyReport:
        return PrivacyReport(
            engine=self.engine.name,
            entity_counts=dict(self._counts),
            unique_counts=self.pseudo.unique_counts(),
            messages_total=self._messages_total,
            messages_with_pii=self._messages_with_pii,
        )


def redact_text(raw: str, prefer_presidio: bool = True, stable: bool = False):
    """Convenience: redact a raw export, returning (redacted_text, report)."""
    r = Redactor(engine=build_engine(prefer_presidio), stable=stable)
    return r.redact_text(raw), r.report()


def redact_dataframe(df, prefer_presidio: bool = True, stable: bool = False):
    """Convenience: redact a parsed DataFrame, returning (df, report)."""
    r = Redactor(engine=build_engine(prefer_presidio), stable=stable)
    return r.redact_dataframe(df), r.report()
