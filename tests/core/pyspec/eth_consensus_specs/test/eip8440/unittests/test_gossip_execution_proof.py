from eth_consensus_specs.test.context import (
    always_bls,
    expect_assertion_error,
    spec_state_test,
    with_eip8440_and_later,
)
from eth_consensus_specs.test.eip8025.unittests.test_gossip_execution_proof import (
    make_signed_execution_proof,
    setup_store_with_block,
    UNSUPPORTED_LOW_PROOF_TYPE,
    validate,
)
from eth_consensus_specs.test.helpers.gossip import get_seen
from eth_consensus_specs.test.helpers.proof_engine import MockProofEngine


@with_eip8440_and_later
@spec_state_test
def test_execution_proof_is_keyed_by_head_block_root(spec, state):
    """
    Look up and store a proof by its head block, whatever its origin.
    """
    store, block_root = setup_store_with_block(spec, state)
    signed_proof = make_signed_execution_proof(
        spec, state, block_root, origin_block_root=spec.Root(b"\x01" * 32)
    )
    proof_engine = MockProofEngine()

    assert validate(spec, get_seen(spec), store, signed_proof, proof_engine) == ("valid", None)
    spec.on_execution_proof(store, signed_proof, proof_engine)
    assert proof_engine.verifications == [signed_proof.message, signed_proof.message]
    assert store.execution_proofs[block_root] == {
        signed_proof.message.proof_type: signed_proof.message
    }


@with_eip8440_and_later
@spec_state_test
@always_bls
def test_verify_signed_execution_proof(spec, state):
    """
    Authenticate a signed execution proof, and reject a tampered one.
    """
    store, block_root = setup_store_with_block(spec, state)
    block_state = store.block_states[block_root]
    signed_proof = make_signed_execution_proof(spec, state, block_root)
    spec.verify_signed_execution_proof(block_state, signed_proof)

    signed_proof.message.origin_block_root = spec.Root(b"\x01" * 32)
    expect_assertion_error(lambda: spec.verify_signed_execution_proof(block_state, signed_proof))


@with_eip8440_and_later
@spec_state_test
def test_execution_proof_does_not_require_payload(spec, state):
    """
    Accept and store a proof for a known block whose payload has not been seen.
    """
    store, block_root = setup_store_with_block(spec, state)
    store.payloads.pop(block_root)

    unknown_proof = make_signed_execution_proof(spec, state, spec.Root(b"\xaa" * 32))
    assert validate(spec, get_seen(spec), store, unknown_proof) == (
        "ignore",
        "execution proof's beacon block has not been seen",
    )

    signed_proof = make_signed_execution_proof(spec, state, block_root)
    proof_engine = MockProofEngine()
    assert validate(spec, get_seen(spec), store, signed_proof, proof_engine) == ("valid", None)
    spec.on_execution_proof(store, signed_proof, proof_engine)
    assert store.execution_proofs[block_root] == {
        signed_proof.message.proof_type: signed_proof.message
    }


@with_eip8440_and_later
@spec_state_test
def test_gossip_ignores_proof_for_unvalidated_block(spec, state):
    """
    Ignore a proof for a known block whose post-state is not yet available.
    """
    store, block_root = setup_store_with_block(spec, state)
    store.block_states.pop(block_root)
    signed_proof = make_signed_execution_proof(spec, state, block_root)
    proof_engine = MockProofEngine()
    seen = get_seen(spec)

    assert validate(spec, seen, store, signed_proof, proof_engine) == (
        "ignore",
        "execution proof's beacon block has not been validated",
    )
    assert proof_engine.verifications == []
    assert seen.execution_proof_roots == {}
    assert seen.execution_proof_provers == set()


@with_eip8440_and_later
@spec_state_test
def test_gossip_applies_cheap_checks_before_state_lookup(spec, state):
    """
    Apply message-local and deduplication checks before requiring the post-state.
    """
    store, block_root = setup_store_with_block(spec, state)
    store.block_states.pop(block_root)
    signed_proof = make_signed_execution_proof(spec, state, block_root)

    empty_proof = make_signed_execution_proof(spec, state, block_root, proof_data=b"")
    assert validate(spec, get_seen(spec), store, empty_proof) == (
        "reject",
        "execution proof is empty",
    )
    unsupported_proof = make_signed_execution_proof(
        spec, state, block_root, proof_type=UNSUPPORTED_LOW_PROOF_TYPE
    )
    assert validate(spec, get_seen(spec), store, unsupported_proof) == (
        "reject",
        "unexpected execution proof type",
    )

    seen = get_seen(spec)
    seen.execution_proof_roots[block_root] = {signed_proof.message.hash_tree_root()}
    assert validate(spec, seen, store, signed_proof) == (
        "ignore",
        "execution proof has already been processed",
    )

    seen = get_seen(spec)
    seen.execution_proof_provers.add(
        (block_root, signed_proof.message.proof_type, signed_proof.validator_index)
    )
    assert validate(spec, seen, store, signed_proof) == (
        "ignore",
        "proof already seen from this prover for this beacon block and proof type",
    )
