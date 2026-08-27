"""Recover and validate Gloas attestation coverage dimensions."""

from __future__ import annotations

from typing import Any, TYPE_CHECKING

from ruamel.yaml import YAML

from eth_consensus_specs.gloas import minimal as spec
from tests.generators.compliance_runners.state_transition.validation import check_dimensions, decode

if TYPE_CHECKING:
    from pathlib import Path

    from tests.generators.compliance_runners.state_transition.validation import Check

_YAML = YAML(typ="safe")


def _committee_dimensions(pre: Any, attestation: Any) -> tuple[bool, bool, bool]:
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


def _signature_valid(pre: Any, attestation: Any) -> bool:
    try:
        return bool(
            spec.is_valid_indexed_attestation(pre, spec.get_indexed_attestation(pre, attestation))
        )
    except (AssertionError, IndexError):
        return False


def _is_attestation_same_slot(pre: Any, data: Any) -> bool:
    try:
        return bool(spec.is_attestation_same_slot(pre, data))
    except AssertionError:
        return False


def _sets_new_participation_flag(pre: Any, attestation: Any, same_slot: bool) -> bool:
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


def recover(pre: Any, attestation: Any) -> dict[str, Any]:
    data = attestation.data
    current = spec.get_current_epoch(pre)
    target_in_window = data.target.epoch in (spec.get_previous_epoch(pre), current)
    target_matches_slot = data.target.epoch == spec.compute_epoch_at_slot(data.slot)
    inclusion_delay_ok = data.slot + spec.MIN_ATTESTATION_INCLUSION_DELAY <= pre.slot
    committee_indices_valid, committee_nonempty, aggregation_length_valid = _committee_dimensions(
        pre, attestation
    )
    signature_valid = _signature_valid(pre, attestation)
    target_is_current = data.target.epoch == current
    same_slot = _is_attestation_same_slot(pre, data)
    payment_index = (
        int(spec.SLOTS_PER_EPOCH) + int(data.slot) % int(spec.SLOTS_PER_EPOCH)
        if target_is_current
        else int(data.slot) % int(spec.SLOTS_PER_EPOCH)
    )
    pending_payment_amount_positive = (
        pre.builder_pending_payments[payment_index].withdrawal.amount > 0
    )
    sets_new_participation_flag = _sets_new_participation_flag(pre, attestation, same_slot)

    if not target_in_window:
        handler_outcome = "REJECT_TARGET_EPOCH_OUT_OF_WINDOW"
    elif not target_matches_slot:
        handler_outcome = "REJECT_TARGET_EPOCH_SLOT_MISMATCH"
    elif not inclusion_delay_ok:
        handler_outcome = "REJECT_INCLUSION_DELAY"
    elif data.index >= 2:
        handler_outcome = "REJECT_INDEX"
    elif not committee_indices_valid:
        handler_outcome = "REJECT_COMMITTEE_INDEX"
    elif not committee_nonempty:
        handler_outcome = "REJECT_COMMITTEE_EMPTY"
    elif not aggregation_length_valid:
        handler_outcome = "REJECT_AGGREGATION_LENGTH"
    elif not signature_valid:
        handler_outcome = "REJECT_SIGNATURE"
    else:
        handler_outcome = "ACCEPT_CURRENT" if target_is_current else "ACCEPT_PREVIOUS"

    payment_weight_increased = (
        handler_outcome.startswith("ACCEPT_")
        and sets_new_participation_flag
        and pending_payment_amount_positive
    )
    return {
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
        "outcome": handler_outcome,
    }


def validate_case(case_dir: Path) -> list[Check]:
    pre = decode(case_dir / "pre.ssz_snappy", spec.BeaconState)
    attestation = decode(case_dir / "attestation.ssz_snappy", spec.Attestation)
    claimed = _YAML.load((case_dir / "dimensions.yaml").read_text())["claimed"]
    actual = recover(pre, attestation)
    return check_dimensions(claimed, actual)
