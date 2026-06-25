"""Unit tests for the PII redaction pipeline.

These run against the dependency-free RegexEngine so they pass anywhere with no
extra installs. The Presidio path is exercised only when it is importable
(skipped otherwise), and only on detections both engines must agree on.

Run with:  python -m unittest discover -s privacy/tests
"""
import os
import unittest

from privacy.engines import (
    CARD,
    CNIC,
    EMAIL,
    PERSON,
    PHONE,
    RegexEngine,
    build_engine,
)
from privacy.patterns import luhn_ok
from privacy.redactor import Redactor

SYNTHETIC = (
    "2/14/23, 9:02 PM - Ali Raza: Hey Sara, email me at ali.raza@example.com\n"
    "2/14/23, 9:03 PM - Sara Khan: Sure, call +92 300 1234567 or 0321-9876543\n"
    "2/14/23, 9:08 PM - Ali Raza: my CNIC is 42101-1234567-1 and card 4111 1111 1111 1111\n"
)


def _regex_redactor():
    return Redactor(engine=RegexEngine())


class TestPatterns(unittest.TestCase):
    def test_luhn(self):
        self.assertTrue(luhn_ok("4111111111111111"))
        self.assertFalse(luhn_ok("4111111111111112"))


class TestStructuredRedaction(unittest.TestCase):
    def setUp(self):
        self.r = _regex_redactor()
        self.out = self.r.redact_text(SYNTHETIC)

    def test_email_removed(self):
        self.assertNotIn("ali.raza@example.com", self.out)
        self.assertIn("Email_1", self.out)

    def test_phone_removed(self):
        self.assertNotIn("+92 300 1234567", self.out)
        self.assertNotIn("0321-9876543", self.out)

    def test_cnic_removed(self):
        self.assertNotIn("42101-1234567-1", self.out)
        self.assertIn("CNIC_1", self.out)

    def test_card_removed(self):
        self.assertNotIn("4111 1111 1111 1111", self.out)
        self.assertIn("Card_1", self.out)

    def test_senders_pseudonymised(self):
        self.assertNotIn("Ali Raza", self.out)
        self.assertNotIn("Sara Khan", self.out)
        # both participants mapped to distinct, stable Person tokens
        self.assertIn("Person_1", self.out)
        self.assertIn("Person_2", self.out)

    def test_report_counts(self):
        rep = self.r.report()
        self.assertEqual(rep.data_subjects, 2)            # Ali + Sara
        self.assertGreaterEqual(rep.entity_counts.get(EMAIL, 0), 1)
        self.assertGreaterEqual(rep.entity_counts.get(PHONE, 0), 2)
        self.assertEqual(rep.entity_counts.get(CNIC, 0), 1)
        self.assertEqual(rep.entity_counts.get(CARD, 0), 1)


class TestConsistentPseudonyms(unittest.TestCase):
    def test_same_value_same_token(self):
        r = _regex_redactor()
        out = r.redact_text(
            "2/14/23, 9:02 PM - Ali Raza: ping ali.raza@example.com\n"
            "2/14/23, 9:05 PM - Ali Raza: again ali.raza@example.com\n"
        )
        # one sender, one email value -> exactly one token each, reused
        self.assertEqual(out.count("Email_1"), 2)
        self.assertNotIn("Email_2", out)
        self.assertNotIn("Ali Raza", out)

    def test_name_in_body_matches_sender_token(self):
        r = _regex_redactor()
        out = r.redact_text(
            "2/14/23, 9:02 PM - Ali Raza: hi\n"
            "2/14/23, 9:03 PM - Sara Khan: thanks Ali Raza\n"
        )
        # "Ali Raza" addressed in the body gets the same token as the sender
        self.assertNotIn("Ali Raza", out)


class TestStableMode(unittest.TestCase):
    def test_stable_tokens_repeatable(self):
        text = "2/14/23, 9:02 PM - Ali Raza: ali.raza@example.com\n"
        a = Redactor(engine=RegexEngine(), stable=True, salt="s").redact_text(text)
        b = Redactor(engine=RegexEngine(), stable=True, salt="s").redact_text(text)
        self.assertEqual(a, b)                # deterministic across runs
        self.assertNotIn("Person_1", a)        # hashed, not sequential


class TestDataframeMode(unittest.TestCase):
    def test_dataframe_redaction(self):
        try:
            import pandas as pd
        except ImportError:
            self.skipTest("pandas not installed")
        df = pd.DataFrame(
            {
                "user": ["Ali Raza", "Sara Khan", "group_notification"],
                "message": [
                    "mail ali.raza@example.com",
                    "call +92 300 1234567",
                    "Sara Khan joined",
                ],
            }
        )
        out = Redactor(engine=RegexEngine()).redact_dataframe(df)
        self.assertNotIn("Ali Raza", out["user"].tolist())
        self.assertTrue(all("@" not in m for m in out["message"]))
        self.assertIn("group_notification", out["user"].tolist())  # preserved


class TestPresidioParity(unittest.TestCase):
    """Only runs when Presidio + its model are installed."""

    def test_presidio_catches_structured_pii(self):
        engine = build_engine(prefer_presidio=True)
        if engine.name != "presidio":
            self.skipTest("Presidio/spaCy not installed")
        out = Redactor(engine=engine).redact_text(SYNTHETIC)
        self.assertNotIn("ali.raza@example.com", out)
        self.assertNotIn("42101-1234567-1", out)


if __name__ == "__main__":
    unittest.main()
