from eth_consensus_specs.test.context import (
    always_bls,
    expect_assertion_error,
    spec_state_test,
    with_eip8025_and_later,
)
from eth_consensus_specs.test.helpers.block import build_empty_block_for_next_slot
from eth_consensus_specs.test.helpers.fork_choice import (
    get_genesis_forkchoice_store_and_block,
)
from eth_consensus_specs.test.helpers.gossip import get_seen, run_validate_gossip
from eth_consensus_specs.test.helpers.keys import privkeys
from eth_consensus_specs.test.helpers.proof_engine import MockProofEngine
from eth_consensus_specs.test.helpers.state import state_transition_and_sign_block

TEST_PROOF_TYPE = 1
ALTERNATE_TEST_PROOF_TYPE = 2
THIRD_TEST_PROOF_TYPE = 3
UNSUPPORTED_LOW_PROOF_TYPE = 0
UNSUPPORTED_HIGH_PROOF_TYPE = 4


def setup_store_with_block(spec, state):
    """Build one accepted block and return its fork-choice store and root."""
    store, _anchor_block = get_genesis_forkchoice_store_and_block(spec, state)
    block = build_empty_block_for_next_slot(spec, state)
    signed_block = state_transition_and_sign_block(spec, state, block)
    block_root = signed_block.message.hash_tree_root()
    store.blocks[block_root] = signed_block.message
    store.block_states[block_root] = state.copy()
    store.payloads[block_root] = spec.ExecutionPayloadEnvelope(beacon_block_root=block_root)

    return store, block_root


def make_signed_execution_proof_envelope(
    spec,
    state,
    beacon_block_root,
    *,
    prover_index=0,
    proof_data=b"\x01",
    proof_type=TEST_PROOF_TYPE,
):
    proof_envelope = spec.ExecutionProofEnvelope(
        proof_data=spec.ProofData(proof_data),
        proof_type=spec.ProofType(proof_type),
        beacon_block_root=beacon_block_root,
    )
    signature = spec.get_execution_proof_envelope_signature(
        state, proof_envelope, privkeys[prover_index]
    )
    return spec.SignedExecutionProofEnvelope(
        message=proof_envelope,
        validator_index=spec.ValidatorIndex(prover_index),
        signature=signature,
    )


def validate(spec, seen, store, signed_proof, proof_engine=None):
    if proof_engine is None:
        proof_engine = MockProofEngine()
    return run_validate_gossip(
        spec,
        seen=seen,
        store=store,
        signed_proof_envelope=signed_proof,
        proof_engine=proof_engine,
    )


def get_proof_engine_input(spec, store, signed_proof):
    proof_envelope = signed_proof.message
    public_input = spec.compute_execution_proof_public_input(
        store, proof_envelope.beacon_block_root
    )
    return spec.ExecutionProof(
        proof_data=proof_envelope.proof_data,
        proof_type=proof_envelope.proof_type,
        public_input=public_input,
    )


@with_eip8025_and_later
@spec_state_test
def test_validate_execution_proof_gossip_duplicates_and_verified_store(spec, state):
    store, block_root = setup_store_with_block(spec, state)
    seen = get_seen(spec)
    signed_proof = make_signed_execution_proof_envelope(spec, state, block_root)
    proof_engine = MockProofEngine()

    assert validate(spec, seen, store, signed_proof, proof_engine) == ("valid", None)
    assert validate(spec, seen, store, signed_proof, proof_engine) == (
        "ignore",
        "proof already seen from this prover for this beacon block and proof type",
    )

    competing_proof = make_signed_execution_proof_envelope(
        spec, state, block_root, prover_index=1, proof_data=b"\x02"
    )
    assert validate(spec, seen, store, competing_proof) == ("valid", None)

    spec.on_execution_proof(store, signed_proof, proof_engine)
    later_proof = make_signed_execution_proof_envelope(
        spec, state, block_root, prover_index=2, proof_data=b"\x03"
    )
    assert validate(spec, seen, store, later_proof) == (
        "ignore",
        "verified proof already known for this beacon block and proof type",
    )

    for proof_type in (ALTERNATE_TEST_PROOF_TYPE, THIRD_TEST_PROOF_TYPE):
        alternate = make_signed_execution_proof_envelope(
            spec, state, block_root, proof_type=proof_type
        )
        assert validate(spec, get_seen(spec), store, alternate) == ("valid", None)


@with_eip8025_and_later
@spec_state_test
def test_validate_execution_proof_gossip_block_context(spec, state):
    store, block_root = setup_store_with_block(spec, state)
    unknown_root = spec.Root(b"\xaa" * 32)
    unknown_proof = make_signed_execution_proof_envelope(spec, state, unknown_root)
    assert validate(spec, get_seen(spec), store, unknown_proof) == (
        "ignore",
        "execution proof's beacon block has not been seen",
    )

    signed_proof = make_signed_execution_proof_envelope(spec, state, block_root)
    block = store.blocks.pop(block_root)
    assert validate(spec, get_seen(spec), store, signed_proof) == (
        "ignore",
        "execution proof's beacon block has not been seen",
    )
    store.blocks[block_root] = block

    block_state = store.block_states.pop(block_root)
    assert validate(spec, get_seen(spec), store, signed_proof) == (
        "reject",
        "execution proof's beacon block failed validation",
    )
    store.block_states[block_root] = block_state

    payload = store.payloads.pop(block_root)
    proof_engine = MockProofEngine()
    assert validate(spec, get_seen(spec), store, signed_proof, proof_engine) == (
        "ignore",
        "execution proof's payload is unavailable",
    )
    assert proof_engine.verifications == []
    store.payloads[block_root] = payload


@with_eip8025_and_later
@spec_state_test
@always_bls
def test_validate_execution_proof_gossip_authentication_does_not_poison_cache(spec, state):
    store, block_root = setup_store_with_block(spec, state)

    out_of_range = make_signed_execution_proof_envelope(spec, state, block_root)
    out_of_range.validator_index = spec.ValidatorIndex(len(state.validators))
    seen = get_seen(spec)
    assert validate(spec, seen, store, out_of_range) == (
        "reject",
        "execution proof's validator index is invalid",
    )
    assert seen.execution_proofs == set()

    valid_proof = make_signed_execution_proof_envelope(spec, state, block_root)
    invalid_signature = valid_proof.copy()
    invalid_signature.signature = spec.BLSSignature()
    seen = get_seen(spec)
    assert validate(spec, seen, store, invalid_signature) == (
        "reject",
        "execution proof's signature is invalid",
    )
    assert validate(spec, seen, store, valid_proof) == ("valid", None)

    original_exit_epoch = store.block_states[block_root].validators[1].exit_epoch
    block_state = store.block_states[block_root]
    block_state.validators[1].exit_epoch = spec.get_current_epoch(block_state)
    inactive_proof = make_signed_execution_proof_envelope(
        spec, block_state, block_root, prover_index=1
    )
    seen = get_seen(spec)
    assert validate(spec, seen, store, inactive_proof) == (
        "reject",
        "execution proof's validator is not active",
    )
    block_state.validators[1].exit_epoch = original_exit_epoch
    active_proof = make_signed_execution_proof_envelope(
        spec, block_state, block_root, prover_index=1
    )
    assert validate(spec, seen, store, active_proof) == ("valid", None)


@with_eip8025_and_later
@spec_state_test
def test_validate_execution_proof_gossip_structural_checks(spec, state):
    store, block_root = setup_store_with_block(spec, state)
    cases = [
        (
            make_signed_execution_proof_envelope(spec, state, block_root, proof_data=b""),
            "execution proof data is empty",
        ),
        (
            make_signed_execution_proof_envelope(
                spec, state, block_root, proof_type=UNSUPPORTED_LOW_PROOF_TYPE
            ),
            "execution proof type is unsupported",
        ),
        (
            make_signed_execution_proof_envelope(
                spec,
                state,
                block_root,
                prover_index=1,
                proof_type=UNSUPPORTED_HIGH_PROOF_TYPE,
            ),
            "execution proof type is unsupported",
        ),
        (
            make_signed_execution_proof_envelope(
                spec,
                state,
                block_root,
                prover_index=2,
                proof_data=b"\x01" * (int(spec.MAX_PROOF_SIZE) + 1),
            ),
            "execution proof data exceeds the size limit",
        ),
    ]

    for signed_proof, error in cases:
        assert validate(spec, get_seen(spec), store, signed_proof) == ("reject", error)


@with_eip8025_and_later
@spec_state_test
def test_gossip_verifies_before_handler_stores(spec, state):
    store, block_root = setup_store_with_block(spec, state)
    signed_proof = make_signed_execution_proof_envelope(spec, state, block_root)
    proof_engine = MockProofEngine()
    proof = get_proof_engine_input(spec, store, signed_proof)

    assert validate(spec, get_seen(spec), store, signed_proof, proof_engine) == ("valid", None)
    assert proof_engine.verifications == [proof]
    assert block_root not in store.execution_proofs

    spec.on_execution_proof(store, signed_proof, proof_engine)
    assert proof_engine.verifications == [proof, proof]
    assert store.execution_proofs[block_root] == {
        signed_proof.message.proof_type: signed_proof.message
    }
    expect_assertion_error(lambda: spec.on_execution_proof(store, signed_proof, proof_engine))

    alternate_proof = make_signed_execution_proof_envelope(
        spec, state, block_root, proof_type=ALTERNATE_TEST_PROOF_TYPE
    )
    rejecting_engine = MockProofEngine(verification_result=False)
    seen = get_seen(spec)
    assert validate(spec, seen, store, alternate_proof, rejecting_engine) == (
        "reject",
        "execution proof is invalid",
    )
    expected_alternate_proof = get_proof_engine_input(spec, store, alternate_proof)
    assert rejecting_engine.verifications == [expected_alternate_proof]
    assert alternate_proof.message.proof_type not in store.execution_proofs[block_root]
    assert validate(spec, seen, store, alternate_proof) == (
        "ignore",
        "proof already seen from this prover for this beacon block and proof type",
    )

    assert validate(spec, get_seen(spec), store, alternate_proof) == ("valid", None)
    accepting_engine = MockProofEngine()
    spec.on_execution_proof(store, alternate_proof, accepting_engine)
    third_proof = make_signed_execution_proof_envelope(
        spec, state, block_root, proof_type=THIRD_TEST_PROOF_TYPE
    )
    assert validate(spec, get_seen(spec), store, third_proof) == ("valid", None)
    spec.on_execution_proof(store, third_proof, MockProofEngine())

    assert store.execution_proofs[block_root] == {
        signed_proof.message.proof_type: signed_proof.message,
        alternate_proof.message.proof_type: alternate_proof.message,
        third_proof.message.proof_type: third_proof.message,
    }


@with_eip8025_and_later
@spec_state_test
@always_bls
def test_on_execution_proof_enforces_storage_context(spec, state):
    store, block_root = setup_store_with_block(spec, state)
    signed_proof = make_signed_execution_proof_envelope(spec, state, block_root)

    block = store.blocks.pop(block_root)
    proof_engine = MockProofEngine()
    expect_assertion_error(lambda: spec.on_execution_proof(store, signed_proof, proof_engine))
    store.blocks[block_root] = block

    block_state = store.block_states.pop(block_root)
    expect_assertion_error(lambda: spec.on_execution_proof(store, signed_proof, proof_engine))
    store.block_states[block_root] = block_state

    payload = store.payloads.pop(block_root)
    expect_assertion_error(lambda: spec.on_execution_proof(store, signed_proof, proof_engine))
    store.payloads[block_root] = payload

    rejecting_engine = MockProofEngine(verification_result=False)
    expect_assertion_error(lambda: spec.on_execution_proof(store, signed_proof, rejecting_engine))
    proof = get_proof_engine_input(spec, store, signed_proof)
    assert rejecting_engine.verifications == [proof]
    assert block_root not in store.execution_proofs

    spec.on_execution_proof(store, signed_proof, proof_engine)
    assert proof_engine.verifications == [proof]
