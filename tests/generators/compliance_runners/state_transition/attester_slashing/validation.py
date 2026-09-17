"""Independent semantic validation for attester-slashing vectors."""

from __future__ import annotations

from typing import Any, TYPE_CHECKING

from ruamel.yaml import YAML

from eth_consensus_specs.gloas import minimal as spec
from tests.generators.compliance_runners.state_transition.provider import check_dimensions, decode
from tests.generators.compliance_runners.state_transition.validation_helpers import bls_enabled

if TYPE_CHECKING:
    from pathlib import Path

    from tests.generators.compliance_runners.state_transition.provider import Check


_YAML = YAML(typ="safe")


def intersection_size(indices: set[Any]) -> str:
    """Classify the exact common-attester cardinality for coverage."""
    return {
        0: "NONE",
        1: "ONE",
        2: "TWO",
    }.get(len(indices), "THREE_OR_MORE")


def recover_dimensions(pre: Any, slashing: Any) -> dict[str, Any]:
    first = slashing.attestation_1
    second = slashing.attestation_2
    with bls_enabled():
        first_valid = bool(spec.is_valid_indexed_attestation(pre, first))
        second_valid = bool(spec.is_valid_indexed_attestation(pre, second))
    data_slashable = bool(spec.is_slashable_attestation_data(first.data, second.data))
    first_indices_well_formed = len(first.attesting_indices) > 0 and list(
        first.attesting_indices
    ) == sorted(set(first.attesting_indices))
    current_epoch = spec.get_current_epoch(pre)
    indices = set(first.attesting_indices).intersection(second.attesting_indices)
    slashable_intersection = any(
        spec.is_slashable_validator(pre.validators[index], current_epoch) for index in indices
    )
    if not data_slashable:
        outcome = "REJECT_NOT_SLASHABLE"
    elif not first_indices_well_formed:
        outcome = "REJECT_MALFORMED_FIRST_INDICES"
    elif not first_valid:
        outcome = "REJECT_FIRST_ATTESTATION"
    elif not second_valid:
        outcome = "REJECT_SECOND_ATTESTATION"
    elif not slashable_intersection:
        outcome = "REJECT_NO_SLASHABLE_INTERSECTION"
    else:
        outcome = "ACCEPT"
    return {
        "attestation_data_slashable": data_slashable,
        "attestation_1_indices_well_formed": first_indices_well_formed,
        "attestation_1_valid": first_valid,
        "attestation_2_valid": second_valid,
        "intersection_size": intersection_size(indices),
        "slashable_intersection": slashable_intersection,
        "outcome": outcome,
    }


def validate_case(case_dir: Path) -> list[Check]:
    pre = decode(case_dir / "pre.ssz_snappy", spec.BeaconState)
    slashing = decode(case_dir / "attester_slashing.ssz_snappy", spec.AttesterSlashing)
    claimed = _YAML.load((case_dir / "dimensions.yaml").read_text())["claimed"]
    return check_dimensions(claimed, recover_dimensions(pre, slashing))
