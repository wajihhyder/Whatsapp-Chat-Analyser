# Privacy & PII Redaction

WhatsApp chat exports are **personal data**: real names, phone numbers, emails,
national ID numbers, even card numbers and home locations. Analysing or sharing
them — or committing a sample to a public repo — exposes all of it.

This module (`privacy/`) removes that data *before* the chat is analysed,
displayed, or shared, and is designed around a single principle:

> **Privacy by design (GDPR Art. 25): the safest place to handle personal data
> is locally, and the safest thing to do with an identifier is to never see it.**

## What it does

- **Detects** PII in a WhatsApp export: people's names, phone numbers (including
  local Pakistani `+92 …` / `03xx-…` formats), emails, **CNIC** national IDs,
  IBANs, credit-card numbers (Luhn-validated), IPs and URLs.
- **Pseudonymises** rather than deletes: each value is replaced by a stable
  token (`Person_1`, `Phone_2`, `CNIC_1` …). The **same value always maps to the
  same token**, so the analytics still work — you can still count messages per
  person and build per-user timelines — but the identities are gone. This is
  *pseudonymisation* in the sense of **GDPR Art. 4(5)**, not mere masking.
- **Reports** what it removed (counts per category, number of distinct data
  subjects) **without ever printing a single real value** — the audit trail a
  data-protection reviewer expects.

## Why local-first (and why the LLM pass is off by default)

The detection runs **entirely on your machine**. There is an *optional* pass
(`--llm`) that asks an LLM to catch context-dependent PII the patterns miss —
but it is **disabled by default and gated behind an explicit flag + API key**,
because sending the chat to a third-party model to find PII means the very data
you are protecting leaves your machine. For a privacy tool that is usually the
wrong trade-off. Treating "should we send this to the cloud?" as a deliberate,
defaulted-to-no decision *is* the privacy engineering — see the warning at the
top of [`privacy/llm_pass.py`](privacy/llm_pass.py).

## How it maps to data-protection practice

| Concern | How this addresses it |
|---|---|
| **Data minimisation** (GDPR Art. 5(1)(c)) | Identifiers are stripped before processing; the analytics never need them. |
| **Pseudonymisation** (Art. 4(5)) | Stable token mapping keeps data useful while de-identifying it. |
| **Privacy by design & default** (Art. 25) | Redaction runs by default in the app; cloud calls are opt-in. |
| **Right to erasure / re-use** (Art. 17) | The redacted transcript is safe to retain, share, or commit. |
| **Localised identifiers** | First-class recognisers for Pakistani CNIC / IBAN / mobile formats, not just US/EU defaults. |

## Architecture

```
chat .txt ──▶ Redactor ──▶ redacted .txt + privacy report
                 │
       ┌─────────┴──────────┐
       │  DetectionEngine   │   pluggable; pick by what's installed
       ├────────────────────┤
       │ RegexEngine        │   offline, zero deps — structured PII + participant names
       │ PresidioEngine     │   the above + spaCy NER for free-text names/places
       │ (+ optional LLM)   │   off by default — context-dependent PII (cloud)
       └────────────────────┘
                 │
         Pseudonymizer        consistent tokens (sequential or salted-hash)
```

The **regex engine has no dependencies** so the tool runs out of the box. The
**Presidio engine is a strict superset** — it reuses the exact same structured
detection and adds NER on top, so enabling it can only catch *more*, never less.

## Usage

**Sanitise an export from the command line:**

```bash
python -m privacy.cli "WhatsApp Chat.txt" -o clean.txt --report
python -m privacy.cli chat.txt -o clean.txt --offline --stable   # no Presidio, stable tokens
python -m privacy.cli chat.txt -o clean.txt --json audit.json     # machine-readable audit
```

**In code:**

```python
from privacy import redact_text
clean, report = redact_text(open("chat.txt", encoding="utf-8").read())
print(report.render())
```

**In the analyser app:** redaction is wired into `app.py` behind a sidebar
toggle (**on by default**); every chart and the word cloud then run on
pseudonymised data, with a "Privacy report" expander showing what was removed.

Try it on the safe synthetic sample:

```bash
python -m privacy.cli sample_data/synthetic_chat.txt --offline --report
```

## Honest limitations

- The offline engine is **high precision**: it catches structured PII and the
  exact names of chat participants, but not bare first names, nicknames, or
  places in free text. That recall gap is exactly what the Presidio engine (with
  a larger spaCy model, e.g. `en_core_web_lg`) and the optional LLM pass address.
- Pseudonymisation is **not anonymisation** — a determined adversary with side
  information can sometimes re-identify. For stronger guarantees, use `--stable`
  with a secret salt and treat the salt as a key, or drop the mapping entirely.
- The WhatsApp line parser targets the common Android `M/D/YY, h:mm AM/PM -`
  export format; other locales may need the regex in `privacy/redactor.py`
  adjusted.

## Tests

```bash
python -m unittest discover -s privacy/tests
```
