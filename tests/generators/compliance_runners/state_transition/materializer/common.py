"""Shared concrete-input helpers for state-transition materializers."""

from __future__ import annotations

from typing import Any

from eth_consensus_specs.test.helpers.genesis import create_genesis_state
from tests.generators.compliance_runners.state_transition.materializer.state_preprocessor import (
    common_state_preprocessor,
)

BIG = 10_000_000_000  # 10 Gwei, well above MIN_DEPOSIT_AMOUNT


def set_parent_block(spec: Any, state: Any, hash_match: bool) -> None:
    """Set the parent-block state per state_latest_block_hash_match."""
    if hash_match:
        # Parent block full: hashes must match (use a non-zero hash)
        if bytes(state.latest_block_hash) == b"\x00" * 32:
            state.latest_block_hash = spec.Hash32(b"\x01" * 32)
        state.latest_execution_payload_bid.block_hash = state.latest_block_hash
    else:
        # Parent block empty: hashes must differ
        state.latest_block_hash = spec.Hash32(b"\x00" * 32)
        state.latest_execution_payload_bid.block_hash = spec.Hash32(b"\x01" * 32)


def make_base_state(spec: Any, num_validators: int = 64, preprocess: bool = True) -> Any:
    """Build a preprocessed base state (genesis + optional 2-epoch advance)."""
    state = create_genesis_state(
        spec,
        validator_balances=[spec.MAX_EFFECTIVE_BALANCE] * num_validators,
        activation_threshold=spec.MAX_EFFECTIVE_BALANCE,
    )
    state.builders = type(state.builders)()
    state.builder_pending_payments = type(state.builder_pending_payments)()
    state.builder_pending_withdrawals = type(state.builder_pending_withdrawals)()
    if preprocess:
        state = common_state_preprocessor(spec, state)
    return state
