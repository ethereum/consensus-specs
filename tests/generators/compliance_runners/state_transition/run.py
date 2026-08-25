"""Generate and validate state-transition compliance cases.

Usage:
    uv run python -m tests.generators.compliance_runners.state_transition.run
    uv run python -m tests.generators.compliance_runners.state_transition.run --handler withdrawals
"""

from __future__ import annotations

import argparse
from importlib import import_module
from pathlib import Path

from .validation import HANDLERS, main as validate


def run(handler: str, comptests_output: Path | None = None) -> int:
    handlers = HANDLERS if handler == "all" else (handler,)
    result = 0
    for current_handler in handlers:
        output_dir = (
            comptests_output / "tests"
            if comptests_output is not None
            else Path(__file__).parent / current_handler / "reftests"
        )
        coverage = import_module(f".{current_handler}.coverage", __package__)
        coverage.materialize_profile("standard", output_dir=output_dir)
        print()
        result |= validate(output_dir)
    return result


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--handler", choices=(*HANDLERS, "all"), default="all")
    parser.add_argument("--comptests-output", type=Path)
    args = parser.parse_args()
    return run(args.handler, args.comptests_output)


if __name__ == "__main__":
    raise SystemExit(main())
