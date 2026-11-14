"""Observe participant count and signature validity for a sync aggregate."""

from __future__ import annotations

from typing import TYPE_CHECKING

from tests.generators.compliance_runners.state_transition.validation_helpers import bls_enabled

if TYPE_CHECKING:
    from tests.generators.compliance_runners.state_transition.evaluation.coverage_dsl import (
        Context,
    )


def observe_attributes(ctx: Context) -> dict[str, object]:
    spec, pre, aggregate = ctx.spec, ctx.pre, ctx.operation
    bits = aggregate.sync_committee_bits
    participant_count = int(spec.get_set_bit_count(bits))
    committee_size = int(spec.SYNC_COMMITTEE_SIZE)
    participation_level = (
        "FULL"
        if participant_count == committee_size
        else "MAJORITY"
        if participant_count > committee_size // 2
        else "EMPTY"
    )
    participant_pubkeys = [
        pubkey for pubkey, bit in zip(pre.current_sync_committee.pubkeys, bits, strict=True) if bit
    ]
    previous_slot = max(pre.slot, spec.Slot(1)) - 1
    domain = spec.get_domain(
        pre, spec.DOMAIN_SYNC_COMMITTEE, spec.compute_epoch_at_slot(previous_slot)
    )
    signing_root = spec.compute_signing_root(
        spec.get_block_root_at_slot(pre, previous_slot), domain
    )
    with bls_enabled():
        signature_valid = bool(
            spec.eth_fast_aggregate_verify(
                participant_pubkeys, signing_root, aggregate.sync_committee_signature
            )
        )
    return {
        "observed_participation_level": participation_level,
        "observed_signature_valid": signature_valid,
    }
