"""Independent validation for Gloas payload-attestation compliance vectors."""

from __future__ import annotations

from ..validation import Check, decode

from pathlib import Path
from typing import Any

from ruamel.yaml import YAML

from eth_consensus_specs.gloas import minimal as spec

_YAML = YAML(typ="safe")

def recover(pre: Any, operation: Any) -> dict[str, Any]:
    data = operation.data
    indexed = spec.get_indexed_payload_attestation(pre, operation)
    nonempty = len(indexed.attesting_indices) > 0
    aggregation_bits = list(operation.aggregation_bits)
    if not any(aggregation_bits):
        attesting_indices_profile = "EMPTY"
    elif all(aggregation_bits):
        attesting_indices_profile = "ALL"
    else:
        attesting_indices_profile = "PARTIAL"
    signature_valid = (
        "NA"
        if not nonempty
        else ("T" if spec.is_valid_indexed_payload_attestation(pre, indexed) else "F")
    )
    result = {
        "parent_root_matches": data.beacon_block_root == pre.latest_block_header.parent_root,
        "slot_is_previous": data.slot + 1 == pre.slot,
        "attesting_indices_profile": attesting_indices_profile,
        "attesting_indices_nonempty": nonempty,
        "signature_valid": signature_valid,
    }
    if not result["parent_root_matches"]:
        outcome = "REJECT_PARENT_ROOT"
    elif not result["slot_is_previous"]:
        outcome = "REJECT_SLOT"
    elif not nonempty:
        outcome = "REJECT_EMPTY"
    elif signature_valid != "T":
        outcome = "REJECT_SIGNATURE"
    else:
        outcome = "ACCEPT"
    result["outcome"] = outcome
    return result

def validate_case(case_dir: Path) -> tuple[list[Check], list[str]]:
    pre = decode(case_dir / "pre.ssz_snappy", spec.BeaconState)
    operation = decode(case_dir / "payload_attestation.ssz_snappy", spec.PayloadAttestation)
    claimed = _YAML.load((case_dir / "dimensions.yaml").read_text())["claimed"]
    actual = recover(pre, operation)
    checks = [
        Check(name, value, actual.get(name), "ok" if actual.get(name) == value else "mismatch")
        for name, value in claimed.items()
    ]
    return checks, []
