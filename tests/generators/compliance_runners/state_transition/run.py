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
from .provider import PROFILES, run


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--handler", choices=(*HANDLERS, "all"), default="all")
    parser.add_argument("--profile", choices=PROFILES, default="standard")
    parser.add_argument("--preset", choices=("minimal", "mainnet"), default="minimal")
    parser.add_argument("--comptests-output", type=Path)
    args = parser.parse_args()
    return run(args.handler, args.comptests_output, args.profile, args.preset)


if __name__ == "__main__":
    raise SystemExit(main())
