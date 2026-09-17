"""Independent semantic validation for sync-aggregate vectors."""

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


def recover_dimensions(pre: Any, aggregate: Any) -> dict[str, Any]:
    bits = aggregate.sync_committee_bits
    count = int(spec.get_set_bit_count(bits))
    committee_size = int(spec.SYNC_COMMITTEE_SIZE)
    level = (
        "FULL"
        if count == committee_size
        else "MAJORITY"
        if count > committee_size // 2
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
        "participation_level": level,
        "signature_valid": signature_valid,
        "outcome": "ACCEPT" if signature_valid else "REJECT_SIGNATURE",
    }


def validate_case(case_dir: Path) -> list[Check]:
    pre = decode(case_dir / "pre.ssz_snappy", spec.BeaconState)
    aggregate = decode(case_dir / "sync_aggregate.ssz_snappy", spec.SyncAggregate)
    claimed = _YAML.load((case_dir / "dimensions.yaml").read_text())["claimed"]
    return check_dimensions(claimed, recover_dimensions(pre, aggregate))
