"""Generate and validate state-transition compliance cases.

Usage:
    uv run python -m tests.generators.compliance_runners.state_transition.run HANDLER
"""

from __future__ import annotations

import argparse
from importlib import import_module
from pathlib import Path

from .validation import main as validate


def run(handler: str) -> int:
    coverage = import_module(f".{handler}.coverage", __package__)
    coverage.materialize_profile("standard")
    print()
    return validate(Path(__file__).parent / handler / "reftests")


def main() -> int:
    handlers = [
        "attestation",
        "builder_deposit_request",
        "builder_exit_request",
        "builder_pending_payments",
        "consolidation_request",
        "deposit_request",
        "execution_payload_bid",
        "parent_execution_payload",
        "payload_attestation",
        "pending_deposits",
        "proposer_slashing",
        "ptc_window",
        "withdrawal_request",
        "withdrawals",
    ]
    parser = argparse.ArgumentParser()
    parser.add_argument("handler", choices=handlers)
    args = parser.parse_args()
    return run(args.handler)


if __name__ == "__main__":
    raise SystemExit(main())
