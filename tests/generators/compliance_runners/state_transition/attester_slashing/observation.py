"""Observe attester-slashing predicates from the operation and pre-state."""

from tests.generators.compliance_runners.state_transition.validation_helpers import bls_enabled


def observe_attributes(ctx):
    spec, pre, slashing = ctx.spec, ctx.pre, ctx.operation
    first, second = slashing.attestation_1, slashing.attestation_2
    with bls_enabled():
        first_valid = bool(spec.is_valid_indexed_attestation(pre, first))
        second_valid = bool(spec.is_valid_indexed_attestation(pre, second))
    data_slashable = bool(spec.is_slashable_attestation_data(first.data, second.data))
    indices_well_formed = len(first.attesting_indices) > 0 and list(
        first.attesting_indices
    ) == sorted(set(first.attesting_indices))
    current_epoch = spec.get_current_epoch(pre)
    intersection = set(first.attesting_indices).intersection(second.attesting_indices)
    slashable_intersection = any(
        spec.is_slashable_validator(pre.validators[index], current_epoch) for index in intersection
    )
    intersection_size = {
        0: "NONE",
        1: "ONE",
        2: "TWO",
    }.get(len(intersection), "THREE_OR_MORE")
    return {
        "observed_attestation_data_slashable": data_slashable,
        "observed_attestation_1_indices_well_formed": bool(indices_well_formed),
        "observed_attestation_1_valid": first_valid,
        "observed_attestation_2_valid": second_valid,
        "observed_intersection_size": intersection_size,
        "observed_slashable_intersection": slashable_intersection,
    }
