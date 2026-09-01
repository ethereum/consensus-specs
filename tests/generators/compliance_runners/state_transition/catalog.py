"""Catalog of state-transition runners, handlers, and providers."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class Provider:
    """A module that supplies vectors for one runner/handler pair."""

    name: str
    module: str
    runner: str
    handler: str


RUNNERS: dict[str, tuple[str, ...]] = {
    "operations": (
        "attestation",
        "builder_deposit_request",
        "builder_exit_request",
        "consolidation_request",
        "deposit_request",
        "execution_payload_bid",
        "parent_execution_payload",
        "payload_attestation",
        "proposer_slashing",
        "withdrawal_request",
        "withdrawals",
    ),
    "epoch_processing": (
        "builder_pending_payments",
        "pending_deposits",
        "ptc_window",
    ),
}
HANDLERS = tuple(handler for handlers in RUNNERS.values() for handler in handlers)
PROVIDERS = tuple(
    Provider(name=handler, module=handler, runner=runner, handler=handler)
    for runner, handlers in RUNNERS.items()
    for handler in handlers
)
