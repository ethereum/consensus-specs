"""Independent validation for Gloas payload-attestation compliance vectors."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

import snappy
from ruamel.yaml import YAML

from eth_consensus_specs.gloas import minimal as spec

_YAML = YAML(typ="safe")


@dataclass
class Check:
    dimension: str
    claimed: Any
    actual: Any
    status: str


def _decode(path: Path, sedes: Any) -> Any:
    return sedes.decode_bytes(snappy.decompress(path.read_bytes()))


def recover(pre: Any, operation: Any) -> dict[str, Any]:
    data = operation.data
    indexed = spec.get_indexed_payload_attestation(pre, operation)
    nonempty = len(indexed.attesting_indices) > 0
    signature_valid = (
        "NA"
        if not nonempty
        else ("T" if spec.is_valid_indexed_payload_attestation(pre, indexed) else "F")
    )
    result = {
        "parent_root_matches": data.beacon_block_root == pre.latest_block_header.parent_root,
        "slot_is_previous": data.slot + 1 == pre.slot,
        "attesting_indices_nonempty": nonempty,
        "signature_valid": signature_valid,
        "state_effected": False,
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
    pre = _decode(case_dir / "pre.ssz_snappy", spec.BeaconState)
    operation = _decode(case_dir / "payload_attestation.ssz_snappy", spec.PayloadAttestation)
    claimed = _YAML.load((case_dir / "dimensions.yaml").read_text())["claimed"]
    actual = recover(pre, operation)
    checks = [
        Check(name, value, actual.get(name), "ok" if actual.get(name) == value else "mismatch")
        for name, value in claimed.items()
    ]
    post_path, errors = case_dir / "post.ssz_snappy", []
    if actual["outcome"].startswith("REJECT_"):
        if post_path.exists():
            errors.append("rejected operation must not have a post state")
        return checks, errors
    if not post_path.exists():
        return checks, ["accepted operation is missing post state"]
    post, oracle = _decode(post_path, spec.BeaconState), pre.copy()
    spec.process_payload_attestation(oracle, operation)
    if oracle.hash_tree_root() != post.hash_tree_root():
        errors.append("post state does not match spec re-execution")
    if pre.hash_tree_root() != post.hash_tree_root():
        errors.append("handler unexpectedly changed state")
    return checks, errors
