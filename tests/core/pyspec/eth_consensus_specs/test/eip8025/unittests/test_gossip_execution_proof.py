from eth_consensus_specs.test.context import (
    spec_state_test,
    with_eip8025_and_later,
)
from eth_consensus_specs.test.helpers.block import build_empty_block_for_next_slot
from eth_consensus_specs.test.helpers.execution_payload import (
    build_signed_execution_payload_envelope,
)
from eth_consensus_specs.test.helpers.fork_choice import (
    get_genesis_forkchoice_store_and_block,
)
from eth_consensus_specs.test.helpers.gossip import get_seen, run_validate_gossip
from eth_consensus_specs.test.helpers.keys import privkeys
from eth_consensus_specs.test.helpers.state import state_transition_and_sign_block


def setup_store_with_payload(spec, state):
    """Build and import one block and its accepted execution payload envelope."""
    store, _anchor_block = get_genesis_forkchoice_store_and_block(spec, state)
    block = build_empty_block_for_next_slot(spec, state)
    signed_block = state_transition_and_sign_block(spec, state, block)
    block_root = signed_block.message.hash_tree_root()
    store.blocks[block_root] = signed_block.message
    store.block_states[block_root] = state.copy()

    signed_envelope = build_signed_execution_payload_envelope(spec, state, block_root, signed_block)
    store.payloads[block_root] = signed_envelope.message
    return store, signed_block, block_root


def make_signed_execution_proof(
    spec,
    state,
    checkpoint,
    *,
    prover_index=0,
    proof_data=b"\x01",
    proof_type=0,
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
        public_input=spec.PublicInput(origin=origin, head=head),
    )
    signature = spec.get_execution_proof_signature(state, proof, privkeys[prover_index])
    return spec.SignedExecutionProof(
        message=proof,
        validator_index=spec.ValidatorIndex(prover_index),
        signature=signature,
    )


def validate(spec, seen, store, state, signed_proof, checkpoint, proof_engine=None):
    if proof_engine is None:
        proof_engine = spec.PROOF_ENGINE
    return run_validate_gossip(
        spec,
        seen=seen,
        store=store,
        state=state,
        signed_execution_proof=signed_proof,
        trusted_execution_checkpoint=checkpoint,
        proof_engine=proof_engine,
    )


@with_eip8025_and_later
@spec_state_test
def test_validate_execution_proof_gossip_valid_and_duplicate(spec, state):
    store, signed_block, block_root = setup_store_with_payload(spec, state)
    checkpoint = spec.ExecutionCheckpoint(
        slot=signed_block.message.slot,
        beacon_block_root=block_root,
    )
    seen = get_seen(spec)
    signed_proof = make_signed_execution_proof(spec, state, checkpoint)

    assert validate(spec, seen, store, state, signed_proof, checkpoint) == (
        "valid",
        None,
    )
    assert validate(spec, seen, store, state, signed_proof, checkpoint) == (
        "ignore",
        "execution proof has already been processed",
    )

    competing_proof = make_signed_execution_proof(
        spec,
        state,
        checkpoint,
        prover_index=1,
        proof_data=b"\x02",
    )
    assert validate(spec, seen, store, state, competing_proof, checkpoint) == (
        "ignore",
        "valid proof already seen for this head and proof type",
    )


@with_eip8025_and_later
@spec_state_test
def test_validate_execution_proof_gossip_waits_for_payload(spec, state):
    store, signed_block, block_root = setup_store_with_payload(spec, state)
    checkpoint = spec.ExecutionCheckpoint(
        slot=signed_block.message.slot,
        beacon_block_root=block_root,
    )
    signed_proof = make_signed_execution_proof(spec, state, checkpoint)
    seen = get_seen(spec)
    envelope = store.payloads.pop(block_root)

    assert validate(spec, seen, store, state, signed_proof, checkpoint) == (
        "ignore",
        "execution proof's payload envelope has not been seen",
    )

    store.payloads[block_root] = envelope
    assert validate(spec, seen, store, state, signed_proof, checkpoint) == (
        "valid",
        None,
    )


@with_eip8025_and_later
@spec_state_test
def test_validate_execution_proof_gossip_tracks_invalid_prover_attempt(spec, state):
    store, signed_block, block_root = setup_store_with_payload(spec, state)
    checkpoint = spec.ExecutionCheckpoint(
        slot=signed_block.message.slot,
        beacon_block_root=block_root,
    )
    seen = get_seen(spec)
    empty_proof = make_signed_execution_proof(spec, state, checkpoint, proof_data=b"")

    assert validate(spec, seen, store, state, empty_proof, checkpoint) == (
        "reject",
        "execution proof data is empty",
    )

    retry = make_signed_execution_proof(spec, state, checkpoint, proof_data=b"\x02")
    assert validate(spec, seen, store, state, retry, checkpoint) == (
        "ignore",
        "proof already seen from this prover for this head and proof type",
    )


@with_eip8025_and_later
@spec_state_test
def test_validate_execution_proof_gossip_rejects_public_input_mismatch(spec, state):
    store, signed_block, block_root = setup_store_with_payload(spec, state)
    checkpoint = spec.ExecutionCheckpoint(
        slot=signed_block.message.slot,
        beacon_block_root=block_root,
    )
    wrong_origin = spec.ExecutionCheckpoint(
        slot=checkpoint.slot,
        beacon_block_root=spec.Root(b"\xaa" * 32),
    )
    signed_proof = make_signed_execution_proof(
        spec,
        state,
        checkpoint,
        origin=wrong_origin,
    )

    assert validate(spec, get_seen(spec), store, state, signed_proof, checkpoint) == (
        "reject",
        "execution proof's origin is not the trusted checkpoint",
    )

    wrong_head = spec.ExecutionCheckpoint(
        slot=spec.Slot(checkpoint.slot + 1),
        beacon_block_root=checkpoint.beacon_block_root,
    )
    signed_proof = make_signed_execution_proof(
        spec,
        state,
        checkpoint,
        prover_index=1,
        head=wrong_head,
    )
    assert validate(spec, get_seen(spec), store, state, signed_proof, checkpoint) == (
        "reject",
        "execution proof's head does not identify the accepted block",
    )


@with_eip8025_and_later
@spec_state_test
def test_validate_execution_proof_gossip_rejects_invalid_proof(spec, state):
    class RejectingProofEngine:
        def verify_execution_proof(self, _proof):
            return False

    store, signed_block, block_root = setup_store_with_payload(spec, state)
    checkpoint = spec.ExecutionCheckpoint(
        slot=signed_block.message.slot,
        beacon_block_root=block_root,
    )
    signed_proof = make_signed_execution_proof(spec, state, checkpoint)

    assert validate(
        spec,
        get_seen(spec),
        store,
        state,
        signed_proof,
        checkpoint,
        RejectingProofEngine(),
    ) == ("reject", "execution proof failed validation")
