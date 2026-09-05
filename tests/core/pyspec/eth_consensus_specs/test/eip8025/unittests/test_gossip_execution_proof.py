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


class CacheInspectingProofEngine(MockProofEngine):
    def __init__(self, seen, proof_root, prover_key, *, verification_result=True):
        super().__init__(verification_result=verification_result)
        self.seen = seen
        self.proof_root = proof_root
        self.prover_key = prover_key

    def verify_execution_proof(self, proof):
        block_root = self.prover_key[0]
        assert self.proof_root not in self.seen.execution_proof_roots.get(block_root, set())
        assert self.prover_key not in self.seen.execution_proof_provers
        return super().verify_execution_proof(proof)


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
        proof_data=spec.ProofData(data=list(proof_data)),
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
    state = store.block_states[proof_envelope.beacon_block_root]
    payload_envelope = store.payloads[proof_envelope.beacon_block_root]
    bid = state.latest_execution_payload_bid
    new_payload_request = spec.SSZNewPayloadRequest(
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
    public_input = spec.PublicInput(
        new_payload_request_root=spec.hash_tree_root(new_payload_request),
        successful_validation=True,
        chain_id=spec.config.DEPOSIT_CHAIN_ID,
        schema_id=spec.STATELESS_INPUT_SCHEMA_ID,
    )
    return spec.ExecutionProof(
        proof_data=proof_envelope.proof_data,
        proof_type=proof_envelope.proof_type,
        public_input=public_input,
    )


@with_eip8025_and_later
@spec_state_test
def test_gossip_deduplicates_execution_proofs_by_root_and_proof_type(spec, state):
    """
    Accept distinct proofs while ignoring duplicate or already verified proofs.
    """
    store, block_root = setup_store_with_block(spec, state)
    seen = get_seen(spec)
    signed_proof = make_signed_execution_proof_envelope(spec, state, block_root)
    proof_engine = MockProofEngine()

    # Ignore the same proof, including when it is signed by another prover.
    assert validate(spec, seen, store, signed_proof, proof_engine) == ("valid", None)
    assert validate(spec, seen, store, signed_proof, proof_engine) == (
        "ignore",
        "execution proof has already been processed",
    )

    same_proof_from_another_prover = make_signed_execution_proof_envelope(
        spec, state, block_root, prover_index=1
    )
    assert validate(spec, seen, store, same_proof_from_another_prover) == (
        "ignore",
        "execution proof has already been processed",
    )

    competing_proof = make_signed_execution_proof_envelope(
        spec, state, block_root, prover_index=1, proof_data=b"\x02"
    )
    assert validate(spec, seen, store, competing_proof) == ("valid", None)

    # Once a proof is stored, ignore further proofs of the same type for the block.
    spec.on_execution_proof(store, signed_proof, proof_engine)
    later_proof = make_signed_execution_proof_envelope(
        spec, state, block_root, prover_index=2, proof_data=b"\x03"
    )
    assert validate(spec, seen, store, later_proof) == (
        "ignore",
        "verified proof already known for this beacon block and proof type",
    )

    # Proofs of types not yet stored remain eligible for propagation.
    for proof_type in (ALTERNATE_TEST_PROOF_TYPE, THIRD_TEST_PROOF_TYPE):
        alternate = make_signed_execution_proof_envelope(
            spec, state, block_root, proof_type=proof_type
        )
        assert validate(spec, get_seen(spec), store, alternate) == ("valid", None)


@with_eip8025_and_later
@spec_state_test
def test_gossip_handles_missing_execution_proof_block_context(spec, state):
    """
    Apply the correct gossip result when required block context is unavailable.
    """
    store, block_root = setup_store_with_block(spec, state)

    # Ignore proofs for an unknown beacon block until the block arrives.
    unknown_root = spec.Root(b"\xaa" * 32)
    unknown_proof = make_signed_execution_proof_envelope(spec, state, unknown_root)
    assert validate(spec, get_seen(spec), store, unknown_proof) == (
        "ignore",
        "execution proof's beacon block has not been seen",
    )

    # Ignore proofs for a known block until validation and payload processing complete.
    signed_proof = make_signed_execution_proof_envelope(spec, state, block_root)
    block_state = store.block_states.pop(block_root)
    payload = store.payloads.pop(block_root)
    assert validate(spec, get_seen(spec), store, signed_proof) == (
        "ignore",
        "execution proof's payload is unavailable",
    )
    store.block_states[block_root] = block_state
    store.payloads[block_root] = payload

    # Ignore proofs until the execution payload becomes available.
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
def test_gossip_applies_cheap_checks_before_payload_lookup(spec, state):
    """
    Apply message-local and deduplication checks before requiring the payload.
    """
    store, block_root = setup_store_with_block(spec, state)
    signed_proof = make_signed_execution_proof_envelope(spec, state, block_root)
    store.payloads.pop(block_root)

    # Reject message-local structural failures without block or payload context.
    unknown_root = spec.Root(b"\xaa" * 32)
    empty_proof = make_signed_execution_proof_envelope(spec, state, unknown_root, proof_data=b"")
    assert validate(spec, get_seen(spec), store, empty_proof) == (
        "reject",
        "execution proof envelope is invalid",
    )
    unsupported_proof = make_signed_execution_proof_envelope(
        spec, state, unknown_root, proof_type=UNSUPPORTED_LOW_PROOF_TYPE
    )
    assert validate(spec, get_seen(spec), store, unsupported_proof) == (
        "reject",
        "execution proof envelope is invalid",
    )

    # Ignore known duplicates without requiring the payload.
    proof_root = signed_proof.message.hash_tree_root()
    seen = get_seen(spec)
    seen.execution_proof_roots[block_root] = {proof_root}
    assert validate(spec, seen, store, signed_proof) == (
        "ignore",
        "execution proof has already been processed",
    )

    store.execution_proofs[block_root] = {signed_proof.message.proof_type: signed_proof.message}
    seen = get_seen(spec)
    seen.execution_proof_roots[block_root] = {proof_root}
    assert validate(spec, seen, store, signed_proof) == (
        "ignore",
        "verified proof already known for this beacon block and proof type",
    )
    store.execution_proofs.pop(block_root)

    seen = get_seen(spec)
    seen.execution_proof_provers.add(
        (
            block_root,
            signed_proof.message.proof_type,
            signed_proof.validator_index,
        )
    )
    assert validate(spec, seen, store, signed_proof) == (
        "ignore",
        "proof already seen from this prover for this beacon block and proof type",
    )

    # A supported, unseen proof still requires the payload.
    assert validate(spec, get_seen(spec), store, signed_proof) == (
        "ignore",
        "execution proof's payload is unavailable",
    )


@with_eip8025_and_later
@spec_state_test
@always_bls
def test_gossip_rejects_unauthenticated_execution_proofs_without_caching(spec, state):
    """
    Reject authentication failures without preventing a later valid proof.
    """
    store, block_root = setup_store_with_block(spec, state)

    # An out-of-range validator index cannot authenticate an envelope.
    out_of_range = make_signed_execution_proof_envelope(spec, state, block_root)
    out_of_range.validator_index = spec.ValidatorIndex(len(state.validators))
    seen = get_seen(spec)
    assert validate(spec, seen, store, out_of_range) == (
        "reject",
        "execution proof envelope is invalid",
    )
    assert seen.execution_proof_roots == {}
    assert seen.execution_proof_provers == set()

    # A bad signature must not cause the corresponding valid proof to be ignored.
    valid_proof = make_signed_execution_proof_envelope(spec, state, block_root)
    invalid_signature = valid_proof.copy()
    invalid_signature.signature = spec.BLSSignature()
    seen = get_seen(spec)
    assert validate(spec, seen, store, invalid_signature) == (
        "reject",
        "execution proof envelope is invalid",
    )
    assert seen.execution_proof_roots == {}
    assert seen.execution_proof_provers == set()
    assert validate(spec, seen, store, valid_proof) == ("valid", None)

    # An inactive prover must not prevent a later proof from that active validator.
    original_exit_epoch = store.block_states[block_root].validators[1].exit_epoch
    block_state = store.block_states[block_root]
    block_state.validators[1].exit_epoch = spec.get_current_epoch(block_state)
    inactive_proof = make_signed_execution_proof_envelope(
        spec, block_state, block_root, prover_index=1
    )
    seen = get_seen(spec)
    assert validate(spec, seen, store, inactive_proof) == (
        "reject",
        "execution proof envelope is invalid",
    )
    assert seen.execution_proof_roots == {}
    assert seen.execution_proof_provers == set()
    block_state.validators[1].exit_epoch = original_exit_epoch
    active_proof = make_signed_execution_proof_envelope(
        spec, block_state, block_root, prover_index=1
    )
    assert validate(spec, seen, store, active_proof) == ("valid", None)


@with_eip8025_and_later
@spec_state_test
def test_gossip_rejects_malformed_execution_proof_fields_without_caching(spec, state):
    """
    Reject invalid proof data and proof types without updating the seen cache.
    """
    store, block_root = setup_store_with_block(spec, state)

    # Exercise empty proof data and proof types outside the supported set.
    cases = [
        make_signed_execution_proof_envelope(spec, state, block_root, proof_data=b""),
        make_signed_execution_proof_envelope(
            spec, state, block_root, proof_type=UNSUPPORTED_LOW_PROOF_TYPE
        ),
        make_signed_execution_proof_envelope(
            spec,
            state,
            block_root,
            prover_index=1,
            proof_type=UNSUPPORTED_HIGH_PROOF_TYPE,
        ),
    ]

    for signed_proof in cases:
        seen = get_seen(spec)
        assert validate(spec, seen, store, signed_proof) == (
            "reject",
            "execution proof envelope is invalid",
        )
        assert seen.execution_proof_roots == {}
        assert seen.execution_proof_provers == set()


@with_eip8025_and_later
@spec_state_test
@always_bls
def test_verify_and_construct_execution_proof_from_envelope(spec, state):
    """
    Authenticate an envelope and derive the proof-engine input from block context.
    """
    store, block_root = setup_store_with_block(spec, state)
    signed_proof = make_signed_execution_proof_envelope(spec, state, block_root)
    block_state = store.block_states[block_root]
    payload_envelope = store.payloads[block_root]

    # Verify the execution proof envelope fields and the prover signature.
    spec.verify_execution_proof_envelope(
        block_state,
        signed_proof,
    )
    # Construct the same execution proof expected by the proof engine.
    assert spec.get_execution_proof(
        block_state,
        signed_proof.message,
        payload_envelope,
    ) == get_proof_engine_input(spec, store, signed_proof)


@with_eip8025_and_later
@spec_state_test
def test_gossip_verifies_execution_proof_before_handler_stores_it(spec, state):
    """
    Verify before propagation, then verify again and store in the handler.
    """
    store, block_root = setup_store_with_block(spec, state)
    signed_proof = make_signed_execution_proof_envelope(spec, state, block_root)
    seen = get_seen(spec)
    proof_root = spec.hash_tree_root(signed_proof.message)
    prover_key = (block_root, signed_proof.message.proof_type, signed_proof.validator_index)
    proof_engine = CacheInspectingProofEngine(seen, proof_root, prover_key)
    proof = get_proof_engine_input(spec, store, signed_proof)

    # Gossip validation verifies the proof without mutating the fork-choice store.
    assert validate(spec, seen, store, signed_proof, proof_engine) == ("valid", None)
    assert proof_engine.verifications == [proof]
    assert proof_root in seen.execution_proof_roots[block_root]
    assert prover_key in seen.execution_proof_provers
    assert block_root not in store.execution_proofs

    # The handler verifies again before storing and rejects duplicate storage.
    handler_engine = MockProofEngine()
    spec.on_execution_proof(store, signed_proof, handler_engine)
    assert handler_engine.verifications == [proof]
    assert store.execution_proofs[block_root] == {
        signed_proof.message.proof_type: signed_proof.message
    }
    expect_assertion_error(lambda: spec.on_execution_proof(store, signed_proof, handler_engine))

    # Cache a failed gossip verification so the same proof and prover are ignored.
    alternate_proof = make_signed_execution_proof_envelope(
        spec, state, block_root, proof_type=ALTERNATE_TEST_PROOF_TYPE
    )
    seen = get_seen(spec)
    alternate_proof_root = spec.hash_tree_root(alternate_proof.message)
    alternate_prover_key = (
        block_root,
        alternate_proof.message.proof_type,
        alternate_proof.validator_index,
    )
    rejecting_engine = CacheInspectingProofEngine(
        seen,
        alternate_proof_root,
        alternate_prover_key,
        verification_result=False,
    )
    assert validate(spec, seen, store, alternate_proof, rejecting_engine) == (
        "reject",
        "execution proof is invalid",
    )
    expected_alternate_proof = get_proof_engine_input(spec, store, alternate_proof)
    assert rejecting_engine.verifications == [expected_alternate_proof]
    assert alternate_proof_root in seen.execution_proof_roots[block_root]
    assert alternate_prover_key in seen.execution_proof_provers
    assert alternate_proof.message.proof_type not in store.execution_proofs[block_root]
    assert validate(spec, seen, store, alternate_proof) == (
        "ignore",
        "execution proof has already been processed",
    )

    alternate_attempt = make_signed_execution_proof_envelope(
        spec, state, block_root, proof_type=ALTERNATE_TEST_PROOF_TYPE, proof_data=b"\x04"
    )
    assert validate(spec, seen, store, alternate_attempt) == (
        "ignore",
        "proof already seen from this prover for this beacon block and proof type",
    )

    # A fresh local cache may accept the proof, and the store tracks each proof type.
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
def test_on_execution_proof_requires_block_context_and_valid_proof(spec, state):
    """
    Store a proof only when its block context exists and verification succeeds.
    """
    store, block_root = setup_store_with_block(spec, state)
    signed_proof = make_signed_execution_proof_envelope(spec, state, block_root)

    # The handler requires the block, its post-state, and its execution payload.
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

    # A failed proof-engine verification must not update the store.
    rejecting_engine = MockProofEngine(verification_result=False)
    expect_assertion_error(lambda: spec.on_execution_proof(store, signed_proof, rejecting_engine))
    proof = get_proof_engine_input(spec, store, signed_proof)
    assert rejecting_engine.verifications == [proof]
    assert block_root not in store.execution_proofs

    # A valid proof with complete context is verified and stored.
    spec.on_execution_proof(store, signed_proof, proof_engine)
    assert proof_engine.verifications == [proof]
