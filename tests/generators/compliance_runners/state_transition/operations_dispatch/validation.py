"""Recover operation-dispatch dimensions from serialized block vectors."""

from __future__ import annotations

from typing import TYPE_CHECKING

from ruamel.yaml import YAML

from eth_consensus_specs.gloas import minimal as spec
from tests.generators.compliance_runners.state_transition.provider import check_dimensions, decode

if TYPE_CHECKING:
    from pathlib import Path

_YAML = YAML(typ="safe")
_FIELDS = (
    "proposer_slashings",
    "attester_slashings",
    "attestations",
    "voluntary_exits",
    "bls_to_execution_changes",
    "payload_attestations",
)


def validate_case(case_dir: Path):
    pre = decode(case_dir / "pre.ssz_snappy", spec.BeaconState)
    block = decode(case_dir / "blocks_0.ssz_snappy", spec.SignedBeaconBlock).message
    post_path = case_dir / "post.ssz_snappy"
    post = decode(post_path, spec.BeaconState) if post_path.exists() else None
    claimed = _YAML.load((case_dir / "dimensions.yaml").read_text())["claimed"]
    body = block.body
    actual = {
        "counts": {field: len(getattr(body, field)) for field in _FIELDS},
        "accepted": post is not None,
        "outcome": "ACCEPT" if post is not None else "REJECT",
    }
    if body.proposer_slashings and body.voluntary_exits:
        actual["shared_slash_exit"] = (
            body.proposer_slashings[0].signed_header_1.message.proposer_index
            == body.voluntary_exits[0].message.validator_index
        )
    if body.payload_attestations:
        actual["payload_root_matches"] = (
            body.payload_attestations[0].data.beacon_block_root == block.parent_root
        )
    if body.attestations:
        attestation = body.attestations[0]
        parent_slot = int(pre.latest_block_header.slot)
        attestation_slot = int(attestation.data.slot)
        actual.update(
            parent_slot_differs_from_attestation_slot=parent_slot != attestation_slot,
            parent_slot_payload_available=bool(
                pre.execution_payload_availability[
                    parent_slot % int(spec.SLOTS_PER_HISTORICAL_ROOT)
                ]
            ),
            attestation_slot_payload_available=bool(
                pre.execution_payload_availability[
                    attestation_slot % int(spec.SLOTS_PER_HISTORICAL_ROOT)
                ]
            ),
        )
        if post is not None:
            indices = spec.get_attesting_indices(post, attestation)
            actual["head_flag_set"] = bool(indices) and all(
                spec.has_flag(post.current_epoch_participation[index], spec.TIMELY_HEAD_FLAG_INDEX)
                for index in indices
            )
    return check_dimensions(claimed, actual)
