"""Generate and validate state-transition compliance cases.

Usage:
    uv run python -m tests.generators.compliance_runners.state_transition.run HANDLER
"""

from __future__ import annotations

import argparse
from collections.abc import Callable
from pathlib import Path
from typing import Any

from .validation import main as validate


def _run_operation(
    handler: str,
    materialize_profile: Callable[[str], Any],
) -> int:
    materialize_profile("standard")
    print()
    return validate(Path(__file__).parent / handler / "reftests")


def _run_execution_payload_bid() -> int:
    from .execution_payload_bid.materializer import main as generate  # noqa: PLC0415

    generate()
    print()
    return validate(Path(__file__).parent / "execution_payload_bid" / "reftests")


def run(handler: str) -> int:
    if handler == "execution_payload_bid":
        return _run_execution_payload_bid()

    if handler == "builder_pending_payments":
        from .builder_pending_payments.coverage import materialize_profile  # noqa: PLC0415

        materialize_profile("standard")
        return validate(Path(__file__).parent / handler / "reftests")

    if handler == "ptc_window":
        from .ptc_window.coverage import materialize_profile  # noqa: PLC0415

        materialize_profile("standard")
        return validate(Path(__file__).parent / handler / "reftests")

    from importlib import import_module

    coverage = import_module(f".{handler}.coverage", __package__)
    return _run_operation(handler, coverage.materialize_profile)


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
