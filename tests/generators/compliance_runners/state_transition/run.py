"""Generate and validate state-transition compliance cases.

Usage:
    uv run python -m tests.generators.compliance_runners.state_transition.run
    uv run python -m tests.generators.compliance_runners.state_transition.run --handler withdrawals
    uv run python -m tests.generators.compliance_runners.state_transition.run --profile smoke
"""

from __future__ import annotations

import argparse
from pathlib import Path

from .catalog import HANDLERS
from .provider import materialize_handler

PROFILES = ("all", "smoke", "normal", "exceptional", "standard")


def run(
    handler: str,
    comptests_output: Path | None = None,
    profile: str = "standard",
) -> int:
    handlers = HANDLERS if handler == "all" else (handler,)
    for current_handler in handlers:
        output_dir = (
            comptests_output
            if comptests_output is not None
            else Path(__file__).parent / current_handler / "reftests"
        )
        materialize_handler(current_handler, profile, output_dir)
    return 0


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--handler", choices=(*HANDLERS, "all"), default="all")
    parser.add_argument("--profile", choices=PROFILES, default="standard")
    parser.add_argument("--comptests-output", type=Path)
    args = parser.parse_args()
    return run(args.handler, args.comptests_output, args.profile)


if __name__ == "__main__":
    raise SystemExit(main())
