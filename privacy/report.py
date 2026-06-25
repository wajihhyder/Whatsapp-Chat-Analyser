"""The privacy report.

After a redaction run this summarises *what* was removed without ever exposing
the values themselves — the audit trail a data-protection reviewer would expect:
which categories of personal data were present, how many distinct data subjects
were involved, and what share of messages carried PII.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict

from .engines import PERSON
from .pseudonymizer import TOKEN_PREFIX


@dataclass
class PrivacyReport:
    engine: str
    entity_counts: Dict[str, int] = field(default_factory=dict)   # total occurrences
    unique_counts: Dict[str, int] = field(default_factory=dict)   # distinct values
    messages_total: int = 0
    messages_with_pii: int = 0

    @property
    def total_redactions(self) -> int:
        return sum(self.entity_counts.values())

    @property
    def data_subjects(self) -> int:
        """Distinct individuals (names) seen — a key GDPR metric."""
        return self.unique_counts.get(PERSON, 0)

    def to_dict(self) -> dict:
        return {
            "engine": self.engine,
            "messages_total": self.messages_total,
            "messages_with_pii": self.messages_with_pii,
            "total_redactions": self.total_redactions,
            "data_subjects": self.data_subjects,
            "entity_counts": dict(self.entity_counts),
            "unique_counts": dict(self.unique_counts),
        }

    def render(self) -> str:
        pct = (
            100 * self.messages_with_pii / self.messages_total
            if self.messages_total
            else 0.0
        )
        lines = [
            "Privacy / PII redaction report",
            "=" * 32,
            f"Engine                : {self.engine}",
            f"Messages scanned      : {self.messages_total}",
            f"Messages with PII     : {self.messages_with_pii} ({pct:.1f}%)",
            f"Total items redacted  : {self.total_redactions}",
            f"Distinct individuals  : {self.data_subjects}",
            "",
            "By category (occurrences / distinct values):",
        ]
        if self.entity_counts:
            for etype in sorted(self.entity_counts, key=lambda e: -self.entity_counts[e]):
                label = TOKEN_PREFIX.get(etype, etype)
                lines.append(
                    f"  - {label:<8}: {self.entity_counts[etype]:>4}"
                    f" / {self.unique_counts.get(etype, 0)}"
                )
        else:
            lines.append("  (none found)")
        lines += [
            "",
            "Note: values are pseudonymised (GDPR Art. 4(5)), not just deleted —",
            "the same value maps to a stable token, so analytics still work while",
            "identities are removed. No personal data appears in this report.",
        ]
        return "\n".join(lines)
