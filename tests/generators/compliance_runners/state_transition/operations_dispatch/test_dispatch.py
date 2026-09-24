"""Check that block integration vectors distinguish the intended behavior."""

from types import SimpleNamespace

from eth_consensus_specs.gloas import minimal as spec
from eth_consensus_specs.utils import bls

from .coverage import build_profile
from .materializer import OperationsDispatchMaterializer


def _vector(scenario: str, accepted: bool):
    materializer = OperationsDispatchMaterializer(spec)
    materializer.test_provider = "process_operations_dispatch"
    _, parts = materializer.materialize_solution(
        SimpleNamespace(scenario=scenario, accepted=accepted)
    )
    encoded = {name: data for name, _, data in parts}
    pre = spec.BeaconState.decode_bytes(encoded["pre"])
    block = spec.SignedBeaconBlock.decode_bytes(encoded["blocks_0"]).message
    post = spec.BeaconState.decode_bytes(encoded["post"]) if "post" in encoded else None
    return pre, block, post


def test_profiles_select_dispatch_scenarios():
    assert {record["scenario"] for record in build_profile("smoke")[1]} == {
        "all_lists",
        "slash_before_exit",
    }
    assert len(build_profile("normal")[1]) == 3
    assert len(build_profile("exceptional")[1]) == 2
    assert len(build_profile("standard")[1]) == 5


def test_slash_then_exit_rejects_but_reverse_order_accepts():
    pre, block, post = _vector("slash_before_exit", accepted=False)
    assert post is None
    old_bls_active = bls.bls_active
    bls.bls_active = True
    try:
        reversed_state = pre.copy()
        spec.process_voluntary_exit(reversed_state, block.body.voluntary_exits[0])
        spec.process_proposer_slashing(reversed_state, block.body.proposer_slashings[0])
    finally:
        bls.bls_active = old_bls_active
    assert reversed_state.validators[1].slashed


def test_invalid_payload_attestation_is_the_rejection_cause():
    pre, block, post = _vector("invalid_payload_attestation", accepted=False)
    assert post is None
    block.body.payload_attestations = spec.PayloadAttestations()
    state_without_attestation = pre.copy()
    old_bls_active = bls.bls_active
    bls.bls_active = True
    try:
        spec.state_transition(
            state_without_attestation,
            spec.SignedBeaconBlock(message=block),
            validate_result=False,
        )
    finally:
        bls.bls_active = old_bls_active
    assert state_without_attestation.slot == block.slot


def test_skipped_slot_attestation_depends_on_parent_slot():
    for scenario, expect_head in (("parent_slot_matches", True), ("parent_slot_mismatches", False)):
        pre, block, post = _vector(scenario, accepted=True)
        assert post is not None
        attestation = block.body.attestations[0]
        parent_slot = pre.latest_block_header.slot
        assert parent_slot != attestation.data.slot
        assert pre.execution_payload_availability[parent_slot]
        assert not pre.execution_payload_availability[attestation.data.slot]
        indices = spec.get_attesting_indices(post, attestation)
        assert indices
        assert all(
            spec.has_flag(post.current_epoch_participation[index], spec.TIMELY_HEAD_FLAG_INDEX)
            is expect_head
            for index in indices
        )
