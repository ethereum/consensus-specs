"""CLI for validating state-transition compliance cases."""

from __future__ import annotations

import argparse
from pathlib import Path

from .provider import discover_handlers, validate_handler


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--test-dir", type=Path, required=True)
    parser.add_argument(
        "--cases",
        type=str,
        help="comma-separated case names to validate, e.g. case_0205,case_0206",
    )
    args = parser.parse_args()
    test_dir = args.test_dir
    selected_cases = (
        {case.strip() for case in args.cases.split(",") if case.strip()} if args.cases else None
    )

    handlers = tuple(discover_handlers(test_dir))
    result = 0
    for handler in handlers:
        result |= validate_handler(test_dir, handler, selected_cases)
    return result


if __name__ == "__main__":
    raise SystemExit(main())
