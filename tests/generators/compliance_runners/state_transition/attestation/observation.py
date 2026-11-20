"""Recover attestation predicates and payment effects independently of claims."""

from typing import Any

from tests.generators.compliance_runners.state_transition.validation_helpers import bls_enabled


def _committee_dimensions(spec: Any, pre: Any, attestation: Any) -> tuple[bool, bool, bool]:
    """Recover independent committee-index, nonempty, and length predicates."""
    try:
        indices = spec.get_committee_indices(attestation.committee_bits)
        count = spec.get_committee_count_per_slot(pre, attestation.data.target.epoch)
    except (AssertionError, IndexError):
        return False, False, False
    indices_valid = all(index < count for index in indices)
    if not indices_valid:
        return False, False, False
    offset = 0
    nonempty = True
    try:
        for index in indices:
            committee = spec.get_beacon_committee(pre, attestation.data.slot, index)
            end = min(offset + len(committee), len(attestation.aggregation_bits))
            bits = attestation.aggregation_bits[offset:end]
            if len(bits) != len(committee) or not any(bits):
                nonempty = False
            offset += len(committee)
        return indices_valid, nonempty, len(attestation.aggregation_bits) == offset
    except (AssertionError, IndexError):
        return False, False, False


def _signature_valid(spec: Any, pre: Any, attestation: Any) -> bool:
    try:
        return bool(
            spec.is_valid_indexed_attestation(pre, spec.get_indexed_attestation(pre, attestation))
        )
    except (AssertionError, IndexError):
        return False


def _is_attestation_same_slot(spec: Any, pre: Any, data: Any) -> bool:
    try:
        return bool(spec.is_attestation_same_slot(pre, data))
    except AssertionError:
        return False


def _sets_new_participation_flag(spec: Any, pre: Any, attestation: Any, same_slot: bool) -> bool:
    if not same_slot:
        return False
    try:
        flag_indices = spec.get_attestation_participation_flag_indices(
            pre,
            attestation.data,
            pre.slot - attestation.data.slot,
            pre.latest_block_header.slot,
        )
        participation = (
            pre.current_epoch_participation
            if attestation.data.target.epoch == spec.get_current_epoch(pre)
            else pre.previous_epoch_participation
        )
        return any(
            any(not spec.has_flag(participation[index], flag) for flag in flag_indices)
            for index in spec.get_attesting_indices(pre, attestation)
        )
    except (AssertionError, IndexError):
        return False


def observe_attributes(ctx) -> dict[str, Any]:
    spec, pre, attestation = ctx.spec, ctx.pre, ctx.operation
    data = attestation.data
    current = spec.get_current_epoch(pre)
    target_in_window = data.target.epoch in (spec.get_previous_epoch(pre), current)
    target_matches_slot = data.target.epoch == spec.compute_epoch_at_slot(data.slot)
    inclusion_delay_ok = data.slot + spec.MIN_ATTESTATION_INCLUSION_DELAY <= pre.slot
    committee_indices_valid, committee_nonempty, aggregation_length_valid = _committee_dimensions(
        spec, pre, attestation
    )
    with bls_enabled():
        signature_valid = _signature_valid(spec, pre, attestation)
    target_is_current = data.target.epoch == current
    same_slot = _is_attestation_same_slot(spec, pre, data)
    payment_index = (
        int(spec.SLOTS_PER_EPOCH) + int(data.slot) % int(spec.SLOTS_PER_EPOCH)
        if target_is_current
        else int(data.slot) % int(spec.SLOTS_PER_EPOCH)
    )
    pending_payment_amount_positive = (
        pre.builder_pending_payments[payment_index].withdrawal.amount > 0
    )
    sets_new_participation_flag = _sets_new_participation_flag(spec, pre, attestation, same_slot)

    payment_weight_increased = bool(
        ctx.post is not None
        and ctx.post.builder_pending_payments[payment_index].weight
        > pre.builder_pending_payments[payment_index].weight
    )
    values = {
        "target_epoch_in_window": target_in_window,
        "target_epoch_matches_slot": target_matches_slot,
        "inclusion_delay_ok": inclusion_delay_ok,
        "index_valid": data.index < 2,
        "committee_indices_valid": committee_indices_valid,
        "committee_nonempty": committee_nonempty,
        "aggregation_length_valid": aggregation_length_valid,
        "signature_valid": signature_valid,
        "target_is_current": target_is_current,
        "attestation_is_same_slot": same_slot,
        "pending_payment_amount_positive": pending_payment_amount_positive,
        "sets_new_participation_flag": sets_new_participation_flag,
        "payment_weight_increased": payment_weight_increased,
        "accepted": ctx.post is not None,
    }

    return {f"observed_{name}": bool(value) for name, value in values.items()}
