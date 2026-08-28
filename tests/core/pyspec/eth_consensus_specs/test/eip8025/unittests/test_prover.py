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
from eth_consensus_specs.test.helpers.proof_engine import MockProofEngine
from eth_consensus_specs.test.helpers.state import state_transition_and_sign_block

TEST_PROOF_TYPE = 1


def setup_store_with_block(spec, state):
    store, _anchor_block = get_genesis_forkchoice_store_and_block(spec, state)
    block = build_empty_block_for_next_slot(spec, state)
    signed_block = state_transition_and_sign_block(spec, state, block)
    block_root = signed_block.message.hash_tree_root()
    store.blocks[block_root] = signed_block.message
    store.block_states[block_root] = state.copy()
    store.payloads[block_root] = spec.ExecutionPayloadEnvelope(beacon_block_root=block_root)
    return store, block_root


def make_new_payload_request(spec, state, payload_envelope):
    bid = state.latest_execution_payload_bid
    return spec.SSZNewPayloadRequest(
        execution_payload=payload_envelope.payload,
        versioned_hashes=spec.VersionedHashes(
            data=[
                spec.kzg_commitment_to_versioned_hash(commitment)
                for commitment in bid.blob_kzg_commitments
            ]
        ),
        parent_beacon_block_root=payload_envelope.parent_beacon_block_root,
        execution_requests=payload_envelope.execution_requests,
    )


@with_eip8025_and_later
@spec_state_test
@always_bls
def test_prover_requests_retrieves_signs_and_stores_execution_proof(spec, state):
    """
    Exercise the prover workflow from proof request through verified storage.
    """
    store, beacon_block_root = setup_store_with_block(spec, state)
    proof_type = spec.ProofType(TEST_PROOF_TYPE)
    proof_data = spec.ProofData(data=[1])
    new_payload_request = make_new_payload_request(
        spec, store.block_states[beacon_block_root], store.payloads[beacon_block_root]
    )
    new_payload_request_root = spec.hash_tree_root(new_payload_request)
    proof = spec.ExecutionProof(
        proof_data=proof_data,
        proof_type=proof_type,
        public_input=spec.PublicInput(
            new_payload_request_root=new_payload_request_root,
            successful_validation=True,
            chain_id=spec.config.DEPOSIT_CHAIN_ID,
            schema_id=spec.STATELESS_INPUT_SCHEMA_ID,
        ),
    )
    proof_engine = MockProofEngine(proof=proof)
    proof_attributes = spec.ProofAttributes(proof_types=[proof_type])
    signed_payload_envelope = spec.SignedExecutionPayloadEnvelope(
        message=store.payloads[beacon_block_root]
    )

    # Construct the payload request internally and submit it to the proof engine.
    request_root = spec.request_execution_proofs(
        store.blocks[beacon_block_root],
        signed_payload_envelope,
        [proof_type],
        proof_engine,
    )
    assert request_root == new_payload_request_root
    assert proof_engine.requests == [
        (
            new_payload_request,
            spec.config.DEPOSIT_CHAIN_ID,
            spec.STATELESS_INPUT_SCHEMA_ID,
            proof_attributes,
        )
    ]

    # Retrieve the generated proof and sign its execution proof envelope.
    validator_index = spec.ValidatorIndex(0)
    signed_proof = spec.get_signed_execution_proof_envelope(
        state,
        beacon_block_root,
        request_root,
        proof_type,
        validator_index,
        privkeys[validator_index],
        proof_engine,
    )
    assert proof_engine.retrievals == [(request_root, proof_type)]
    assert signed_proof.message.proof_data == proof_data
    assert signed_proof.message.proof_type == proof_type
    assert signed_proof.message.beacon_block_root == beacon_block_root

    # Verify during gossip validation and again before storing the envelope.
    spec.validate_execution_proof_gossip(get_seen(spec), store, signed_proof, proof_engine)
    spec.on_execution_proof(store, signed_proof, proof_engine)

    assert proof_engine.verifications == [proof, proof]
    assert store.execution_proofs[beacon_block_root][proof_type] == signed_proof.message


@with_eip8025_and_later
@spec_state_test
def test_default_proof_engine_disables_generation_and_retrieval(spec, state):
    """
    Confirm that the default verifier-only engine does not implement the prover role.
    """
    proof_type = spec.ProofType(TEST_PROOF_TYPE)
    beacon_block_root = spec.Root(b"\x11" * 32)
    payload_envelope = spec.ExecutionPayloadEnvelope(beacon_block_root=beacon_block_root)
    new_payload_request = make_new_payload_request(spec, state, payload_envelope)
    proof_attributes = spec.ProofAttributes(proof_types=[proof_type])

    # Proof generation and retrieval are unavailable without a prover implementation.
    with pytest.raises(NotImplementedError, match="no default proof generation"):
        spec.PROOF_ENGINE.request_proofs(
            new_payload_request,
            spec.config.DEPOSIT_CHAIN_ID,
            spec.STATELESS_INPUT_SCHEMA_ID,
            proof_attributes,
        )

    with pytest.raises(NotImplementedError, match="no default proof retrieval"):
        spec.PROOF_ENGINE.get_proof(spec.hash_tree_root(new_payload_request), proof_type)
