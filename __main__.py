"""Command line entry point.

    python -m claimcheck DRAFT --facts SHEET.json [--facts OTHER.json] [--llm off|mock|anthropic]

Exit codes: 0 ready to publish, 1 blocked, 2 bad input.
"""
from __future__ import annotations

import argparse
import sys

from .llm import Resolver
from .models import InputError
from .pipeline import run
from .report import to_json, to_markdown


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(prog="claimcheck", description="Check numbers in campaign copy against verified fact sheets.")
    ap.add_argument("draft", help="Markdown draft with front matter (voice, featured_org)")
    ap.add_argument("--facts", action="append", required=True, help="Fact sheet JSON; repeat for more than one org")
    ap.add_argument("--llm", choices=["off", "mock", "anthropic"], default="off", help="How to resolve ambiguous claims (default: off)")
    ap.add_argument("--fixtures", help="Recorded model replies, required for --llm mock")
    ap.add_argument("--out", help="Also write the Markdown report to this file")
    ap.add_argument("--json", dest="json_out", help="Also write a JSON report to this file")
    args = ap.parse_args(argv)

    try:
        resolver = Resolver(args.llm, args.fixtures)
        rep = run(args.draft, args.facts, resolver)
    except (InputError, ValueError) as e:
        print(f"INPUT ERROR: {e}", file=sys.stderr)
        return 2

    md = to_markdown(rep)
    print(md)
    if args.out:
        with open(args.out, "w", encoding="utf-8") as fh:
            fh.write(md + "\n")
    if args.json_out:
        with open(args.json_out, "w", encoding="utf-8") as fh:
            fh.write(to_json(rep) + "\n")
    return 0 if rep.ready else 1


if __name__ == "__main__":
    sys.exit(main())
