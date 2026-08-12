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
from eth_consensus_specs.test.helpers.state import state_transition_and_sign_block

TEST_PROOF_TYPE = 1
ALTERNATE_TEST_PROOF_TYPE = 2
UNSUPPORTED_TEST_PROOF_TYPE = 3


class DummyProofEngine:
    def __init__(self, accept=True):
        self.accept = accept
        self.proofs = []

    def verify_execution_proof(self, proof, chain_config_root):
        self.proofs.append((proof, chain_config_root))
        return self.accept


def setup_store_with_block(spec, state):
    """Build and import one block without requiring its payload envelope."""
    store, _anchor_block = get_genesis_forkchoice_store_and_block(spec, state)
    block = build_empty_block_for_next_slot(spec, state)
    signed_block = state_transition_and_sign_block(spec, state, block)
    block_root = signed_block.message.hash_tree_root()
    store.blocks[block_root] = signed_block.message
    store.block_states[block_root] = state.copy()
    return store, signed_block, block_root


def make_signed_execution_proof(
    spec,
    state,
    checkpoint,
    *,
    prover_index=0,
    proof_data=b"\x01",
    proof_type=TEST_PROOF_TYPE,
    origin=None,
    head=None,
):
    if origin is None:
        origin = checkpoint
    if head is None:
        head = checkpoint
    proof = spec.ExecutionProof(
        proof_data=spec.ProgressiveByteList(proof_data),
        proof_type=spec.ProofType(proof_type),
        claim=spec.ExecutionProofClaim(origin=origin, head=head),
    )
    signature = spec.get_execution_proof_signature(state, proof, privkeys[prover_index])
    return spec.SignedExecutionProof(
        message=proof,
        validator_index=spec.ValidatorIndex(prover_index),
        signature=signature,
    )


def validate(spec, seen, store, state, signed_proof, checkpoint, supported_proof_types=None):
    if supported_proof_types is None:
        supported_proof_types = {
            spec.ProofType(TEST_PROOF_TYPE),
            spec.ProofType(ALTERNATE_TEST_PROOF_TYPE),
        }
    return run_validate_gossip(
        spec,
        seen=seen,
        store=store,
        state=state,
        signed_execution_proof=signed_proof,
        execution_checkpoint=checkpoint,
        supported_proof_types=supported_proof_types,
    )


def get_checkpoint(spec, signed_block, block_root):
    return spec.ExecutionCheckpoint(
        slot=signed_block.message.slot,
        beacon_block_root=block_root,
    )


def assert_handler_rejects(spec, store, signed_proof, checkpoint, proof_engine):
    proof = signed_proof.message
    head_root = proof.claim.head.beacon_block_root
    expect_assertion_error(
        lambda: spec.on_execution_proof(
            store,
            signed_proof,
            checkpoint,
            proof_engine,
        )
    )
    assert proof.proof_type not in store.execution_proofs.get(head_root, {})


@with_eip8025_and_later
@spec_state_test
def test_validate_execution_proof_gossip_duplicates_and_verified_store(spec, state):
    store, signed_block, block_root = setup_store_with_block(spec, state)
    checkpoint = get_checkpoint(spec, signed_block, block_root)
    seen = get_seen(spec)
    signed_proof = make_signed_execution_proof(spec, state, checkpoint)

    assert store.payloads == {}
    assert validate(spec, seen, store, state, signed_proof, checkpoint) == (
        "valid",
        None,
    )
    assert validate(spec, seen, store, state, signed_proof, checkpoint) == (
        "ignore",
        "proof already seen from this prover for this head and proof type",
    )

    competing_proof = make_signed_execution_proof(
        spec,
        state,
        checkpoint,
        prover_index=1,
        proof_data=b"\x02",
    )
    assert validate(spec, seen, store, state, competing_proof, checkpoint) == (
        "valid",
        None,
    )

    spec.on_execution_proof(
        store,
        signed_proof,
        checkpoint,
        DummyProofEngine(),
    )
    later_proof = make_signed_execution_proof(
        spec,
        state,
        checkpoint,
        prover_index=2,
        proof_data=b"\x03",
    )
    assert validate(spec, seen, store, state, later_proof, checkpoint) == (
        "ignore",
        "verified proof already known for this head and proof type",
    )

    alternate_type = make_signed_execution_proof(
        spec,
        state,
        checkpoint,
        proof_type=ALTERNATE_TEST_PROOF_TYPE,
    )
    assert validate(spec, seen, store, state, alternate_type, checkpoint) == (
        "valid",
        None,
    )


@with_eip8025_and_later
@spec_state_test
def test_validate_execution_proof_gossip_unknown_and_failed_block(spec, state):
    store, signed_block, block_root = setup_store_with_block(spec, state)
    checkpoint = get_checkpoint(spec, signed_block, block_root)
    unknown_head = spec.ExecutionCheckpoint(
        slot=checkpoint.slot,
        beacon_block_root=spec.Root(b"\xaa" * 32),
    )
    unknown_proof = make_signed_execution_proof(spec, state, checkpoint, head=unknown_head)

    assert validate(spec, get_seen(spec), store, state, unknown_proof, checkpoint) == (
        "ignore",
        "execution proof's head block has not been seen",
    )

    signed_proof = make_signed_execution_proof(spec, state, checkpoint)
    del store.block_states[block_root]
    assert validate(spec, get_seen(spec), store, state, signed_proof, checkpoint) == (
        "reject",
        "execution proof's head block failed validation",
    )


@with_eip8025_and_later
@spec_state_test
@always_bls
def test_validate_execution_proof_gossip_authentication_does_not_poison_cache(spec, state):
    store, signed_block, block_root = setup_store_with_block(spec, state)
    checkpoint = get_checkpoint(spec, signed_block, block_root)

    out_of_range = make_signed_execution_proof(spec, state, checkpoint)
    out_of_range.validator_index = spec.ValidatorIndex(len(state.validators))
    seen = get_seen(spec)
    assert validate(spec, seen, store, state, out_of_range, checkpoint) == (
        "reject",
        "execution proof's validator index is invalid",
    )
    assert seen.execution_proof_provers == set()

    valid_proof = make_signed_execution_proof(spec, state, checkpoint)
    invalid_signature = valid_proof.copy()
    invalid_signature.signature = spec.BLSSignature()
    seen = get_seen(spec)
    assert validate(spec, seen, store, state, invalid_signature, checkpoint) == (
        "reject",
        "execution proof's signature is invalid",
    )
    assert validate(spec, seen, store, state, valid_proof, checkpoint) == (
        "valid",
        None,
    )

    original_exit_epoch = state.validators[1].exit_epoch
    state.validators[1].exit_epoch = spec.get_current_epoch(state)
    inactive_proof = make_signed_execution_proof(spec, state, checkpoint, prover_index=1)
    seen = get_seen(spec)
    assert validate(spec, seen, store, state, inactive_proof, checkpoint) == (
        "reject",
        "execution proof's validator is not active",
    )
    state.validators[1].exit_epoch = original_exit_epoch
    active_proof = make_signed_execution_proof(spec, state, checkpoint, prover_index=1)
    assert validate(spec, seen, store, state, active_proof, checkpoint) == (
        "valid",
        None,
    )


@with_eip8025_and_later
@spec_state_test
def test_validate_execution_proof_gossip_checks_validator_index_before_duplicate(spec, state):
    store, signed_block, block_root = setup_store_with_block(spec, state)
    checkpoint = get_checkpoint(spec, signed_block, block_root)
    signed_proof = make_signed_execution_proof(spec, state, checkpoint)
    invalid_index = spec.ValidatorIndex(len(state.validators))
    signed_proof.validator_index = invalid_index

    seen = get_seen(spec)
    seen.execution_proof_provers.add((block_root, signed_proof.message.proof_type, invalid_index))
    assert validate(spec, seen, store, state, signed_proof, checkpoint) == (
        "reject",
        "execution proof's validator index is invalid",
    )


@with_eip8025_and_later
@spec_state_test
def test_validate_execution_proof_gossip_rejected_attempt_is_not_consumed(spec, state):
    store, signed_block, block_root = setup_store_with_block(spec, state)
    checkpoint = get_checkpoint(spec, signed_block, block_root)
    seen = get_seen(spec)
    empty_proof = make_signed_execution_proof(spec, state, checkpoint, proof_data=b"")

    assert validate(spec, seen, store, state, empty_proof, checkpoint) == (
        "reject",
        "execution proof data is empty",
    )

    retry = make_signed_execution_proof(spec, state, checkpoint, proof_data=b"\x02")
    assert validate(spec, seen, store, state, retry, checkpoint) == (
        "valid",
        None,
    )


@with_eip8025_and_later
@spec_state_test
def test_validate_execution_proof_gossip_structural_checks(spec, state):
    store, signed_block, block_root = setup_store_with_block(spec, state)
    checkpoint = get_checkpoint(spec, signed_block, block_root)
    wrong_origin = spec.ExecutionCheckpoint(
        slot=checkpoint.slot,
        beacon_block_root=spec.Root(b"\xaa" * 32),
    )
    wrong_head = spec.ExecutionCheckpoint(
        slot=spec.Slot(checkpoint.slot + 1),
        beacon_block_root=checkpoint.beacon_block_root,
    )
    cases = [
        (
            make_signed_execution_proof(spec, state, checkpoint, origin=wrong_origin),
            "execution proof's origin is not the execution checkpoint",
        ),
        (
            make_signed_execution_proof(spec, state, checkpoint, prover_index=1, head=wrong_head),
            "execution proof's head does not identify the accepted block",
        ),
        (
            make_signed_execution_proof(
                spec,
                state,
                checkpoint,
                prover_index=2,
                proof_type=UNSUPPORTED_TEST_PROOF_TYPE,
            ),
            "execution proof type is unsupported",
        ),
        (
            make_signed_execution_proof(
                spec,
                state,
                checkpoint,
                prover_index=3,
                proof_data=b"\x01" * (int(spec.MAX_PROOF_SIZE) + 1),
            ),
            "execution proof data exceeds the size limit",
        ),
    ]

    for signed_proof, error in cases:
        assert validate(spec, get_seen(spec), store, state, signed_proof, checkpoint) == (
            "reject",
            error,
        )


@with_eip8025_and_later
@spec_state_test
def test_on_execution_proof_verifies_then_stores(spec, state):
    store, signed_block, block_root = setup_store_with_block(spec, state)
    checkpoint = get_checkpoint(spec, signed_block, block_root)
    signed_proof = make_signed_execution_proof(spec, state, checkpoint)
    proof_engine = DummyProofEngine()

    spec.on_execution_proof(
        store,
        signed_proof,
        checkpoint,
        proof_engine,
    )

    assert proof_engine.proofs == [(signed_proof.message, spec.CHAIN_CONFIG_ROOT)]
    assert store.execution_proofs[block_root] == {
        signed_proof.message.proof_type: signed_proof.message
    }
    expect_assertion_error(
        lambda: spec.on_execution_proof(
            store,
            signed_proof,
            checkpoint,
            proof_engine,
        )
    )

    alternate_proof = make_signed_execution_proof(
        spec,
        state,
        checkpoint,
        proof_type=ALTERNATE_TEST_PROOF_TYPE,
    )
    rejecting_engine = DummyProofEngine(accept=False)
    assert_handler_rejects(
        spec,
        store,
        alternate_proof,
        checkpoint,
        rejecting_engine,
    )
    assert rejecting_engine.proofs == [(alternate_proof.message, spec.CHAIN_CONFIG_ROOT)]

    spec.on_execution_proof(
        store,
        alternate_proof,
        checkpoint,
        DummyProofEngine(),
    )
    assert store.execution_proofs[block_root] == {
        signed_proof.message.proof_type: signed_proof.message,
        alternate_proof.message.proof_type: alternate_proof.message,
    }


@with_eip8025_and_later
@spec_state_test
@always_bls
def test_on_execution_proof_enforces_context_and_intrinsic_invariants(spec, state):
    store, signed_block, block_root = setup_store_with_block(spec, state)
    checkpoint = get_checkpoint(spec, signed_block, block_root)
    proof_engine = DummyProofEngine()

    signed_proof = make_signed_execution_proof(spec, state, checkpoint)
    block = store.blocks.pop(block_root)
    assert_handler_rejects(spec, store, signed_proof, checkpoint, proof_engine)
    store.blocks[block_root] = block

    head_state = store.block_states.pop(block_root)
    assert_handler_rejects(spec, store, signed_proof, checkpoint, proof_engine)
    store.block_states[block_root] = head_state

    empty_proof = make_signed_execution_proof(spec, state, checkpoint, proof_data=b"")
    assert_handler_rejects(spec, store, empty_proof, checkpoint, proof_engine)

    oversized_proof = make_signed_execution_proof(
        spec,
        state,
        checkpoint,
        prover_index=1,
        proof_data=b"\x01" * (int(spec.MAX_PROOF_SIZE) + 1),
    )
    assert_handler_rejects(spec, store, oversized_proof, checkpoint, proof_engine)

    invalid_signature = make_signed_execution_proof(spec, state, checkpoint, prover_index=3)
    invalid_signature.signature = spec.BLSSignature()
    assert_handler_rejects(spec, store, invalid_signature, checkpoint, proof_engine)

    original_exit_epoch = head_state.validators[4].exit_epoch
    head_state.validators[4].exit_epoch = spec.get_current_epoch(head_state)
    inactive_proof = make_signed_execution_proof(spec, head_state, checkpoint, prover_index=4)
    assert_handler_rejects(spec, store, inactive_proof, checkpoint, proof_engine)
    head_state.validators[4].exit_epoch = original_exit_epoch

    out_of_range = make_signed_execution_proof(spec, state, checkpoint, prover_index=5)
    out_of_range.validator_index = spec.ValidatorIndex(len(head_state.validators))
    assert_handler_rejects(spec, store, out_of_range, checkpoint, proof_engine)

    wrong_origin = spec.ExecutionCheckpoint(
        slot=checkpoint.slot,
        beacon_block_root=spec.Root(b"\xbb" * 32),
    )
    contextual_mismatch = make_signed_execution_proof(
        spec,
        state,
        checkpoint,
        prover_index=6,
        origin=wrong_origin,
    )
    assert_handler_rejects(spec, store, contextual_mismatch, checkpoint, proof_engine)

    wrong_head = spec.ExecutionCheckpoint(
        slot=spec.Slot(checkpoint.slot + 1),
        beacon_block_root=checkpoint.beacon_block_root,
    )
    contextual_mismatch = make_signed_execution_proof(
        spec,
        state,
        checkpoint,
        prover_index=7,
        head=wrong_head,
    )
    assert_handler_rejects(spec, store, contextual_mismatch, checkpoint, proof_engine)

    assert proof_engine.proofs == []
