from eth_consensus_specs.test.context import (
    spec_state_test,
    with_gloas_and_later,
)
from eth_consensus_specs.test.helpers.block import (
    build_empty_block_for_next_slot,
    sign_block,
)
from eth_consensus_specs.test.helpers.execution_payload import (
    build_signed_execution_payload_envelope,
)
from eth_consensus_specs.test.helpers.fork_choice import (
    get_genesis_forkchoice_store_and_block,
)
from eth_consensus_specs.test.helpers.gossip import (
    get_filename,
    get_seen,
    make_progressive_list,
    run_validate_gossip,
    setup_store_with_failed_block,
    wrap_genesis_block,
)


@with_gloas_and_later
@spec_state_test
def test_gossip_beacon_block__valid_parent_empty(spec, state):
    """A block building on an empty parent (to execution payload)."""
    anchor_state = state.copy()
    yield "topic", "meta", "beacon_block"

    store, anchor_block = get_genesis_forkchoice_store_and_block(spec, state)
    signed_anchor = wrap_genesis_block(spec, anchor_block)
    yield "state", anchor_state
    yield get_filename(signed_anchor), signed_anchor
    yield "blocks", "meta", [{"block": get_filename(signed_anchor)}]

    seen = get_seen(spec)
    block = build_empty_block_for_next_slot(spec, state)
    # Claim the parent is empty by building on the pre-payload block hash,
    # which does not match the parent bid's block_hash. The parent payload
    # check does not apply, so no envelope is needed for the block to be valid.
    block.body.signed_execution_payload_bid.message.parent_block_hash = state.latest_block_hash
    assert not spec.is_parent_node_full(store, block)
    signed_block = sign_block(spec, state, block, proposer_index=block.proposer_index)
    yield get_filename(signed_block), signed_block

    time_ms = spec.compute_time_at_slot_ms(state, signed_block.message.slot)
    yield "current_time_ms", "meta", int(time_ms)
    messages = []

    time_ms += 500
    result, reason = run_validate_gossip(
        spec,
        seen=seen,
        store=store,
        state=state,
        signed_beacon_block=signed_block,
        current_time_ms=time_ms,
    )
    assert result == "valid"
    assert reason is None
    messages.append(
        {
            "current_time_ms": int(time_ms),
            "message": get_filename(signed_block),
            "expected": result,
        }
    )

    yield "messages", "meta", messages


@with_gloas_and_later
@spec_state_test
def test_gossip_beacon_block__valid_parent_full(spec, state):
    """A block building on a full parent (with an execution payload)."""
    anchor_state = state.copy()
    yield "topic", "meta", "beacon_block"

    store, anchor_block = get_genesis_forkchoice_store_and_block(spec, state)
    signed_anchor = wrap_genesis_block(spec, anchor_block)
    anchor_root = anchor_block.hash_tree_root()
    yield "state", anchor_state
    yield get_filename(signed_anchor), signed_anchor

    # The parent's payload has been received and verified, recorded in the
    # store as `on_execution_payload_envelope` would.
    signed_envelope = build_signed_execution_payload_envelope(
        spec, state, anchor_root, signed_anchor
    )
    store.payloads[anchor_root] = signed_envelope.message
    yield get_filename(signed_envelope), signed_envelope
    yield (
        "blocks",
        "meta",
        [
            {
                "block": get_filename(signed_anchor),
                "payload": get_filename(signed_envelope),
            }
        ],
    )

    seen = get_seen(spec)
    block = build_empty_block_for_next_slot(spec, state)
    # Claim the parent is full by matching the bid's parent_block_hash to the
    # parent bid's block_hash.
    parent_bid = anchor_block.body.signed_execution_payload_bid.message
    block.body.signed_execution_payload_bid.message.parent_block_hash = parent_bid.block_hash
    assert spec.is_parent_node_full(store, block)
    signed_block = sign_block(spec, state, block, proposer_index=block.proposer_index)
    yield get_filename(signed_block), signed_block

    time_ms = spec.compute_time_at_slot_ms(state, signed_block.message.slot)
    yield "current_time_ms", "meta", int(time_ms)
    messages = []

    time_ms += 500
    result, reason = run_validate_gossip(
        spec,
        seen=seen,
        store=store,
        state=state,
        signed_beacon_block=signed_block,
        current_time_ms=time_ms,
    )
    assert result == "valid"
    assert reason is None
    messages.append(
        {
            "current_time_ms": int(time_ms),
            "message": get_filename(signed_block),
            "expected": result,
        }
    )

    yield "messages", "meta", messages


@with_gloas_and_later
@spec_state_test
def test_gossip_beacon_block__ignore_parent_payload_not_verified(spec, state):
    """A block building on a full parent whose payload is not verified is ignored."""
    anchor_state = state.copy()
    yield "topic", "meta", "beacon_block"

    store, anchor_block = get_genesis_forkchoice_store_and_block(spec, state)
    signed_anchor = wrap_genesis_block(spec, anchor_block)
    yield "state", anchor_state
    yield get_filename(signed_anchor), signed_anchor
    yield "blocks", "meta", [{"block": get_filename(signed_anchor)}]

    seen = get_seen(spec)
    block = build_empty_block_for_next_slot(spec, state)
    # Claim the parent is full by matching the bid's parent_block_hash to the
    # parent bid's block_hash. The parent's payload has not been verified
    # (there is no envelope in the store), so the block must be ignored.
    parent_bid = anchor_block.body.signed_execution_payload_bid.message
    block.body.signed_execution_payload_bid.message.parent_block_hash = parent_bid.block_hash
    signed_block = sign_block(spec, state, block, proposer_index=block.proposer_index)
    yield get_filename(signed_block), signed_block

    time_ms = spec.compute_time_at_slot_ms(state, signed_block.message.slot)
    yield "current_time_ms", "meta", int(time_ms)
    messages = []

    time_ms += 500
    result, reason = run_validate_gossip(
        spec,
        seen=seen,
        store=store,
        state=state,
        signed_beacon_block=signed_block,
        current_time_ms=time_ms,
    )
    assert result == "ignore"
    assert reason == "parent payload is not verified"
    messages.append(
        {
            "current_time_ms": int(time_ms),
            "message": get_filename(signed_block),
            "expected": result,
            "reason": reason,
        }
    )

    yield "messages", "meta", messages


@with_gloas_and_later
@spec_state_test
def test_gossip_beacon_block__reject_bid_not_on_parent_execution_head(spec, state):
    """A block whose bid builds on an unrelated execution head is rejected.

    The bid's parent_block_hash is neither the parent bid's block_hash (which
    would make the parent full) nor the parent state's latest_block_hash (the
    empty-parent branch), so it is classified as an empty parent yet does not
    build on the parent's execution head. Block processing rejects such a block,
    so gossip must reject it too.
    """
    anchor_state = state.copy()
    yield "topic", "meta", "beacon_block"

    store, anchor_block = get_genesis_forkchoice_store_and_block(spec, state)
    signed_anchor = wrap_genesis_block(spec, anchor_block)
    yield "state", anchor_state
    yield get_filename(signed_anchor), signed_anchor
    yield "blocks", "meta", [{"block": get_filename(signed_anchor)}]

    seen = get_seen(spec)
    block = build_empty_block_for_next_slot(spec, state)
    # An arbitrary execution head that is neither the parent's payload hash
    # (full) nor the parent state's latest_block_hash (empty). Every other
    # condition is satisfied, so any client rejects regardless of check order.
    bid = block.body.signed_execution_payload_bid.message
    bid.parent_block_hash = spec.Hash32(b"\xab" * 32)
    assert not spec.is_parent_node_full(store, block)
    assert bid.parent_block_hash != state.latest_block_hash
    signed_block = sign_block(spec, state, block, proposer_index=block.proposer_index)
    yield get_filename(signed_block), signed_block

    time_ms = spec.compute_time_at_slot_ms(state, signed_block.message.slot)
    yield "current_time_ms", "meta", int(time_ms)
    messages = []

    time_ms += 500
    result, reason = run_validate_gossip(
        spec,
        seen=seen,
        store=store,
        state=state,
        signed_beacon_block=signed_block,
        current_time_ms=time_ms,
    )
    assert result == "reject"
    assert reason == "bid does not build on the parent's execution head"
    messages.append(
        {
            "current_time_ms": int(time_ms),
            "message": get_filename(signed_block),
            "expected": result,
            "reason": reason,
        }
    )

    yield "messages", "meta", messages


@with_gloas_and_later
@spec_state_test
def test_gossip_beacon_block__reject_too_many_blob_commitments(spec, state):
    """A block whose bid carries more KZG commitments than the per-epoch limit is rejected."""
    anchor_state = state.copy()
    yield "topic", "meta", "beacon_block"

    store, anchor_block = get_genesis_forkchoice_store_and_block(spec, state)
    signed_anchor = wrap_genesis_block(spec, anchor_block)
    yield "state", anchor_state
    yield get_filename(signed_anchor), signed_anchor
    yield "blocks", "meta", [{"block": get_filename(signed_anchor)}]

    seen = get_seen(spec)
    block = build_empty_block_for_next_slot(spec, state)
    max_blobs = spec.get_blob_parameters(spec.get_current_epoch(state)).max_blobs_per_block
    over_limit = int(max_blobs) + 1
    block.body.signed_execution_payload_bid.message.blob_kzg_commitments = spec.List[
        spec.KZGCommitment, spec.MAX_BLOB_COMMITMENTS_PER_BLOCK
    ](*([spec.KZGCommitment()] * over_limit))
    signed_block = sign_block(spec, state, block, proposer_index=block.proposer_index)
    yield get_filename(signed_block), signed_block

    time_ms = spec.compute_time_at_slot_ms(state, signed_block.message.slot)
    yield "current_time_ms", "meta", int(time_ms)
    messages = []

    time_ms += 500
    result, reason = run_validate_gossip(
        spec,
        seen=seen,
        store=store,
        state=state,
        signed_beacon_block=signed_block,
        current_time_ms=time_ms,
    )
    assert result == "reject"
    assert reason == "too many blob kzg commitments"
    messages.append(
        {
            "current_time_ms": int(time_ms),
            "message": get_filename(signed_block),
            "expected": result,
            "reason": reason,
        }
    )

    yield "messages", "meta", messages


@with_gloas_and_later
@spec_state_test
def test_gossip_beacon_block__reject_bid_parent_root_mismatch(spec, state):
    """A block whose bid parent_block_root does not match its parent_root is rejected."""
    anchor_state = state.copy()
    yield "topic", "meta", "beacon_block"

    store, anchor_block = get_genesis_forkchoice_store_and_block(spec, state)
    signed_anchor = wrap_genesis_block(spec, anchor_block)
    yield "state", anchor_state
    yield get_filename(signed_anchor), signed_anchor
    yield "blocks", "meta", [{"block": get_filename(signed_anchor)}]

    seen = get_seen(spec)
    block = build_empty_block_for_next_slot(spec, state)
    # Corrupt the bid's parent_block_root.
    block.body.signed_execution_payload_bid.message.parent_block_root = spec.Root(b"\xab" * 32)
    signed_block = sign_block(spec, state, block, proposer_index=block.proposer_index)
    yield get_filename(signed_block), signed_block

    time_ms = spec.compute_time_at_slot_ms(state, signed_block.message.slot)
    yield "current_time_ms", "meta", int(time_ms)
    messages = []

    time_ms += 500
    result, reason = run_validate_gossip(
        spec,
        seen=seen,
        store=store,
        state=state,
        signed_beacon_block=signed_block,
        current_time_ms=time_ms,
    )
    assert result == "reject"
    assert reason == "bid's parent does not equal block's parent"
    messages.append(
        {
            "current_time_ms": int(time_ms),
            "message": get_filename(signed_block),
            "expected": result,
            "reason": reason,
        }
    )

    yield "messages", "meta", messages


@with_gloas_and_later
@spec_state_test
def test_gossip_beacon_block__reject_parent_failed_validation(spec, state):
    """A block whose parent failed validation is rejected."""
    anchor_state = state.copy()
    yield "topic", "meta", "beacon_block"

    store, signed_anchor, signed_parent = setup_store_with_failed_block(spec, state)
    parent_root = signed_parent.message.hash_tree_root()
    yield "state", anchor_state
    yield get_filename(signed_anchor), signed_anchor
    yield get_filename(signed_parent), signed_parent
    yield (
        "blocks",
        "meta",
        [
            {"block": get_filename(signed_anchor)},
            {"block": get_filename(signed_parent), "failed": True},
        ],
    )

    # Build the child on the valid version of the parent, then re-point it at
    # the failed parent.
    child = build_empty_block_for_next_slot(spec, state)
    child.parent_root = parent_root
    child.body.signed_execution_payload_bid.message.parent_block_root = parent_root
    signed_child = sign_block(spec, state, child, proposer_index=child.proposer_index)
    yield get_filename(signed_child), signed_child

    seen = get_seen(spec)
    time_ms = spec.compute_time_at_slot_ms(state, child.slot)
    yield "current_time_ms", "meta", int(time_ms)
    messages = []

    time_ms += 500
    result, reason = run_validate_gossip(
        spec,
        seen=seen,
        store=store,
        state=state,
        signed_beacon_block=signed_child,
        current_time_ms=time_ms,
    )
    assert result == "reject"
    assert reason == "block's parent is invalid"
    messages.append(
        {
            "current_time_ms": int(time_ms),
            "message": get_filename(signed_child),
            "expected": result,
            "reason": reason,
        }
    )

    yield "messages", "meta", messages


def _assert_beacon_block_gossip(spec, state, mutate_block, expected, reason=None):
    """
    Build a block on the genesis anchor with an empty parent, apply ``mutate_block``,
    and assert gossip validation returns ``expected`` (with ``reason`` when rejected).

    The empty-parent base is otherwise valid, so it serves both the limit (valid) and
    limit+1 (reject) count tests: only the mutated count differs between them.
    """
    anchor_state = state.copy()
    yield "topic", "meta", "beacon_block"

    store, anchor_block = get_genesis_forkchoice_store_and_block(spec, state)
    signed_anchor = wrap_genesis_block(spec, anchor_block)
    yield "state", anchor_state
    yield get_filename(signed_anchor), signed_anchor
    yield "blocks", "meta", [{"block": get_filename(signed_anchor)}]

    seen = get_seen(spec)
    block = build_empty_block_for_next_slot(spec, state)
    # Treat the parent as empty so no parent payload envelope is required for validity.
    block.body.signed_execution_payload_bid.message.parent_block_hash = state.latest_block_hash
    mutate_block(spec, block)
    signed_block = sign_block(spec, state, block, proposer_index=block.proposer_index)
    yield get_filename(signed_block), signed_block

    time_ms = spec.compute_time_at_slot_ms(state, signed_block.message.slot)
    yield "current_time_ms", "meta", int(time_ms)
    messages = []

    time_ms += 500
    result, reason_out = run_validate_gossip(
        spec,
        seen=seen,
        store=store,
        state=state,
        signed_beacon_block=signed_block,
        current_time_ms=time_ms,
    )
    assert result == expected
    assert reason_out == reason
    message = {
        "current_time_ms": int(time_ms),
        "message": get_filename(signed_block),
        "expected": result,
    }
    if reason is not None:
        message["reason"] = reason
    messages.append(message)

    yield "messages", "meta", messages


@with_gloas_and_later
@spec_state_test
def test_gossip_beacon_block__valid_max_parent_withdrawal_requests(spec, state):
    """A block with the maximum number of parent withdrawal requests is valid."""

    def mutate(spec, block):
        count = int(spec.MAX_WITHDRAWAL_REQUESTS_PER_PAYLOAD)
        block.body.parent_execution_requests = spec.ExecutionRequests(
            withdrawals=spec.WithdrawalRequests(*([spec.WithdrawalRequest()] * count))
        )

    yield from _assert_beacon_block_gossip(spec, state, mutate, "valid")


@with_gloas_and_later
@spec_state_test
def test_gossip_beacon_block__reject_too_many_parent_withdrawal_requests(spec, state):
    """A block whose parent execution requests exceed the withdrawal-request limit is rejected."""

    def mutate(spec, block):
        count = int(spec.MAX_WITHDRAWAL_REQUESTS_PER_PAYLOAD) + 1
        block.body.parent_execution_requests = spec.ExecutionRequests(
            withdrawals=spec.WithdrawalRequests(*([spec.WithdrawalRequest()] * count))
        )

    yield from _assert_beacon_block_gossip(
        spec, state, mutate, "reject", "too many parent withdrawal requests"
    )


@with_gloas_and_later
@spec_state_test
def test_gossip_beacon_block__valid_max_parent_consolidation_requests(spec, state):
    """A block with the maximum number of parent consolidation requests is valid."""

    def mutate(spec, block):
        count = int(spec.MAX_CONSOLIDATION_REQUESTS_PER_PAYLOAD)
        block.body.parent_execution_requests = spec.ExecutionRequests(
            consolidations=spec.ConsolidationRequests(*([spec.ConsolidationRequest()] * count))
        )

    yield from _assert_beacon_block_gossip(spec, state, mutate, "valid")


@with_gloas_and_later
@spec_state_test
def test_gossip_beacon_block__reject_too_many_parent_consolidation_requests(spec, state):
    """A block whose parent execution requests exceed the consolidation-request limit is rejected."""

    def mutate(spec, block):
        count = int(spec.MAX_CONSOLIDATION_REQUESTS_PER_PAYLOAD) + 1
        block.body.parent_execution_requests = spec.ExecutionRequests(
            consolidations=spec.ConsolidationRequests(*([spec.ConsolidationRequest()] * count))
        )

    yield from _assert_beacon_block_gossip(
        spec, state, mutate, "reject", "too many parent consolidation requests"
    )


@with_gloas_and_later
@spec_state_test
def test_gossip_beacon_block__valid_max_parent_builder_deposit_requests(spec, state):
    """A block with the maximum number of parent builder deposit requests is valid."""

    def mutate(spec, block):
        count = int(spec.MAX_BUILDER_DEPOSIT_REQUESTS_PER_PAYLOAD)
        block.body.parent_execution_requests = spec.ExecutionRequests(
            builder_deposits=spec.BuilderDepositRequests(*([spec.BuilderDepositRequest()] * count))
        )

    yield from _assert_beacon_block_gossip(spec, state, mutate, "valid")


@with_gloas_and_later
@spec_state_test
def test_gossip_beacon_block__reject_too_many_parent_builder_deposit_requests(spec, state):
    """A block whose parent execution requests exceed the builder-deposit-request limit is rejected."""

    def mutate(spec, block):
        count = int(spec.MAX_BUILDER_DEPOSIT_REQUESTS_PER_PAYLOAD) + 1
        block.body.parent_execution_requests = spec.ExecutionRequests(
            builder_deposits=spec.BuilderDepositRequests(*([spec.BuilderDepositRequest()] * count))
        )

    yield from _assert_beacon_block_gossip(
        spec, state, mutate, "reject", "too many parent builder deposit requests"
    )


@with_gloas_and_later
@spec_state_test
def test_gossip_beacon_block__valid_max_parent_builder_exit_requests(spec, state):
    """A block with the maximum number of parent builder exit requests is valid."""

    def mutate(spec, block):
        count = int(spec.MAX_BUILDER_EXIT_REQUESTS_PER_PAYLOAD)
        block.body.parent_execution_requests = spec.ExecutionRequests(
            builder_exits=spec.BuilderExitRequests(*([spec.BuilderExitRequest()] * count))
        )

    yield from _assert_beacon_block_gossip(spec, state, mutate, "valid")


@with_gloas_and_later
@spec_state_test
def test_gossip_beacon_block__reject_too_many_parent_builder_exit_requests(spec, state):
    """A block whose parent execution requests exceed the builder-exit-request limit is rejected."""

    def mutate(spec, block):
        count = int(spec.MAX_BUILDER_EXIT_REQUESTS_PER_PAYLOAD) + 1
        block.body.parent_execution_requests = spec.ExecutionRequests(
            builder_exits=spec.BuilderExitRequests(*([spec.BuilderExitRequest()] * count))
        )

    yield from _assert_beacon_block_gossip(
        spec, state, mutate, "reject", "too many parent builder exit requests"
    )


@with_gloas_and_later
@spec_state_test
def test_gossip_beacon_block__valid_max_proposer_slashings(spec, state):
    """A block with the maximum number of proposer slashings is valid."""

    def mutate(spec, block):
        block.body.proposer_slashings = make_progressive_list(
            spec, spec.ProposerSlashing, int(spec.MAX_PROPOSER_SLASHINGS)
        )

    yield from _assert_beacon_block_gossip(spec, state, mutate, "valid")


@with_gloas_and_later
@spec_state_test
def test_gossip_beacon_block__reject_too_many_proposer_slashings(spec, state):
    """A block with more proposer slashings than the limit is rejected."""

    def mutate(spec, block):
        block.body.proposer_slashings = make_progressive_list(
            spec, spec.ProposerSlashing, int(spec.MAX_PROPOSER_SLASHINGS) + 1
        )

    yield from _assert_beacon_block_gossip(
        spec, state, mutate, "reject", "too many proposer slashings"
    )


@with_gloas_and_later
@spec_state_test
def test_gossip_beacon_block__valid_max_attester_slashings(spec, state):
    """A block with the maximum number of attester slashings is valid."""

    def mutate(spec, block):
        block.body.attester_slashings = make_progressive_list(
            spec, spec.AttesterSlashing, int(spec.MAX_ATTESTER_SLASHINGS_ELECTRA)
        )

    yield from _assert_beacon_block_gossip(spec, state, mutate, "valid")


@with_gloas_and_later
@spec_state_test
def test_gossip_beacon_block__reject_too_many_attester_slashings(spec, state):
    """A block with more attester slashings than the limit is rejected."""

    def mutate(spec, block):
        block.body.attester_slashings = make_progressive_list(
            spec, spec.AttesterSlashing, int(spec.MAX_ATTESTER_SLASHINGS_ELECTRA) + 1
        )

    yield from _assert_beacon_block_gossip(
        spec, state, mutate, "reject", "too many attester slashings"
    )


@with_gloas_and_later
@spec_state_test
def test_gossip_beacon_block__valid_max_attestations(spec, state):
    """A block with the maximum number of attestations is valid."""

    def mutate(spec, block):
        block.body.attestations = make_progressive_list(
            spec, spec.Attestation, int(spec.MAX_ATTESTATIONS_ELECTRA)
        )

    yield from _assert_beacon_block_gossip(spec, state, mutate, "valid")


@with_gloas_and_later
@spec_state_test
def test_gossip_beacon_block__reject_too_many_attestations(spec, state):
    """A block with more attestations than the limit is rejected."""

    def mutate(spec, block):
        block.body.attestations = make_progressive_list(
            spec, spec.Attestation, int(spec.MAX_ATTESTATIONS_ELECTRA) + 1
        )

    yield from _assert_beacon_block_gossip(spec, state, mutate, "reject", "too many attestations")


@with_gloas_and_later
@spec_state_test
def test_gossip_beacon_block__valid_no_deposits(spec, state):
    """A block with no deposits (the maximum allowed) is valid."""

    def mutate(spec, block):
        block.body.deposits = make_progressive_list(spec, spec.Deposit, 0)

    yield from _assert_beacon_block_gossip(spec, state, mutate, "valid")


@with_gloas_and_later
@spec_state_test
def test_gossip_beacon_block__reject_contains_deposits(spec, state):
    """A block that carries any deposits is rejected."""

    def mutate(spec, block):
        block.body.deposits = make_progressive_list(spec, spec.Deposit, 1)

    yield from _assert_beacon_block_gossip(
        spec, state, mutate, "reject", "block must not contain deposits"
    )


@with_gloas_and_later
@spec_state_test
def test_gossip_beacon_block__valid_max_voluntary_exits(spec, state):
    """A block with the maximum number of voluntary exits is valid."""

    def mutate(spec, block):
        block.body.voluntary_exits = make_progressive_list(
            spec, spec.SignedVoluntaryExit, int(spec.MAX_VOLUNTARY_EXITS)
        )

    yield from _assert_beacon_block_gossip(spec, state, mutate, "valid")


@with_gloas_and_later
@spec_state_test
def test_gossip_beacon_block__reject_too_many_voluntary_exits(spec, state):
    """A block with more voluntary exits than the limit is rejected."""

    def mutate(spec, block):
        block.body.voluntary_exits = make_progressive_list(
            spec, spec.SignedVoluntaryExit, int(spec.MAX_VOLUNTARY_EXITS) + 1
        )

    yield from _assert_beacon_block_gossip(
        spec, state, mutate, "reject", "too many voluntary exits"
    )


@with_gloas_and_later
@spec_state_test
def test_gossip_beacon_block__valid_max_bls_to_execution_changes(spec, state):
    """A block with the maximum number of BLS to execution changes is valid."""

    def mutate(spec, block):
        block.body.bls_to_execution_changes = make_progressive_list(
            spec, spec.SignedBLSToExecutionChange, int(spec.MAX_BLS_TO_EXECUTION_CHANGES)
        )

    yield from _assert_beacon_block_gossip(spec, state, mutate, "valid")


@with_gloas_and_later
@spec_state_test
def test_gossip_beacon_block__reject_too_many_bls_to_execution_changes(spec, state):
    """A block with more BLS to execution changes than the limit is rejected."""

    def mutate(spec, block):
        block.body.bls_to_execution_changes = make_progressive_list(
            spec, spec.SignedBLSToExecutionChange, int(spec.MAX_BLS_TO_EXECUTION_CHANGES) + 1
        )

    yield from _assert_beacon_block_gossip(
        spec, state, mutate, "reject", "too many bls to execution changes"
    )


@with_gloas_and_later
@spec_state_test
def test_gossip_beacon_block__valid_max_payload_attestations(spec, state):
    """A block with the maximum number of payload attestations is valid."""

    def mutate(spec, block):
        block.body.payload_attestations = make_progressive_list(
            spec, spec.PayloadAttestation, int(spec.MAX_PAYLOAD_ATTESTATIONS)
        )

    yield from _assert_beacon_block_gossip(spec, state, mutate, "valid")


@with_gloas_and_later
@spec_state_test
def test_gossip_beacon_block__reject_too_many_payload_attestations(spec, state):
    """A block with more payload attestations than the limit is rejected."""

    def mutate(spec, block):
        block.body.payload_attestations = make_progressive_list(
            spec, spec.PayloadAttestation, int(spec.MAX_PAYLOAD_ATTESTATIONS) + 1
        )

    yield from _assert_beacon_block_gossip(
        spec, state, mutate, "reject", "too many payload attestations"
    )
