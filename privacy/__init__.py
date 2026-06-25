"""Privacy-by-design PII redaction for WhatsApp chat exports.

Removes personal data (names, phone numbers, emails, national IDs, cards, …)
from a chat *before* it is analysed or shared, replacing each value with a
stable pseudonym so the analytics still work. Detection runs locally — by
default nothing is sent to any third-party service.

Quick start::

    from privacy import redact_text
    clean, report = redact_text(open("chat.txt", encoding="utf-8").read())
    print(report.render())

Or wire it into the analyser in one line (see ``app.py``)::

    from privacy import Redactor
    df = Redactor().redact_dataframe(df)
"""
from __future__ import annotations

from .engines import DetectionEngine, PresidioEngine, RegexEngine, build_engine
from .redactor import Redactor, redact_dataframe, redact_text
from .report import PrivacyReport

__version__ = "1.0.0"
__all__ = [
    "Redactor",
    "redact_text",
    "redact_dataframe",
    "build_engine",
    "DetectionEngine",
    "RegexEngine",
    "PresidioEngine",
    "PrivacyReport",
]
