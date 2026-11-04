from eth_consensus_specs.test.context import spec_state_test, with_phases
from eth_consensus_specs.test.helpers.constants import PQ
from eth_consensus_specs.test.helpers.keys import get_vrf_selection_proof


@with_phases([PQ])
@spec_state_test
def test_valid_selection_proof(spec, state):
    selection_proof = spec.SelectionProof(data=get_vrf_selection_proof(0))
    assert spec.is_valid_selection_proof(state, 0, state.slot, selection_proof)
    assert spec.is_valid_selection_proof(state, 0, state.slot + 1, selection_proof)


@with_phases([PQ])
@spec_state_test
def test_selection_proof_wrong_leaf(spec, state):
    selection_proof = spec.SelectionProof(data=get_vrf_selection_proof(0))
    selection_proof[0] = spec.Bytes32(b"\x01" * 32)
    assert not spec.is_valid_selection_proof(state, 0, state.slot, selection_proof)


@with_phases([PQ])
@spec_state_test
def test_selection_proof_of_other_validator(spec, state):
    selection_proof = spec.SelectionProof(data=get_vrf_selection_proof(1))
    assert not spec.is_valid_selection_proof(state, 0, state.slot, selection_proof)
