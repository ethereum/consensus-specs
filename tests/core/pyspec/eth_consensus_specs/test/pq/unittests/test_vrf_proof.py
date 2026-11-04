from eth_consensus_specs.test.context import spec_state_test, with_phases
from eth_consensus_specs.test.helpers.constants import PQ
from eth_consensus_specs.test.helpers.keys import get_vrf_proof


@with_phases([PQ])
@spec_state_test
def test_valid_vrf_proof(spec, state):
    proof = spec.VRFProof(data=get_vrf_proof(0))
    assert spec.is_valid_vrf_proof(state, 0, state.slot, proof)
    assert spec.is_valid_vrf_proof(state, 0, state.slot + 1, proof)


@with_phases([PQ])
@spec_state_test
def test_vrf_proof_wrong_leaf(spec, state):
    proof = spec.VRFProof(data=get_vrf_proof(0))
    proof[0] = spec.Bytes32(b"\x01" * 32)
    assert not spec.is_valid_vrf_proof(state, 0, state.slot, proof)


@with_phases([PQ])
@spec_state_test
def test_vrf_proof_of_other_validator(spec, state):
    proof = spec.VRFProof(data=get_vrf_proof(1))
    assert not spec.is_valid_vrf_proof(state, 0, state.slot, proof)
