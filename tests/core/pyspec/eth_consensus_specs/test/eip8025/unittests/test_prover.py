from types import SimpleNamespace

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
from eth_consensus_specs.test.helpers.keys import privkeys
from eth_consensus_specs.test.helpers.state import state_transition_and_sign_block

TEST_PROOF_TYPE = 1


class RecordingProofEngine:
    def __init__(self, proof=None):
        self.proof = proof
        self.requests = []
        self.retrievals = []
        self.verified = []

    def verify_execution_proof(self, proof, chain_config_root):
        self.verified.append((proof, chain_config_root))
        return True

    def request_proof(self, private_input, proof_type):
        self.requests.append((private_input, proof_type))
        return private_input.beacon_chain_witness.signed_envelope.message.beacon_block_root

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
    return store, signed_block, block_root


def make_execution_proof(
    spec,
    signed_block,
    block_root,
    *,
    proof_type=TEST_PROOF_TYPE,
    head_root=None,
    head_slot=None,
):
    if head_root is None:
        head_root = block_root
    if head_slot is None:
        head_slot = signed_block.message.slot
    checkpoint = spec.ExecutionCheckpoint(
        slot=head_slot,
        beacon_block_root=head_root,
    )
    return spec.ExecutionProof(
        proof_data=spec.ProgressiveByteList(b"\x01"),
        proof_type=spec.ProofType(proof_type),
        claim=spec.ExecutionProofClaim(origin=checkpoint, head=checkpoint),
    )


def make_private_input(spec, block_root):
    signed_envelope = spec.SignedExecutionPayloadEnvelope(
        message=spec.ExecutionPayloadEnvelope(beacon_block_root=block_root)
    )
    beacon_chain_witness = SimpleNamespace(signed_envelope=signed_envelope)
    return spec.PrivateInput(
        beacon_chain_witness=beacon_chain_witness,
        execution_witness=None,
        chain_config=None,
        public_keys=[],
    )


@with_eip8025_and_later(features=("prover",))
@spec_state_test
@always_bls
def test_prover_can_request_retrieve_sign_and_store(spec, state, eip8025_features):
    assert eip8025_features == frozenset({"prover"})
    store, signed_block, block_root = setup_store_with_block(spec, state)
    proof = make_execution_proof(spec, signed_block, block_root)
    proof_engine = RecordingProofEngine(proof)
    private_input = make_private_input(spec, block_root)

    requested_root = proof_engine.request_proof(private_input, proof.proof_type)
    assert requested_root == block_root
    assert proof_engine.requests == [(private_input, proof.proof_type)]

    unsigned_proof = proof_engine.get_proof(requested_root, proof.proof_type)
    assert unsigned_proof == proof
    assert proof_engine.retrievals == [(block_root, proof.proof_type)]

    validator_index = spec.ValidatorIndex(0)
    signature = spec.get_execution_proof_signature(state, proof, privkeys[validator_index])
    signed_proof = spec.SignedExecutionProof(
        message=proof,
        validator_index=validator_index,
        signature=signature,
    )
    spec.on_execution_proof(store, signed_proof, proof_engine)

    assert proof_engine.verified == [(proof, spec.CHAIN_CONFIG_ROOT)]
    assert store.execution_proofs[block_root][proof.proof_type] == proof


@with_eip8025_and_later(features=("prover",))
@spec_state_test
def test_default_proof_engine_rejects_prover_operations(spec, state, eip8025_features):
    assert eip8025_features == frozenset({"prover"})
    proof_type = spec.ProofType(TEST_PROOF_TYPE)

    with pytest.raises(NotImplementedError, match="no default proof generation"):
        spec.PROOF_ENGINE.request_proof(None, proof_type)

    with pytest.raises(NotImplementedError, match="no default proof retrieval"):
        spec.PROOF_ENGINE.get_proof(spec.Root(), proof_type)
