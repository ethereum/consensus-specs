from eth_consensus_specs.test.context import (
    spec_state_test,
    with_gloas_and_later,
)
from eth_consensus_specs.test.helpers.block import build_empty_block_for_next_slot
from eth_consensus_specs.test.helpers.execution_payload import (
    build_execution_payload_envelope,
    build_signed_execution_payload_envelope,
    commit_bid_to_execution_payload,
    compute_el_block_hash_for_envelope,
    sign_execution_payload_envelope,
)
from eth_consensus_specs.test.helpers.fork_choice import (
    get_genesis_forkchoice_store_and_block,
)
from eth_consensus_specs.test.helpers.gossip import (
    get_filename,
    get_seen,
    run_validate_gossip,
    setup_store_with_failed_block,
    wrap_genesis_block,
)
from eth_consensus_specs.test.helpers.state import state_transition_and_sign_block
from eth_consensus_specs.test.helpers.withdrawals import set_validator_partially_withdrawable


def setup_store_with_block(spec, state, execution_requests=None, update_envelope=None):
    """
    Apply one block to the genesis store and build its envelope. Returns store,
    blocks, signed_envelope.
    """
    store, anchor_block = get_genesis_forkchoice_store_and_block(spec, state)
    signed_anchor = wrap_genesis_block(spec, anchor_block)
    block = build_empty_block_for_next_slot(spec, state)
    if execution_requests is not None:
        block.body.signed_execution_payload_bid.message.execution_requests_root = (
            execution_requests.hash_tree_root()
        )
    commit_bid_to_execution_payload(spec, state, block, execution_requests, update_envelope)
    signed_block = state_transition_and_sign_block(spec, state, block)
    block_root = signed_block.message.hash_tree_root()
    store.blocks[block_root] = signed_block.message
    store.block_states[block_root] = state.copy()

    envelope = build_execution_payload_envelope(
        spec, state, block_root, signed_block.message, execution_requests
    )
    if update_envelope is not None:
        update_envelope(envelope)
    signed_envelope = sign_execution_payload_envelope(spec, state, signed_block, envelope)
    return store, [signed_anchor, signed_block], signed_envelope


@with_gloas_and_later
@spec_state_test
def test_gossip_execution_payload_envelope__valid(spec, state):
    """A well-formed envelope for a known block passes gossip validation."""
    anchor_state = state.copy()
    yield "topic", "meta", "execution_payload"

    store, blocks, signed_envelope = setup_store_with_block(spec, state)
    yield "state", anchor_state
    for signed in blocks:
        yield get_filename(signed), signed
    yield "blocks", "meta", [{"block": get_filename(b)} for b in blocks]

    seen = get_seen(spec)
    yield get_filename(signed_envelope), signed_envelope

    messages = []

    result, reason = run_validate_gossip(
        spec, seen=seen, store=store, signed_execution_payload_envelope=signed_envelope
    )
    assert result == "valid"
    assert reason is None
    messages.append(
        {
            "message": get_filename(signed_envelope),
            "expected": result,
        }
    )

    yield "messages", "meta", messages


@with_gloas_and_later
@spec_state_test
def test_gossip_execution_payload_envelope__ignore_block_unseen(spec, state):
    """An envelope referencing an unknown beacon block is ignored."""
    anchor_state = state.copy()
    yield "topic", "meta", "execution_payload"

    store, blocks, _ = setup_store_with_block(spec, state)
    yield "state", anchor_state
    for signed in blocks:
        yield get_filename(signed), signed
    yield "blocks", "meta", [{"block": get_filename(b)} for b in blocks]

    seen = get_seen(spec)
    # Build the envelope already targeting a block root that is not in the
    # store, so its signature stays valid over the final message and the only
    # failing condition is the unseen block (order-independent).
    unknown_root = spec.Root(b"\xab" * 32)
    signed_envelope = build_signed_execution_payload_envelope(spec, state, unknown_root, blocks[-1])
    yield get_filename(signed_envelope), signed_envelope

    messages = []

    result, reason = run_validate_gossip(
        spec, seen=seen, store=store, signed_execution_payload_envelope=signed_envelope
    )
    assert result == "ignore"
    assert reason == "envelope's block has not been seen"
    messages.append(
        {
            "message": get_filename(signed_envelope),
            "expected": result,
            "reason": reason,
        }
    )

    yield "messages", "meta", messages


@with_gloas_and_later
@spec_state_test
def test_gossip_execution_payload_envelope__ignore_duplicate(spec, state):
    """The second valid envelope for the same (block_root, builder) is ignored."""
    anchor_state = state.copy()
    yield "topic", "meta", "execution_payload"

    store, blocks, signed_envelope = setup_store_with_block(spec, state)
    yield "state", anchor_state
    for signed in blocks:
        yield get_filename(signed), signed
    yield "blocks", "meta", [{"block": get_filename(b)} for b in blocks]

    seen = get_seen(spec)
    yield get_filename(signed_envelope), signed_envelope

    messages = []

    result, reason = run_validate_gossip(
        spec, seen=seen, store=store, signed_execution_payload_envelope=signed_envelope
    )
    assert result == "valid"
    assert reason is None
    messages.append(
        {
            "message": get_filename(signed_envelope),
            "expected": result,
        }
    )

    result, reason = run_validate_gossip(
        spec, seen=seen, store=store, signed_execution_payload_envelope=signed_envelope
    )
    assert result == "ignore"
    assert reason == "already seen envelope for this block root from this builder"
    messages.append(
        {
            "message": get_filename(signed_envelope),
            "expected": result,
            "reason": reason,
        }
    )

    yield "messages", "meta", messages


@with_gloas_and_later
@spec_state_test
def test_gossip_execution_payload_envelope__reject_slot_mismatch(spec, state):
    """An envelope whose payload.slot_number does not match block.slot is rejected."""
    anchor_state = state.copy()
    yield "topic", "meta", "execution_payload"

    def update_envelope(envelope):
        envelope.payload.slot_number += 1

    store, blocks, signed_envelope = setup_store_with_block(
        spec, state, update_envelope=update_envelope
    )
    yield "state", anchor_state
    for signed in blocks:
        yield get_filename(signed), signed
    yield "blocks", "meta", [{"block": get_filename(b)} for b in blocks]

    seen = get_seen(spec)
    yield get_filename(signed_envelope), signed_envelope

    messages = []

    result, reason = run_validate_gossip(
        spec, seen=seen, store=store, signed_execution_payload_envelope=signed_envelope
    )
    assert result == "reject"
    assert reason == "block's slot does not match payload's slot number"
    messages.append(
        {
            "message": get_filename(signed_envelope),
            "expected": result,
            "reason": reason,
        }
    )

    yield "messages", "meta", messages


@with_gloas_and_later
@spec_state_test
def test_gossip_execution_payload_envelope__reject_block_hash_mismatch(spec, state):
    """An envelope whose payload.block_hash does not match the bid is rejected."""
    anchor_state = state.copy()
    yield "topic", "meta", "execution_payload"

    store, blocks, signed_envelope = setup_store_with_block(spec, state)
    yield "state", anchor_state
    for signed in blocks:
        yield get_filename(signed), signed
    yield "blocks", "meta", [{"block": get_filename(b)} for b in blocks]

    seen = get_seen(spec)
    envelope = signed_envelope.message
    envelope.payload.transactions.append(spec.Transaction(data=list(b"\x99" * 128)))
    envelope.payload.block_hash = compute_el_block_hash_for_envelope(spec, envelope)
    signed_envelope = sign_execution_payload_envelope(spec, state, blocks[-1], envelope)
    yield get_filename(signed_envelope), signed_envelope

    messages = []

    result, reason = run_validate_gossip(
        spec, seen=seen, store=store, signed_execution_payload_envelope=signed_envelope
    )
    assert result == "reject"
    assert reason == "payload's block hash does not match the bid's block hash"
    messages.append(
        {
            "message": get_filename(signed_envelope),
            "expected": result,
            "reason": reason,
        }
    )

    yield "messages", "meta", messages


@with_gloas_and_later
@spec_state_test
def test_gossip_execution_payload_envelope__reject_invalid_signature(spec, state):
    """An envelope with an invalid signature is rejected."""
    anchor_state = state.copy()
    yield "topic", "meta", "execution_payload"

    store, blocks, signed_envelope = setup_store_with_block(spec, state)
    yield "state", anchor_state
    for signed in blocks:
        yield get_filename(signed), signed
    yield "blocks", "meta", [{"block": get_filename(b)} for b in blocks]

    seen = get_seen(spec)
    signed_envelope.signature = spec.BLSSignature()
    yield get_filename(signed_envelope), signed_envelope

    messages = []

    result, reason = run_validate_gossip(
        spec, seen=seen, store=store, signed_execution_payload_envelope=signed_envelope
    )
    assert result == "reject"
    assert reason == "invalid envelope signature"
    messages.append(
        {
            "message": get_filename(signed_envelope),
            "expected": result,
            "reason": reason,
        }
    )

    yield "messages", "meta", messages


@with_gloas_and_later
@spec_state_test
def test_gossip_execution_payload_envelope__ignore_pre_finalized(spec, state):
    """An envelope whose payload slot is before the latest finalized slot is ignored."""
    anchor_state = state.copy()
    yield "topic", "meta", "execution_payload"

    store, blocks, signed_envelope = setup_store_with_block(spec, state)
    block_root = blocks[-1].message.hash_tree_root()
    # Advance the finalized checkpoint past the block's slot so the envelope
    # appears to be from a pre-finalized slot.
    store.finalized_checkpoint = spec.Checkpoint(
        epoch=spec.Epoch(spec.compute_epoch_at_slot(state.slot) + 2),
        root=block_root,
    )
    yield "state", anchor_state
    for signed in blocks:
        yield get_filename(signed), signed
    yield "blocks", "meta", [{"block": get_filename(b)} for b in blocks]
    yield (
        "finalized_checkpoint",
        "meta",
        {
            "epoch": int(store.finalized_checkpoint.epoch),
            "root": "0x" + block_root.hex(),
        },
    )

    seen = get_seen(spec)
    yield get_filename(signed_envelope), signed_envelope

    messages = []

    result, reason = run_validate_gossip(
        spec, seen=seen, store=store, signed_execution_payload_envelope=signed_envelope
    )
    assert result == "ignore"
    assert reason == "envelope is from a slot before the latest finalized slot"
    messages.append(
        {
            "message": get_filename(signed_envelope),
            "expected": result,
            "reason": reason,
        }
    )

    yield "messages", "meta", messages


@with_gloas_and_later
@spec_state_test
def test_gossip_execution_payload_envelope__reject_block_failed_validation(spec, state):
    """An envelope whose block failed validation is rejected."""
    anchor_state = state.copy()
    yield "topic", "meta", "execution_payload"

    block = build_empty_block_for_next_slot(spec, state)
    commit_bid_to_execution_payload(spec, state, block)
    store, signed_anchor, signed_block = setup_store_with_failed_block(spec, state, block=block)
    block_root = signed_block.message.hash_tree_root()
    yield "state", anchor_state
    yield get_filename(signed_anchor), signed_anchor
    yield get_filename(signed_block), signed_block
    yield (
        "blocks",
        "meta",
        [
            {"block": get_filename(signed_anchor)},
            {"block": get_filename(signed_block), "failed": True},
        ],
    )

    seen = get_seen(spec)
    signed_envelope = build_signed_execution_payload_envelope(spec, state, block_root, signed_block)
    yield get_filename(signed_envelope), signed_envelope

    messages = []

    result, reason = run_validate_gossip(
        spec, seen=seen, store=store, signed_execution_payload_envelope=signed_envelope
    )
    assert result == "reject"
    assert reason == "envelope's block failed validation"
    messages.append(
        {
            "message": get_filename(signed_envelope),
            "expected": result,
            "reason": reason,
        }
    )

    yield "messages", "meta", messages


@with_gloas_and_later
@spec_state_test
def test_gossip_execution_payload_envelope__reject_builder_index_mismatch(spec, state):
    """An envelope whose builder_index does not match the bid's builder_index is rejected."""
    anchor_state = state.copy()
    yield "topic", "meta", "execution_payload"

    store, blocks, signed_envelope = setup_store_with_block(spec, state)
    yield "state", anchor_state
    for signed in blocks:
        yield get_filename(signed), signed
    yield "blocks", "meta", [{"block": get_filename(b)} for b in blocks]

    seen = get_seen(spec)
    bid_builder_index = blocks[-1].message.body.signed_execution_payload_bid.message.builder_index
    # Pick any builder index that differs from the bid's. We subtract 1 instead
    # of adding so the value stays inside Uint64 range when the bid uses the
    # max-value sentinel BUILDER_INDEX_SELF_BUILD.
    signed_envelope.message.builder_index = spec.BuilderIndex(int(bid_builder_index) - 1)
    yield get_filename(signed_envelope), signed_envelope

    messages = []

    result, reason = run_validate_gossip(
        spec, seen=seen, store=store, signed_execution_payload_envelope=signed_envelope
    )
    assert result == "reject"
    assert reason == "envelope's builder index does not match the bid's builder index"
    messages.append(
        {
            "message": get_filename(signed_envelope),
            "expected": result,
            "reason": reason,
        }
    )

    yield "messages", "meta", messages


@with_gloas_and_later
@spec_state_test
def test_gossip_execution_payload_envelope__reject_execution_requests_root_mismatch(spec, state):
    """An envelope whose execution_requests root does not match the bid's is rejected."""
    anchor_state = state.copy()
    yield "topic", "meta", "execution_payload"

    store, anchor_block = get_genesis_forkchoice_store_and_block(spec, state)
    signed_anchor = wrap_genesis_block(spec, anchor_block)
    # Use execution_requests with a non-empty deposits list so its root differs
    # from the bid's empty execution_requests_root.
    non_empty_requests = spec.ExecutionRequests(
        deposits=spec.DepositRequests.of(spec.DepositRequest())
    )
    block = build_empty_block_for_next_slot(spec, state)
    commit_bid_to_execution_payload(spec, state, block, non_empty_requests)
    signed_block = state_transition_and_sign_block(spec, state, block)
    block_root = signed_block.message.hash_tree_root()
    store.blocks[block_root] = signed_block.message
    store.block_states[block_root] = state.copy()
    blocks = [signed_anchor, signed_block]

    yield "state", anchor_state
    for signed in blocks:
        yield get_filename(signed), signed
    yield "blocks", "meta", [{"block": get_filename(b)} for b in blocks]

    seen = get_seen(spec)
    signed_envelope = build_signed_execution_payload_envelope(
        spec, state, block_root, signed_block, execution_requests=non_empty_requests
    )
    yield get_filename(signed_envelope), signed_envelope

    messages = []

    result, reason = run_validate_gossip(
        spec, seen=seen, store=store, signed_execution_payload_envelope=signed_envelope
    )
    assert result == "reject"
    assert reason == "envelope's execution requests root does not match the bid's"
    messages.append(
        {
            "message": get_filename(signed_envelope),
            "expected": result,
            "reason": reason,
        }
    )

    yield "messages", "meta", messages


def _assert_envelope_requests(spec, state, execution_requests, expected, reason=None):
    """Assert an envelope carrying ``execution_requests`` returns ``expected``.

    The block's bid commits to the same requests (set before the state
    transition, so the block is valid and replayable) so that the
    requests-root check passes and the request-count checks are reached.
    """
    anchor_state = state.copy()
    yield "topic", "meta", "execution_payload"

    store, blocks, signed_envelope = setup_store_with_block(
        spec, state, execution_requests=execution_requests
    )
    yield "state", anchor_state
    for signed in blocks:
        yield get_filename(signed), signed
    yield "blocks", "meta", [{"block": get_filename(b)} for b in blocks]

    seen = get_seen(spec)
    yield get_filename(signed_envelope), signed_envelope

    messages = []

    result, reason_out = run_validate_gossip(
        spec, seen=seen, store=store, signed_execution_payload_envelope=signed_envelope
    )
    assert result == expected
    assert reason_out == reason
    message = {
        "message": get_filename(signed_envelope),
        "expected": result,
    }
    if reason is not None:
        message["reason"] = reason
    messages.append(message)

    yield "messages", "meta", messages


def _assert_envelope_withdrawals(spec, state, count, expected, reason=None):
    """
    Assert an envelope whose payload carries ``count`` withdrawals returns
    ``expected``.

    Withdrawals are only processed on top of a full parent, so the block builds
    on the anchor's payload, and its post-state expects the maximum number of
    withdrawals. The payload carries these, followed by default withdrawals up
    to ``count``.
    """
    for index in range(spec.MAX_WITHDRAWALS_PER_PAYLOAD):
        set_validator_partially_withdrawable(spec, state, index)
    anchor_state = state.copy()
    yield "topic", "meta", "execution_payload"

    store, anchor_block = get_genesis_forkchoice_store_and_block(spec, state)
    signed_anchor = wrap_genesis_block(spec, anchor_block)
    anchor_root = anchor_block.hash_tree_root()
    # The anchor's payload has been received and verified, recorded in the
    # store as `on_execution_payload_envelope` would.
    signed_anchor_envelope = build_signed_execution_payload_envelope(
        spec, state, anchor_root, signed_anchor
    )
    store.payloads[anchor_root] = signed_anchor_envelope.message

    block = build_empty_block_for_next_slot(spec, state)
    # Claim the parent is full by matching the bid's parent_block_hash to the
    # parent bid's block_hash. The bid's block_hash must differ from it.
    bid = block.body.signed_execution_payload_bid.message
    bid.parent_block_hash = anchor_block.body.signed_execution_payload_bid.message.block_hash
    bid.block_hash = spec.Hash32(b"\x42" * 32)

    def update_envelope(envelope):
        withdrawals = list(envelope.payload.withdrawals)
        withdrawals += [spec.Withdrawal()] * (count - len(withdrawals))
        envelope.payload.withdrawals = spec.Withdrawals(data=withdrawals)

    commit_bid_to_execution_payload(spec, state, block, update_envelope=update_envelope)
    signed_block = state_transition_and_sign_block(spec, state, block)
    block_root = signed_block.message.hash_tree_root()
    store.blocks[block_root] = signed_block.message
    store.block_states[block_root] = state.copy()
    assert len(state.payload_expected_withdrawals) == spec.MAX_WITHDRAWALS_PER_PAYLOAD

    yield "state", anchor_state
    yield get_filename(signed_anchor), signed_anchor
    yield get_filename(signed_anchor_envelope), signed_anchor_envelope
    yield get_filename(signed_block), signed_block
    yield (
        "blocks",
        "meta",
        [
            {
                "block": get_filename(signed_anchor),
                "payload": get_filename(signed_anchor_envelope),
            },
            {"block": get_filename(signed_block)},
        ],
    )

    seen = get_seen(spec)
    envelope = build_execution_payload_envelope(spec, state, block_root, signed_block.message)
    update_envelope(envelope)
    signed_envelope = sign_execution_payload_envelope(spec, state, signed_block, envelope)
    yield get_filename(signed_envelope), signed_envelope

    messages = []

    result, reason_out = run_validate_gossip(
        spec, seen=seen, store=store, signed_execution_payload_envelope=signed_envelope
    )
    assert result == expected
    assert reason_out == reason
    message = {
        "message": get_filename(signed_envelope),
        "expected": result,
    }
    if reason is not None:
        message["reason"] = reason
    messages.append(message)

    yield "messages", "meta", messages


@with_gloas_and_later
@spec_state_test
def test_gossip_execution_payload_envelope__valid_max_withdrawal_requests(spec, state):
    """An envelope with the maximum number of withdrawal requests is valid."""
    count = spec.MAX_WITHDRAWAL_REQUESTS_PER_PAYLOAD
    requests = spec.ExecutionRequests(
        withdrawals=spec.WithdrawalRequests(data=([spec.WithdrawalRequest()] * count))
    )
    yield from _assert_envelope_requests(spec, state, requests, "valid")


@with_gloas_and_later
@spec_state_test
def test_gossip_execution_payload_envelope__reject_too_many_withdrawal_requests(spec, state):
    """An envelope whose execution requests exceed the withdrawal-request limit is rejected."""
    count = spec.MAX_WITHDRAWAL_REQUESTS_PER_PAYLOAD + 1
    requests = spec.ExecutionRequests(
        withdrawals=spec.WithdrawalRequests(data=([spec.WithdrawalRequest()] * count))
    )
    yield from _assert_envelope_requests(
        spec, state, requests, "reject", "too many withdrawal requests"
    )


@with_gloas_and_later
@spec_state_test
def test_gossip_execution_payload_envelope__valid_max_consolidation_requests(spec, state):
    """An envelope with the maximum number of consolidation requests is valid."""
    count = spec.MAX_CONSOLIDATION_REQUESTS_PER_PAYLOAD
    requests = spec.ExecutionRequests(
        consolidations=spec.ConsolidationRequests(data=([spec.ConsolidationRequest()] * count))
    )
    yield from _assert_envelope_requests(spec, state, requests, "valid")


@with_gloas_and_later
@spec_state_test
def test_gossip_execution_payload_envelope__reject_too_many_consolidation_requests(spec, state):
    """An envelope whose execution requests exceed the consolidation-request limit is rejected."""
    count = spec.MAX_CONSOLIDATION_REQUESTS_PER_PAYLOAD + 1
    requests = spec.ExecutionRequests(
        consolidations=spec.ConsolidationRequests(data=([spec.ConsolidationRequest()] * count))
    )
    yield from _assert_envelope_requests(
        spec, state, requests, "reject", "too many consolidation requests"
    )


@with_gloas_and_later
@spec_state_test
def test_gossip_execution_payload_envelope__valid_max_builder_deposit_requests(spec, state):
    """An envelope with the maximum number of builder deposit requests is valid."""
    count = spec.MAX_BUILDER_DEPOSIT_REQUESTS_PER_PAYLOAD
    requests = spec.ExecutionRequests(
        builder_deposits=spec.BuilderDepositRequests(data=([spec.BuilderDepositRequest()] * count))
    )
    yield from _assert_envelope_requests(spec, state, requests, "valid")


@with_gloas_and_later
@spec_state_test
def test_gossip_execution_payload_envelope__reject_too_many_builder_deposit_requests(spec, state):
    """An envelope whose execution requests exceed the builder-deposit-request limit is rejected."""
    count = spec.MAX_BUILDER_DEPOSIT_REQUESTS_PER_PAYLOAD + 1
    requests = spec.ExecutionRequests(
        builder_deposits=spec.BuilderDepositRequests(data=([spec.BuilderDepositRequest()] * count))
    )
    yield from _assert_envelope_requests(
        spec, state, requests, "reject", "too many builder deposit requests"
    )


@with_gloas_and_later
@spec_state_test
def test_gossip_execution_payload_envelope__valid_max_builder_exit_requests(spec, state):
    """An envelope with the maximum number of builder exit requests is valid."""
    count = spec.MAX_BUILDER_EXIT_REQUESTS_PER_PAYLOAD
    requests = spec.ExecutionRequests(
        builder_exits=spec.BuilderExitRequests(data=([spec.BuilderExitRequest()] * count))
    )
    yield from _assert_envelope_requests(spec, state, requests, "valid")


@with_gloas_and_later
@spec_state_test
def test_gossip_execution_payload_envelope__reject_too_many_builder_exit_requests(spec, state):
    """An envelope whose execution requests exceed the builder-exit-request limit is rejected."""
    count = spec.MAX_BUILDER_EXIT_REQUESTS_PER_PAYLOAD + 1
    requests = spec.ExecutionRequests(
        builder_exits=spec.BuilderExitRequests(data=([spec.BuilderExitRequest()] * count))
    )
    yield from _assert_envelope_requests(
        spec, state, requests, "reject", "too many builder exit requests"
    )


@with_gloas_and_later
@spec_state_test
def test_gossip_execution_payload_envelope__valid_max_withdrawals(spec, state):
    """An envelope with the maximum number of payload withdrawals is valid."""
    count = spec.MAX_WITHDRAWALS_PER_PAYLOAD
    yield from _assert_envelope_withdrawals(spec, state, count, "valid")


@with_gloas_and_later
@spec_state_test
def test_gossip_execution_payload_envelope__reject_too_many_withdrawals(spec, state):
    """An envelope whose payload carries more withdrawals than the limit is rejected."""
    count = spec.MAX_WITHDRAWALS_PER_PAYLOAD + 1
    yield from _assert_envelope_withdrawals(spec, state, count, "reject", "too many withdrawals")


def _assert_envelope_rejected(spec, state, update_envelope, reason):
    """
    Assert an envelope changed by ``update_envelope`` is rejected with ``reason``.

    The block's bid commits to the block hash of the changed payload, so that
    the condition under test is the only one which fails.
    """
    anchor_state = state.copy()
    yield "topic", "meta", "execution_payload"

    store, blocks, signed_envelope = setup_store_with_block(
        spec, state, update_envelope=update_envelope
    )
    yield "state", anchor_state
    for signed in blocks:
        yield get_filename(signed), signed
    yield "blocks", "meta", [{"block": get_filename(b)} for b in blocks]

    seen = get_seen(spec)
    yield get_filename(signed_envelope), signed_envelope

    messages = []

    result, reason_out = run_validate_gossip(
        spec, seen=seen, store=store, signed_execution_payload_envelope=signed_envelope
    )
    assert result == "reject"
    assert reason_out == reason
    messages.append(
        {
            "message": get_filename(signed_envelope),
            "expected": result,
            "reason": reason,
        }
    )

    yield "messages", "meta", messages


@with_gloas_and_later
@spec_state_test
def test_gossip_execution_payload_envelope__reject_parent_beacon_block_root_mismatch(spec, state):
    """An envelope whose parent_beacon_block_root is not the block's parent root is rejected."""

    def update_envelope(envelope):
        envelope.parent_beacon_block_root = spec.Root(b"\xab" * 32)

    yield from _assert_envelope_rejected(
        spec,
        state,
        update_envelope,
        "envelope's parent beacon block root does not match the block's",
    )


@with_gloas_and_later
@spec_state_test
def test_gossip_execution_payload_envelope__reject_prev_randao_mismatch(spec, state):
    """An envelope whose payload.prev_randao does not match the bid's is rejected."""

    def update_envelope(envelope):
        envelope.payload.prev_randao = spec.Bytes32(b"\xab" * 32)

    yield from _assert_envelope_rejected(
        spec,
        state,
        update_envelope,
        "payload's previous randao does not match the bid's previous randao",
    )


@with_gloas_and_later
@spec_state_test
def test_gossip_execution_payload_envelope__reject_gas_limit_mismatch(spec, state):
    """An envelope whose payload.gas_limit does not match the bid's is rejected."""

    def update_envelope(envelope):
        envelope.payload.gas_limit += 1

    yield from _assert_envelope_rejected(
        spec,
        state,
        update_envelope,
        "payload's gas limit does not match the bid's gas limit",
    )


@with_gloas_and_later
@spec_state_test
def test_gossip_execution_payload_envelope__reject_parent_hash_mismatch(spec, state):
    """An envelope whose payload.parent_hash is not the latest block hash is rejected."""

    def update_envelope(envelope):
        envelope.payload.parent_hash = spec.Hash32(b"\xab" * 32)

    yield from _assert_envelope_rejected(
        spec,
        state,
        update_envelope,
        "payload's parent hash does not match the latest block hash",
    )


@with_gloas_and_later
@spec_state_test
def test_gossip_execution_payload_envelope__reject_incorrect_timestamp(spec, state):
    """An envelope whose payload.timestamp is not the time of the block's slot is rejected."""

    def update_envelope(envelope):
        envelope.payload.timestamp += 1

    yield from _assert_envelope_rejected(
        spec,
        state,
        update_envelope,
        "incorrect execution payload timestamp",
    )


@with_gloas_and_later
@spec_state_test
def test_gossip_execution_payload_envelope__reject_empty_transaction(spec, state):
    """An envelope whose payload contains an empty transaction is rejected."""

    def update_envelope(envelope):
        envelope.payload.transactions.append(spec.Transaction(data=list(b"\x99" * 128)))
        envelope.payload.transactions.append(spec.Transaction())

    yield from _assert_envelope_rejected(
        spec,
        state,
        update_envelope,
        "payload contains an empty transaction",
    )


@with_gloas_and_later
@spec_state_test
def test_gossip_execution_payload_envelope__reject_withdrawals_mismatch(spec, state):
    """An envelope whose payload.withdrawals are not the expected withdrawals is rejected."""

    def update_envelope(envelope):
        envelope.payload.withdrawals.append(spec.Withdrawal())

    yield from _assert_envelope_rejected(
        spec,
        state,
        update_envelope,
        "payload's withdrawals do not match the expected withdrawals",
    )


@with_gloas_and_later
@spec_state_test
def test_gossip_execution_payload_envelope__reject_invalid_block_hash(spec, state):
    """An envelope whose payload.block_hash is not computed correctly is rejected."""
    anchor_state = state.copy()
    yield "topic", "meta", "execution_payload"

    store, blocks, signed_envelope = setup_store_with_block(spec, state)
    yield "state", anchor_state
    for signed in blocks:
        yield get_filename(signed), signed
    yield "blocks", "meta", [{"block": get_filename(b)} for b in blocks]

    seen = get_seen(spec)
    envelope = signed_envelope.message
    envelope.payload.transactions.append(spec.Transaction(data=list(b"\x99" * 128)))
    signed_envelope = sign_execution_payload_envelope(spec, state, blocks[-1], envelope)
    yield get_filename(signed_envelope), signed_envelope

    messages = []

    result, reason = run_validate_gossip(
        spec, seen=seen, store=store, signed_execution_payload_envelope=signed_envelope
    )
    assert result == "reject"
    assert reason == "payload's block hash is not computed correctly"
    messages.append(
        {
            "message": get_filename(signed_envelope),
            "expected": result,
            "reason": reason,
        }
    )

    yield "messages", "meta", messages
