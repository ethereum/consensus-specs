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
    require_post: bool = False
    materializer_module: str | None = None


RUNNERS: dict[str, tuple[str, ...]] = {
    "operations": (
        "block_header",
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
        "effective_balance_updates",
        "eth1_data_reset",
        "historical_summaries_update",
        "inactivity_updates",
        "justification_and_finalization",
        "participation_flag_updates",
        "pending_consolidations",
        "pending_deposits",
        "ptc_window",
        "randao_mixes_reset",
        "slashings",
        "slashings_reset",
        "sync_committee_updates",
        "registry_updates",
        "rewards_and_penalties",
        "proposer_lookahead",
    ),
    "sanity": ("blocks", "slots"),
}
# Temporarily excluded until its fork-epoch setup is resolved.
DISABLED_HANDLERS = {"blocks", "payload_attestation"}
HANDLERS = tuple(
    handler
    for handlers in RUNNERS.values()
    for handler in handlers
    if handler not in DISABLED_HANDLERS
)
PROVIDERS = (
    Provider("block_header", "block_header", "operations", "block_header"),
    Provider("process_operations", "operations", "sanity", "blocks"),
    Provider("process_operations_dispatch", "operations_dispatch", "sanity", "blocks"),
    Provider("process_slot", "slot_processing", "sanity", "slots"),
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
        require_post=True,
    ),
    Provider(
        "builder_exit_request",
        "builder_exit_request",
        "operations",
        "builder_exit_request",
        require_post=True,
    ),
    Provider(
        "consolidation_request",
        "consolidation_request",
        "operations",
        "consolidation_request",
        require_post=True,
    ),
    Provider(
        "deposit_request", "deposit_request", "operations", "deposit_request", require_post=True
    ),
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
    Provider(
        "withdrawal_request",
        "withdrawal_request",
        "operations",
        "withdrawal_request",
        require_post=True,
    ),
    Provider(
        "builder_pending_withdrawal_processing",
        "builder_pending_withdrawal_processing",
        "operations",
        "withdrawals",
        require_post=True,
        materializer_module="withdrawal_processing",
    ),
    Provider(
        "withdrawal_processing",
        "withdrawal_processing",
        "operations",
        "withdrawals",
        require_post=True,
    ),
    Provider(
        "builder_pending_payments",
        "builder_pending_payments",
        "epoch_processing",
        "builder_pending_payments",
        require_post=True,
    ),
    Provider(
        "effective_balance_updates_body",
        "effective_balance_updates",
        "epoch_processing",
        "effective_balance_updates",
    ),
    Provider(
        "eth1_data_reset",
        "eth1_data_reset",
        "epoch_processing",
        "eth1_data_reset",
        require_post=True,
    ),
    Provider(
        "historical_summaries_update",
        "historical_summaries_update",
        "epoch_processing",
        "historical_summaries_update",
        require_post=True,
    ),
    Provider(
        "inactivity_updates",
        "inactivity_updates",
        "epoch_processing",
        "inactivity_updates",
        require_post=True,
    ),
    Provider(
        "inactivity_updates_loop",
        "inactivity_updates_loop",
        "epoch_processing",
        "inactivity_updates",
        require_post=True,
    ),
    Provider(
        "justification_and_finalization",
        "justification_and_finalization",
        "epoch_processing",
        "justification_and_finalization",
        require_post=True,
    ),
    Provider(
        "registry_updates",
        "registry_updates",
        "epoch_processing",
        "registry_updates",
        require_post=True,
    ),
    Provider(
        "rewards_and_penalties",
        "rewards_and_penalties",
        "epoch_processing",
        "rewards_and_penalties",
        require_post=True,
    ),
    Provider(
        "proposer_lookahead",
        "proposer_lookahead",
        "epoch_processing",
        "proposer_lookahead",
        require_post=True,
    ),
    Provider(
        "participation_flag_updates",
        "participation_flag_updates",
        "epoch_processing",
        "participation_flag_updates",
        require_post=True,
    ),
    Provider(
        "pending_consolidations",
        "pending_consolidations",
        "epoch_processing",
        "pending_consolidations",
        require_post=True,
    ),
    Provider(
        "pending_deposits",
        "pending_deposits",
        "epoch_processing",
        "pending_deposits",
        require_post=True,
    ),
    Provider("ptc_window", "ptc_window", "epoch_processing", "ptc_window", require_post=True),
    Provider(
        "randao_mixes_reset",
        "randao_mixes_reset",
        "epoch_processing",
        "randao_mixes_reset",
        require_post=True,
    ),
    Provider("slashings", "slashings", "epoch_processing", "slashings", require_post=True),
    Provider(
        "slashings_reset",
        "slashings_reset",
        "epoch_processing",
        "slashings_reset",
        require_post=True,
    ),
    Provider(
        "sync_committee_updates",
        "sync_committee_updates",
        "epoch_processing",
        "sync_committee_updates",
        require_post=True,
    ),
)
