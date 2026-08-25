import pytest

from eth_consensus_specs.test.context import (
    always_bls,
    spec_state_test,
    with_eip8025_and_later,
)
from eth_consensus_specs.test.helpers.block import build_empty_block_for_next_slot
from eth_consensus_specs.test.helpers.fork_choice import (
    get_genesis_forkchoice_store_and_block,
)
from eth_consensus_specs.test.helpers.gossip import get_seen
from eth_consensus_specs.test.helpers.keys import privkeys
from eth_consensus_specs.test.helpers.state import state_transition_and_sign_block

TEST_PROOF_TYPE = 1


class RecordingProofEngine:
    def __init__(self, proof=None):
        self.proof = proof
        self.requests = []
        self.retrievals = []
        self.verified = []

    def verify_execution_proof(self, proof):
        self.verified.append(proof)
        return True

    def request_proofs(self, beacon_block_root, new_payload_request, proof_attributes):
        self.requests.append((beacon_block_root, new_payload_request, proof_attributes))

    def get_proof(self, beacon_block_root, proof_type):
        self.retrievals.append((beacon_block_root, proof_type))
        return self.proof


def setup_store_with_block(spec, state):
    store, _anchor_block = get_genesis_forkchoice_store_and_block(spec, state)
    block = build_empty_block_for_next_slot(spec, state)
    signed_block = state_transition_and_sign_block(spec, state, block)
    block_root = signed_block.message.hash_tree_root()
    store.blocks[block_root] = signed_block.message
    store.block_states[block_root] = state.copy()
    store.payloads[block_root] = spec.ExecutionPayloadEnvelope(beacon_block_root=block_root)
    return store, block_root


def make_execution_proof(spec, beacon_block_root, *, proof_type=TEST_PROOF_TYPE):
    return spec.ExecutionProof(
        proof_data=spec.ProofData(b"\x01"),
        proof_type=spec.ProofType(proof_type),
        public_input=spec.PublicInput(beacon_block_root=beacon_block_root),
    )


def make_new_payload_request(spec, payload_envelope):
    return spec.NewPayloadRequest(
        execution_payload=payload_envelope.payload,
        versioned_hashes=[],
        parent_beacon_block_root=payload_envelope.parent_beacon_block_root,
        execution_requests=payload_envelope.execution_requests,
    )


@with_eip8025_and_later
@spec_state_test
@always_bls
def test_prover_can_request_retrieve_sign_and_store(spec, state):
    store, beacon_block_root = setup_store_with_block(spec, state)
    proof = make_execution_proof(spec, beacon_block_root)
    proof_engine = RecordingProofEngine(proof)
    new_payload_request = make_new_payload_request(spec, store.payloads[beacon_block_root])
    proof_attributes = spec.ProofAttributes(proof_types=[proof.proof_type])

    result = proof_engine.request_proofs(beacon_block_root, new_payload_request, proof_attributes)
    assert result is None
    assert proof_engine.requests == [(beacon_block_root, new_payload_request, proof_attributes)]

    unsigned_proof = proof_engine.get_proof(beacon_block_root, proof.proof_type)
    assert unsigned_proof == proof
    assert proof_engine.retrievals == [(beacon_block_root, proof.proof_type)]

    validator_index = spec.ValidatorIndex(0)
    signature = spec.get_execution_proof_signature(state, proof, privkeys[validator_index])
    signed_proof = spec.SignedExecutionProof(
        message=proof,
        validator_index=validator_index,
        signature=signature,
    )
    spec.validate_execution_proof_gossip(get_seen(spec), store, signed_proof, proof_engine)
    spec.on_execution_proof(store, signed_proof, proof_engine)

    assert proof_engine.verified == [proof, proof]
    assert store.execution_proofs[beacon_block_root][proof.proof_type] == proof


@with_eip8025_and_later
@spec_state_test
def test_default_proof_engine_rejects_prover_operations(spec, state):
    proof_type = spec.ProofType(TEST_PROOF_TYPE)
    beacon_block_root = spec.Root(b"\x11" * 32)
    payload_envelope = spec.ExecutionPayloadEnvelope(beacon_block_root=beacon_block_root)
    new_payload_request = make_new_payload_request(spec, payload_envelope)
    proof_attributes = spec.ProofAttributes(proof_types=[proof_type])

    with pytest.raises(NotImplementedError, match="no default proof generation"):
        spec.PROOF_ENGINE.request_proofs(beacon_block_root, new_payload_request, proof_attributes)

    with pytest.raises(NotImplementedError, match="no default proof retrieval"):
        spec.PROOF_ENGINE.get_proof(beacon_block_root, proof_type)
