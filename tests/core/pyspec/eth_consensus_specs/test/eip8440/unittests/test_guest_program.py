from dataclasses import dataclass

import pytest

from eth_consensus_specs.test.context import (
    always_bls,
    expect_assertion_error,
    spec_state_test,
    with_eip8440_and_later,
)
from eth_consensus_specs.test.helpers.block import build_block_and_payload
from eth_consensus_specs.test.helpers.execution_payload import (
    compute_and_sign_execution_payload_envelope,
)
from eth_consensus_specs.test.helpers.proof_engine import MockProofEngine
from eth_consensus_specs.test.helpers.state import state_transition_and_sign_block

TEST_PROOF_TYPE = 1


class MockExecutionEngine:
    def __init__(self, *, valid_payload=True):
        self.valid_payload = valid_payload
        self.new_payload_requests = []

    def verify_and_notify_new_payload(self, new_payload_request):
        self.new_payload_requests.append(new_payload_request)
        return self.valid_payload


@dataclass
class AppliedBlock:
    root: object
    state: object
    payload: object
    execution_requests: object
    signed_envelope: object


def apply_block(spec, state, slot=None, parent=None, execution_requests=None):
    """
    Apply a block to ``state``. When ``parent``, the parent block, is given, the
    block applies its payload. Otherwise the block treats its parent as empty and
    builds on the last applied payload. Return the block root, its post-state,
    and its signed payload envelope.
    """
    if slot is None:
        slot = state.slot + 1
    if execution_requests is None:
        execution_requests = spec.ExecutionRequests()
    parent_payload = None if parent is None else parent.payload
    block, payload = build_block_and_payload(
        spec,
        state,
        slot,
        parent_payload=parent_payload,
        execution_requests=execution_requests,
    )
    if parent is not None:
        block.body.parent_execution_requests = parent.execution_requests
    signed_block = state_transition_and_sign_block(spec, state, block)
    root = spec.hash_tree_root(block)
    signed_envelope = compute_and_sign_execution_payload_envelope(
        spec, state, root, signed_block, payload, execution_requests
    )
    return AppliedBlock(root, state.copy(), payload, execution_requests, signed_envelope)


def make_previous_proof(spec, head, origin_block_root):
    return spec.ExecutionProof(
        proof_data=spec.ProofData(data=[1]),
        proof_type=spec.ProofType(TEST_PROOF_TYPE),
        origin_block_root=origin_block_root,
        head_block_root=head.root,
    )


def base_input(spec, target):
    return spec.PrivateInput(
        previous_proof=None,
        previous_state=None,
        state=target.state,
        signed_envelope=target.signed_envelope,
        execution_witness=None,
    )


def recursive_input(spec, previous, target, origin_block_root):
    return spec.PrivateInput(
        previous_proof=make_previous_proof(spec, previous, origin_block_root),
        previous_state=previous.state,
        state=target.state,
        signed_envelope=target.signed_envelope,
        execution_witness=None,
    )


def expected_public_input(spec, origin_block_root, head):
    return spec.PublicInput(
        origin_block_root=origin_block_root,
        head_block_root=head.root,
        chain_id=spec.config.DEPOSIT_CHAIN_ID,
        schema_id=spec.STATELESS_INPUT_SCHEMA_ID,
    )


def expected_new_payload_request(spec, target):
    envelope = target.signed_envelope.message
    bid = target.state.latest_execution_payload_bid
    return spec.NewPayloadRequest(
        execution_payload=envelope.payload,
        versioned_hashes=spec.VersionedHashes(
            data=[
                spec.kzg_commitment_to_versioned_hash(commitment)
                for commitment in bid.blob_kzg_commitments
            ]
        ),
        parent_beacon_block_root=envelope.parent_beacon_block_root,
        execution_requests=envelope.execution_requests,
    )


@with_eip8440_and_later
@spec_state_test
def test_base_step_starts_recursion_at_target(spec, state):
    """
    A base step proves its own block's payload and is its own origin.
    """
    target = apply_block(spec, state)
    proof_engine = MockProofEngine()
    execution_engine = MockExecutionEngine()

    public_input = spec.verify_execution_transition(
        proof_engine, execution_engine, base_input(spec, target)
    )

    assert public_input == expected_public_input(spec, target.root, target)
    assert proof_engine.verifications == []
    assert execution_engine.new_payload_requests == [expected_new_payload_request(spec, target)]


@with_eip8440_and_later
@spec_state_test
def test_recursive_step_from_adjacent_full_block(spec, state):
    """
    Extend a parent proof to the next block, which applies the parent's payload.
    """
    origin = apply_block(spec, state)
    target = apply_block(spec, state, parent=origin)
    proof_engine = MockProofEngine()
    execution_engine = MockExecutionEngine()

    public_input = spec.verify_execution_transition(
        proof_engine, execution_engine, recursive_input(spec, origin, target, origin.root)
    )

    assert public_input == expected_public_input(spec, origin.root, target)
    assert proof_engine.verifications == [make_previous_proof(spec, origin, origin.root)]
    assert execution_engine.new_payload_requests == [expected_new_payload_request(spec, target)]


@with_eip8440_and_later
@spec_state_test
def test_recursive_step_across_empty_blocks_and_missed_slot(spec, state):
    """
    A step spans empty blocks and a missed slot without seeing them, and the
    origin carries through every step.
    """
    origin = apply_block(spec, state)
    previous = apply_block(spec, state, parent=origin)
    # The next block applies the previous payload, but its own payload and that
    # of the block after a missed slot are never applied
    apply_block(spec, state, parent=previous)
    apply_block(spec, state, slot=state.slot + 2)
    target = apply_block(spec, state)
    assert target.state.slot == previous.state.slot + 4
    assert target.state.latest_block_hash == previous.payload.block_hash

    public_input = spec.verify_execution_transition(
        MockProofEngine(),
        MockExecutionEngine(),
        recursive_input(spec, previous, target, origin.root),
    )

    assert public_input == expected_public_input(spec, origin.root, target)


@with_eip8440_and_later
@spec_state_test
def test_recursive_step_rejects_skipped_full_payload(spec, state):
    """
    A step cannot skip a payload applied between the parent proof's head and
    the target.
    """
    previous = apply_block(spec, state)
    skipped = apply_block(spec, state, parent=previous)
    target = apply_block(spec, state, parent=skipped)

    expect_assertion_error(
        lambda: spec.verify_execution_transition(
            MockProofEngine(),
            MockExecutionEngine(),
            recursive_input(spec, previous, target, previous.root),
        )
    )


@with_eip8440_and_later
@spec_state_test
def test_recursive_step_rejects_payload_not_applied_by_target(spec, state):
    """
    A step cannot extend a parent whose payload the target's branch treats as
    empty.
    """
    previous = apply_block(spec, state, parent=apply_block(spec, state))
    # The target builds on the payload before the previous one
    target = apply_block(spec, state)

    expect_assertion_error(
        lambda: spec.verify_execution_transition(
            MockProofEngine(),
            MockExecutionEngine(),
            recursive_input(spec, previous, target, previous.root),
        )
    )


@with_eip8440_and_later
@spec_state_test
def test_recursive_step_rejects_mismatched_previous_state(spec, state):
    """
    The previous state must be the post-state of the parent proof's head block.
    """
    previous = apply_block(spec, state)
    target = apply_block(spec, state, parent=previous)
    private_input = recursive_input(spec, previous, target, previous.root)

    # The post-state of a different block
    private_input.previous_state = target.state
    expect_assertion_error(
        lambda: spec.verify_execution_transition(
            MockProofEngine(), MockExecutionEngine(), private_input
        )
    )

    # The right block's state advanced by a slot
    advanced_state = previous.state.copy()
    spec.process_slots(advanced_state, advanced_state.slot + 1)
    private_input.previous_state = advanced_state
    expect_assertion_error(
        lambda: spec.verify_execution_transition(
            MockProofEngine(), MockExecutionEngine(), private_input
        )
    )


@with_eip8440_and_later
@spec_state_test
def test_recursive_step_rejects_invalid_previous_proof(spec, state):
    """
    A step cannot extend a parent proof that does not verify.
    """
    previous = apply_block(spec, state)
    target = apply_block(spec, state, parent=previous)
    proof_engine = MockProofEngine(valid_proof_data=[])
    execution_engine = MockExecutionEngine()

    expect_assertion_error(
        lambda: spec.verify_execution_transition(
            proof_engine, execution_engine, recursive_input(spec, previous, target, previous.root)
        )
    )


@with_eip8440_and_later
@spec_state_test
def test_step_input_shape_is_enforced(spec, state):
    """
    A base step must not carry a previous state, and a recursive step must.
    """
    previous = apply_block(spec, state)
    target = apply_block(spec, state, parent=previous)

    private_input = base_input(spec, target)
    private_input.previous_state = previous.state
    expect_assertion_error(
        lambda: spec.verify_execution_transition(
            MockProofEngine(), MockExecutionEngine(), private_input
        )
    )

    private_input = recursive_input(spec, previous, target, previous.root)
    private_input.previous_state = None
    expect_assertion_error(
        lambda: spec.verify_execution_transition(
            MockProofEngine(), MockExecutionEngine(), private_input
        )
    )


@with_eip8440_and_later
@spec_state_test
def test_step_rejects_invalid_payload(spec, state):
    """
    A step fails when stateless validation rejects the payload.
    """
    target = apply_block(spec, state)

    expect_assertion_error(
        lambda: spec.verify_execution_transition(
            MockProofEngine(), MockExecutionEngine(valid_payload=False), base_input(spec, target)
        )
    )


@with_eip8440_and_later
@spec_state_test
def test_step_rejects_envelope_inconsistent_with_state(spec, state):
    """
    The payload envelope handler binds the payload to the target block's state.
    """
    target = apply_block(spec, state)

    def run_with(mutate):
        private_input = base_input(spec, target)
        private_input.signed_envelope = target.signed_envelope.copy()
        mutate(private_input.signed_envelope.message)
        expect_assertion_error(
            lambda: spec.verify_execution_transition(
                MockProofEngine(), MockExecutionEngine(), private_input
            )
        )

    def wrong_timestamp(envelope):
        envelope.payload.timestamp += 1

    def wrong_withdrawals(envelope):
        envelope.payload.withdrawals.append(spec.Withdrawal())

    def wrong_gas_limit(envelope):
        envelope.payload.gas_limit += 1

    def wrong_parent_hash(envelope):
        envelope.payload.parent_hash = spec.Hash32(b"\x42" * 32)

    def wrong_block_root(envelope):
        envelope.beacon_block_root = spec.Root(b"\x42" * 32)

    for mutate in (
        wrong_timestamp,
        wrong_withdrawals,
        wrong_gas_limit,
        wrong_parent_hash,
        wrong_block_root,
    ):
        run_with(mutate)


@with_eip8440_and_later
@spec_state_test
@always_bls
def test_step_rejects_invalid_envelope_signature(spec, state):
    """
    The guest verifies the envelope signature against the signer in the state.
    """
    target = apply_block(spec, state)
    private_input = base_input(spec, target)
    assert spec.verify_execution_transition(MockProofEngine(), MockExecutionEngine(), private_input)

    private_input.signed_envelope = target.signed_envelope.copy()
    private_input.signed_envelope.signature = spec.BLSSignature()
    expect_assertion_error(
        lambda: spec.verify_execution_transition(
            MockProofEngine(), MockExecutionEngine(), private_input
        )
    )


@with_eip8440_and_later
@spec_state_test
def test_step_rejects_execution_requests_over_limit(spec, state):
    """
    The guest enforces the per-payload request limits that Gloas checks only in
    gossip, even when the block commits to the requests.
    """
    execution_requests = spec.ExecutionRequests()
    execution_requests.withdrawals = spec.WithdrawalRequests(
        data=[spec.WithdrawalRequest()] * (spec.MAX_WITHDRAWAL_REQUESTS_PER_PAYLOAD + 1)
    )
    target = apply_block(spec, state, execution_requests=execution_requests)

    with pytest.raises(spec.GossipReject):
        spec.verify_execution_transition(
            MockProofEngine(), MockExecutionEngine(), base_input(spec, target)
        )


@with_eip8440_and_later
@spec_state_test
def test_recursive_step_rejects_parent_head_as_target(spec, state):
    """
    A step cannot extend a parent proof to the parent's own head block.
    """
    previous = apply_block(spec, state)

    expect_assertion_error(
        lambda: spec.verify_execution_transition(
            MockProofEngine(),
            MockExecutionEngine(),
            recursive_input(spec, previous, previous, previous.root),
        )
    )


@with_eip8440_and_later
@spec_state_test
def test_step_rejects_withdrawals_over_limit(spec, state):
    """
    The guest rejects a payload with more withdrawals than the per-payload limit
    that Gloas checks in gossip. The state never expects that many, so the
    envelope handler's withdrawals check rejects such a payload as well.
    """
    target = apply_block(spec, state)
    private_input = base_input(spec, target)
    private_input.signed_envelope = target.signed_envelope.copy()
    private_input.signed_envelope.message.payload.withdrawals = spec.Withdrawals(
        data=[spec.Withdrawal()] * (spec.MAX_WITHDRAWALS_PER_PAYLOAD + 1)
    )

    expect_assertion_error(
        lambda: spec.verify_execution_transition(
            MockProofEngine(), MockExecutionEngine(), private_input
        )
    )
