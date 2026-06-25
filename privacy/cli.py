"""Command-line PII redaction for WhatsApp exports.

Examples
--------
Redact a chat and print the privacy report::

    python -m privacy.cli "WhatsApp Chat.txt" -o clean.txt --report

Force fully-offline detection (no Presidio/spaCy), stable cross-export tokens::

    python -m privacy.cli chat.txt -o clean.txt --offline --stable

Write a machine-readable audit summary alongside the redacted file::

    python -m privacy.cli chat.txt -o clean.txt --json audit.json
"""
from __future__ import annotations

import argparse
import json
import sys

from .engines import build_engine
from .redactor import Redactor


def main(argv=None) -> int:
    p = argparse.ArgumentParser(
        prog="privacy.cli",
        description="Redact PII from a WhatsApp chat export (privacy-by-design).",
    )
    p.add_argument("input", help="path to exported chat .txt, or - for stdin")
    p.add_argument("-o", "--output", help="write redacted transcript here (default: stdout)")
    p.add_argument("--report", action="store_true", help="print the privacy report to stderr")
    p.add_argument("--json", dest="json_path", help="write the report as JSON to this path")
    p.add_argument(
        "--offline",
        action="store_true",
        help="force the dependency-free regex engine (skip Presidio/spaCy)",
    )
    p.add_argument(
        "--stable",
        action="store_true",
        help="salted-hash tokens, stable across exports (set REDACT_SALT)",
    )
    p.add_argument(
        "--llm",
        action="store_true",
        help="also run the optional LLM context pass (off by default; see PRIVACY.md)",
    )
    args = p.parse_args(argv)

    raw = sys.stdin.read() if args.input == "-" else _read(args.input)

    engine = build_engine(prefer_presidio=not args.offline)
    if args.llm:
        from .llm_pass import wrap_with_llm

        engine = wrap_with_llm(engine)

    redactor = Redactor(engine=engine, stable=args.stable)
    clean = redactor.redact_text(raw)
    report = redactor.report()

    if args.output:
        with open(args.output, "w", encoding="utf-8") as fh:
            fh.write(clean)
        print(f"Redacted transcript written to {args.output}", file=sys.stderr)
    else:
        sys.stdout.write(clean)

    if args.json_path:
        with open(args.json_path, "w", encoding="utf-8") as fh:
            json.dump(report.to_dict(), fh, indent=2)
        print(f"Audit summary written to {args.json_path}", file=sys.stderr)

    if args.report or args.output:
        print("\n" + report.render(), file=sys.stderr)
    return 0


def _read(path: str) -> str:
    with open(path, "r", encoding="utf-8") as fh:
        return fh.read()


if __name__ == "__main__":
    raise SystemExit(main())
