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
        "attester_slashing",
        "bls_to_execution_change",
        "builder_deposit_request",
        "builder_exit_request",
        "consolidation_request",
        "deposit_request",
        "execution_payload_bid",
        "parent_execution_payload",
        "payload_attestation",
        "proposer_slashing",
        "sync_aggregate",
        "voluntary_exit",
        "withdrawal_request",
        "withdrawals",
    ),
    "epoch_processing": (
        "builder_pending_payments",
        "pending_consolidations",
        "pending_deposits",
        "ptc_window",
    ),
}
HANDLERS = tuple(handler for handlers in RUNNERS.values() for handler in handlers)
# PROVIDERS = tuple(
#     Provider(name=handler, module=handler, runner=runner, handler=handler)
#     for runner, handlers in RUNNERS.items()
#     for handler in handlers
PROVIDERS = (
    Provider("attestation", "attestation", "operations", "attestation"),
    Provider("attester_slashing", "attester_slashing", "operations", "attester_slashing"),
    Provider(
        "bls_to_execution_change",
        "bls_to_execution_change",
        "operations",
        "bls_to_execution_change",
    ),
    Provider(
        "builder_deposit_request",
        "builder_deposit_request",
        "operations",
        "builder_deposit_request",
    ),
    Provider("builder_exit_request", "builder_exit_request", "operations", "builder_exit_request"),
    Provider(
        "consolidation_request",
        "consolidation_request",
        "operations",
        "consolidation_request",
    ),
    Provider("deposit_request", "deposit_request", "operations", "deposit_request"),
    # Provider(
    #     "execution_payload_bid",
    #     "execution_payload_bid",
    #     "operations",
    #     "execution_payload_bid",
    # ),
    Provider("bid_processing", "bid_processing", "operations", "execution_payload_bid"),
    Provider(
        "parent_execution_payload",
        "parent_execution_payload",
        "operations",
        "parent_execution_payload",
    ),
    Provider("payload_attestation", "payload_attestation", "operations", "payload_attestation"),
    Provider("proposer_slashing", "proposer_slashing", "operations", "proposer_slashing"),
    Provider("sync_aggregate", "sync_aggregate", "operations", "sync_aggregate"),
    Provider("voluntary_exit", "voluntary_exit", "operations", "voluntary_exit"),
    Provider("withdrawal_request", "withdrawal_request", "operations", "withdrawal_request"),
    # Provider("withdrawals", "withdrawals", "operations", "withdrawals"),
    Provider(
        "builder_pending_withdrawal_processing",
        "withdrawal_processing.builder_pending_withdrawal_processing",
        "operations",
        "withdrawals",
    ),
    Provider(
        "withdrawal_processing",
        "withdrawal_processing.withdrawal_processing",
        "operations",
        "withdrawals",
    ),
    Provider(
        "builder_pending_payments",
        "builder_pending_payments",
        "epoch_processing",
        "builder_pending_payments",
    ),
    Provider(
        "pending_consolidations",
        "pending_consolidations",
        "epoch_processing",
        "pending_consolidations",
    ),
    Provider("pending_deposits", "pending_deposits", "epoch_processing", "pending_deposits"),
    Provider("ptc_window", "ptc_window", "epoch_processing", "ptc_window"),
)
