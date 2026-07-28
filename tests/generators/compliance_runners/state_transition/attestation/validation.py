"""Independent validation for Gloas attestation compliance vectors."""

from __future__ import annotations

import sys
from pathlib import Path
from typing import Any

import snappy
from ruamel.yaml import YAML

from eth_consensus_specs.gloas import minimal as spec

_YAML = YAML(typ="safe")


def _decode(path: Path, sedes: Any) -> Any:
    return sedes.decode_bytes(snappy.decompress(path.read_bytes()))


def outcome(pre: Any, attestation: Any) -> str:
    data, current = attestation.data, spec.get_current_epoch(pre)
    if data.target.epoch not in (spec.get_previous_epoch(pre), current):
        return "REJECT_TARGET_EPOCH_OUT_OF_WINDOW"
    if data.target.epoch != spec.compute_epoch_at_slot(data.slot):
        return "REJECT_TARGET_EPOCH_SLOT_MISMATCH"
    if data.slot + spec.MIN_ATTESTATION_INCLUSION_DELAY > pre.slot:
        return "REJECT_INCLUSION_DELAY"
    if data.index >= 2:
        return "REJECT_INDEX"
    try:
        indices, count = (
            spec.get_committee_indices(attestation.committee_bits),
            spec.get_committee_count_per_slot(pre, data.target.epoch),
        )
        if any(index >= count for index in indices):
            return "REJECT_COMMITTEE_INDEX"
        offset = 0
        for index in indices:
            committee = spec.get_beacon_committee(pre, data.slot, index)
            if not any(attestation.aggregation_bits[offset + i] for i in range(len(committee))):
                return "REJECT_COMMITTEE_EMPTY"
            offset += len(committee)
        if len(attestation.aggregation_bits) != offset:
            return "REJECT_AGGREGATION_LENGTH"
        if not spec.is_valid_indexed_attestation(
            pre, spec.get_indexed_attestation(pre, attestation)
        ):
            return "REJECT_SIGNATURE"
    except (AssertionError, IndexError):
        return "REJECT_SIGNATURE"
    return "ACCEPT_CURRENT" if data.target.epoch == current else "ACCEPT_PREVIOUS"


def main() -> int:
    root = Path(sys.argv[1]) if len(sys.argv) > 1 else Path(__file__).parent / "reftests"
    cases, failures = sorted(root.glob("**/operations/attestation/**/case_*")), 0
    if not cases:
        print(f"No cases found under {root}")
        return 1
    for case in cases:
        pre = _decode(case / "pre.ssz_snappy", spec.BeaconState)
        attestation = _decode(case / "attestation.ssz_snappy", spec.Attestation)
        claimed = _YAML.load((case / "dimensions.yaml").read_text())["claimed"]
        actual = outcome(pre, attestation)
        errors = []
        post_path = case / "post.ssz_snappy"
        if actual.startswith("REJECT_"):
            if post_path.exists():
                errors.append("rejected operation has a post state")
        elif not post_path.exists():
            errors.append("accepted operation is missing post state")
        else:
            oracle, post = pre.copy(), _decode(post_path, spec.BeaconState)
            spec.process_attestation(oracle, attestation)
            if oracle.hash_tree_root() != post.hash_tree_root():
                errors.append("post does not match spec re-execution")
            data = attestation.data
            payment_index = (
                int(spec.SLOTS_PER_EPOCH) + int(data.slot) % int(spec.SLOTS_PER_EPOCH)
                if data.target.epoch == spec.get_current_epoch(pre)
                else int(data.slot) % int(spec.SLOTS_PER_EPOCH)
            )
            increased = (
                pre.builder_pending_payments[payment_index].weight
                < post.builder_pending_payments[payment_index].weight
            )
            if increased != claimed["payment_weight_increased"]:
                errors.append(
                    f"payment_weight_increased: claimed={claimed['payment_weight_increased']} actual={increased}"
                )
        if actual != claimed["outcome"]:
            errors.append(f"outcome: claimed={claimed['outcome']} actual={actual}")
        failures += len(errors)
        print(f"{case.name}: {'OK' if not errors else 'FAIL'}")
        for error in errors:
            print(f"    {error}")
    print(f"{'PASSED' if not failures else 'FAILED'}: {len(cases)} cases")
    return int(bool(failures))


if __name__ == "__main__":
    raise SystemExit(main())
