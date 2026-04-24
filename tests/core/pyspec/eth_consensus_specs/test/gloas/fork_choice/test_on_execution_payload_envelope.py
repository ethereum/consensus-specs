from eth_consensus_specs.test.context import (
    spec_state_test,
    with_gloas_and_later,
)
from eth_consensus_specs.test.helpers.block import (
    build_empty_block_for_next_slot,
)
from eth_consensus_specs.test.helpers.execution_payload import (
    build_empty_execution_payload,
    build_signed_execution_payload_envelope,
)
from eth_consensus_specs.test.helpers.fork_choice import (
    add_execution_payload,
    check_head_against_root,
    get_anchor_root,
    get_genesis_forkchoice_store_and_block,
    on_tick_and_append_step,
    tick_and_add_block,
)
from eth_consensus_specs.test.helpers.keys import builder_privkeys, privkeys
from eth_consensus_specs.test.helpers.state import (
    state_transition_and_sign_block,
)


def _add_block_and_get_root(spec, state, store, test_steps):
    """Add a block to the store and return (signed_block, block_root)."""
    block = build_empty_block_for_next_slot(spec, state)
    signed_block = state_transition_and_sign_block(spec, state, block)
    yield from tick_and_add_block(spec, store, signed_block, test_steps)
    block_root = signed_block.message.hash_tree_root()
    return signed_block, block_root


def _build_invalid_envelope(spec, state, block_root, signed_block, **overrides):
    """Build a signed envelope with optional field overrides to make it invalid."""
    builder_index = signed_block.message.body.signed_execution_payload_bid.message.builder_index
    bid = state.latest_execution_payload_bid

    payload = build_empty_execution_payload(spec, state)
    payload.block_hash = bid.block_hash
    payload.gas_limit = bid.gas_limit
    payload.parent_hash = state.latest_block_hash

    # Apply payload-level overrides
    for key in (
        "block_hash",
        "gas_limit",
        "parent_hash",
        "prev_randao",
        "slot_number",
        "timestamp",
        "withdrawals",
    ):
        if key in overrides:
            setattr(payload, key, overrides.pop(key))

    envelope = spec.ExecutionPayloadEnvelope(
        beacon_block_root=overrides.pop("beacon_block_root", block_root),
        payload=payload,
        execution_requests=overrides.pop("execution_requests", spec.ExecutionRequests()),
        builder_index=overrides.pop("builder_index", builder_index),
    )

    if overrides.pop("valid_signature", True):
        if envelope.builder_index == spec.BUILDER_INDEX_SELF_BUILD:
            privkey = privkeys[signed_block.message.proposer_index]
        else:
            privkey = builder_privkeys[envelope.builder_index]
        signature = spec.get_execution_payload_envelope_signature(state, envelope, privkey)
    else:
        signature = spec.BLSSignature()

    return spec.SignedExecutionPayloadEnvelope(message=envelope, signature=signature)


#
# Valid cases
#


@with_gloas_and_later
@spec_state_test
def test_on_execution_payload_envelope__valid(spec, state):
    test_steps = []

    # Initialization
    store, anchor_block = get_genesis_forkchoice_store_and_block(spec, state)
    yield "anchor_state", state
    yield "anchor_block", anchor_block

    current_time = state.slot * (spec.config.SLOT_DURATION_MS // 1000) + store.genesis_time
    on_tick_and_append_step(spec, store, current_time, test_steps)

    anchor_root = get_anchor_root(spec, state)
    check_head_against_root(spec, store, anchor_root)

    # Genesis head has EMPTY payload status (no envelope in store.payloads)
    head = spec.get_head(store)
    assert head.payload_status == spec.PAYLOAD_STATUS_EMPTY

    # On receiving a block of `GENESIS_SLOT + 1` slot
    signed_block, block_root = yield from _add_block_and_get_root(spec, state, store, test_steps)

    # Verify block was added to store
    assert block_root in store.blocks
    assert block_root in store.block_states
    assert block_root in store.payload_timeliness_vote

    # Head is the new block with EMPTY status
    check_head_against_root(spec, store, block_root)
    head = spec.get_head(store)
    assert head.payload_status == spec.PAYLOAD_STATUS_EMPTY

    # Builder reveals execution payload
    envelope = build_signed_execution_payload_envelope(spec, state, block_root, signed_block)
    yield from add_execution_payload(spec, store, envelope, test_steps, valid=True)

    # Block root should now be stored in payloads after payload reveal
    assert block_root in store.payloads
    head = spec.get_head(store)
    assert head.payload_status == spec.PAYLOAD_STATUS_FULL

    # On receiving a block of next slot, chain continues after payload reveal
    _, block_2_root = yield from _add_block_and_get_root(spec, state, store, test_steps)
    check_head_against_root(spec, store, block_2_root)

    # Head moved to block 2 with EMPTY status
    head = spec.get_head(store)
    assert head.payload_status == spec.PAYLOAD_STATUS_EMPTY

    yield "steps", test_steps


#
# Invalid cases — ordered to match asserts in verify_execution_payload_envelope
#


@with_gloas_and_later
@spec_state_test
def test_on_execution_payload_envelope__wrong_signature(spec, state):
    test_steps = []
    store, anchor_block = get_genesis_forkchoice_store_and_block(spec, state)
    yield "anchor_state", state
    yield "anchor_block", anchor_block

    current_time = state.slot * (spec.config.SLOT_DURATION_MS // 1000) + store.genesis_time
    on_tick_and_append_step(spec, store, current_time, test_steps)

    signed_block, block_root = yield from _add_block_and_get_root(spec, state, store, test_steps)

    envelope = _build_invalid_envelope(
        spec,
        state,
        block_root,
        signed_block,
        valid_signature=False,
    )
    yield from add_execution_payload(spec, store, envelope, test_steps, valid=False)

    assert block_root not in store.payloads

    yield "steps", test_steps


@with_gloas_and_later
@spec_state_test
def test_on_execution_payload_envelope__wrong_beacon_block_root(spec, state):
    test_steps = []
    store, anchor_block = get_genesis_forkchoice_store_and_block(spec, state)
    yield "anchor_state", state
    yield "anchor_block", anchor_block

    current_time = state.slot * (spec.config.SLOT_DURATION_MS // 1000) + store.genesis_time
    on_tick_and_append_step(spec, store, current_time, test_steps)

    signed_block, block_root = yield from _add_block_and_get_root(spec, state, store, test_steps)

    envelope = _build_invalid_envelope(
        spec,
        state,
        block_root,
        signed_block,
        beacon_block_root=spec.Root(b"\x42" * 32),
    )
    yield from add_execution_payload(spec, store, envelope, test_steps, valid=False)

    assert block_root not in store.payloads

    yield "steps", test_steps


@with_gloas_and_later
@spec_state_test
def test_on_execution_payload_envelope__wrong_slot(spec, state):
    test_steps = []
    store, anchor_block = get_genesis_forkchoice_store_and_block(spec, state)
    yield "anchor_state", state
    yield "anchor_block", anchor_block

    current_time = state.slot * (spec.config.SLOT_DURATION_MS // 1000) + store.genesis_time
    on_tick_and_append_step(spec, store, current_time, test_steps)

    signed_block, block_root = yield from _add_block_and_get_root(spec, state, store, test_steps)

    envelope = _build_invalid_envelope(
        spec,
        state,
        block_root,
        signed_block,
        slot_number=state.slot + 1,
    )
    yield from add_execution_payload(spec, store, envelope, test_steps, valid=False)

    assert block_root not in store.payloads

    yield "steps", test_steps


@with_gloas_and_later
@spec_state_test
def test_on_execution_payload_envelope__wrong_builder_index(spec, state):
    test_steps = []
    store, anchor_block = get_genesis_forkchoice_store_and_block(spec, state)
    yield "anchor_state", state
    yield "anchor_block", anchor_block

    current_time = state.slot * (spec.config.SLOT_DURATION_MS // 1000) + store.genesis_time
    on_tick_and_append_step(spec, store, current_time, test_steps)

    signed_block, block_root = yield from _add_block_and_get_root(spec, state, store, test_steps)

    envelope = _build_invalid_envelope(
        spec,
        state,
        block_root,
        signed_block,
        builder_index=1,
    )
    yield from add_execution_payload(spec, store, envelope, test_steps, valid=False)

    assert block_root not in store.payloads

    yield "steps", test_steps


@with_gloas_and_later
@spec_state_test
def test_on_execution_payload_envelope__wrong_prev_randao(spec, state):
    test_steps = []
    store, anchor_block = get_genesis_forkchoice_store_and_block(spec, state)
    yield "anchor_state", state
    yield "anchor_block", anchor_block

    current_time = state.slot * (spec.config.SLOT_DURATION_MS // 1000) + store.genesis_time
    on_tick_and_append_step(spec, store, current_time, test_steps)

    signed_block, block_root = yield from _add_block_and_get_root(spec, state, store, test_steps)

    envelope = _build_invalid_envelope(
        spec,
        state,
        block_root,
        signed_block,
        prev_randao=spec.Bytes32(b"\x42" * 32),
    )
    yield from add_execution_payload(spec, store, envelope, test_steps, valid=False)

    assert block_root not in store.payloads

    yield "steps", test_steps


@with_gloas_and_later
@spec_state_test
def test_on_execution_payload_envelope__wrong_execution_requests_root(spec, state):
    test_steps = []
    store, anchor_block = get_genesis_forkchoice_store_and_block(spec, state)
    yield "anchor_state", state
    yield "anchor_block", anchor_block

    current_time = state.slot * (spec.config.SLOT_DURATION_MS // 1000) + store.genesis_time
    on_tick_and_append_step(spec, store, current_time, test_steps)

    signed_block, block_root = yield from _add_block_and_get_root(spec, state, store, test_steps)

    # Build envelope with non-empty requests but bid commits to empty requests
    non_empty_requests = spec.ExecutionRequests(
        deposits=spec.List[spec.DepositRequest, spec.MAX_DEPOSIT_REQUESTS_PER_PAYLOAD](
            [
                spec.DepositRequest(
                    pubkey=spec.BLSPubkey(b"\x01" * 48),
                    withdrawal_credentials=spec.Bytes32(b"\x02" * 32),
                    amount=spec.Gwei(32000000000),
                    signature=spec.BLSSignature(b"\x03" * 96),
                    index=spec.uint64(0),
                )
            ]
        ),
        withdrawals=spec.List[spec.WithdrawalRequest, spec.MAX_WITHDRAWAL_REQUESTS_PER_PAYLOAD](),
        consolidations=spec.List[
            spec.ConsolidationRequest, spec.MAX_CONSOLIDATION_REQUESTS_PER_PAYLOAD
        ](),
    )

    envelope = _build_invalid_envelope(
        spec,
        state,
        block_root,
        signed_block,
        execution_requests=non_empty_requests,
    )
    yield from add_execution_payload(spec, store, envelope, test_steps, valid=False)

    assert block_root not in store.payloads

    yield "steps", test_steps


@with_gloas_and_later
@spec_state_test
def test_on_execution_payload_envelope__wrong_withdrawals(spec, state):
    test_steps = []
    store, anchor_block = get_genesis_forkchoice_store_and_block(spec, state)
    yield "anchor_state", state
    yield "anchor_block", anchor_block

    current_time = state.slot * (spec.config.SLOT_DURATION_MS // 1000) + store.genesis_time
    on_tick_and_append_step(spec, store, current_time, test_steps)

    signed_block, block_root = yield from _add_block_and_get_root(spec, state, store, test_steps)

    # Build envelope with a non-empty withdrawal that won't match the state's
    # empty payload_expected_withdrawals
    wrong_withdrawal = spec.Withdrawal(
        index=0, validator_index=0, address=b"\x22" * 20, amount=spec.Gwei(1)
    )
    envelope = _build_invalid_envelope(
        spec,
        state,
        block_root,
        signed_block,
        withdrawals=spec.List[spec.Withdrawal, spec.MAX_WITHDRAWALS_PER_PAYLOAD](
            [wrong_withdrawal]
        ),
    )
    yield from add_execution_payload(spec, store, envelope, test_steps, valid=False)

    assert block_root not in store.payloads

    yield "steps", test_steps


@with_gloas_and_later
@spec_state_test
def test_on_execution_payload_envelope__missing_expected_withdrawal(spec, state):
    """
    Envelope with empty withdrawals must be rejected when the state's
    payload_expected_withdrawals is non-empty.
    """
    # Seed payload_expected_withdrawals directly on the anchor state. The parent
    # is genesis (empty), so process_withdrawals returns early in block_1 and
    # the seeded value carries through unchanged.
    expected_withdrawal = spec.Withdrawal(
        index=0, validator_index=0, address=b"\x22" * 20, amount=spec.Gwei(1)
    )
    state.payload_expected_withdrawals = spec.List[
        spec.Withdrawal, spec.MAX_WITHDRAWALS_PER_PAYLOAD
    ]([expected_withdrawal])

    test_steps = []
    store, anchor_block = get_genesis_forkchoice_store_and_block(spec, state)
    yield "anchor_state", state
    yield "anchor_block", anchor_block

    current_time = state.slot * (spec.config.SLOT_DURATION_MS // 1000) + store.genesis_time
    on_tick_and_append_step(spec, store, current_time, test_steps)

    signed_block, block_root = yield from _add_block_and_get_root(spec, state, store, test_steps)

    # Sanity check: the seeded expected withdrawal survived block_1.
    assert len(state.payload_expected_withdrawals) == 1

    # Build envelope with empty withdrawals, omitting the expected one.
    envelope = _build_invalid_envelope(
        spec,
        state,
        block_root,
        signed_block,
        withdrawals=spec.List[spec.Withdrawal, spec.MAX_WITHDRAWALS_PER_PAYLOAD](),
    )
    yield from add_execution_payload(spec, store, envelope, test_steps, valid=False)

    assert block_root not in store.payloads

    yield "steps", test_steps


@with_gloas_and_later
@spec_state_test
def test_on_execution_payload_envelope__wrong_gas_limit(spec, state):
    test_steps = []
    store, anchor_block = get_genesis_forkchoice_store_and_block(spec, state)
    yield "anchor_state", state
    yield "anchor_block", anchor_block

    current_time = state.slot * (spec.config.SLOT_DURATION_MS // 1000) + store.genesis_time
    on_tick_and_append_step(spec, store, current_time, test_steps)

    signed_block, block_root = yield from _add_block_and_get_root(spec, state, store, test_steps)

    envelope = _build_invalid_envelope(
        spec,
        state,
        block_root,
        signed_block,
        gas_limit=state.latest_execution_payload_bid.gas_limit + 1,
    )
    yield from add_execution_payload(spec, store, envelope, test_steps, valid=False)

    assert block_root not in store.payloads

    yield "steps", test_steps


@with_gloas_and_later
@spec_state_test
def test_on_execution_payload_envelope__wrong_block_hash(spec, state):
    test_steps = []
    store, anchor_block = get_genesis_forkchoice_store_and_block(spec, state)
    yield "anchor_state", state
    yield "anchor_block", anchor_block

    current_time = state.slot * (spec.config.SLOT_DURATION_MS // 1000) + store.genesis_time
    on_tick_and_append_step(spec, store, current_time, test_steps)

    signed_block, block_root = yield from _add_block_and_get_root(spec, state, store, test_steps)

    envelope = _build_invalid_envelope(
        spec,
        state,
        block_root,
        signed_block,
        block_hash=spec.Hash32(b"\x42" * 32),
    )
    yield from add_execution_payload(spec, store, envelope, test_steps, valid=False)

    assert block_root not in store.payloads

    yield "steps", test_steps


@with_gloas_and_later
@spec_state_test
def test_on_execution_payload_envelope__wrong_parent_hash(spec, state):
    test_steps = []
    store, anchor_block = get_genesis_forkchoice_store_and_block(spec, state)
    yield "anchor_state", state
    yield "anchor_block", anchor_block

    current_time = state.slot * (spec.config.SLOT_DURATION_MS // 1000) + store.genesis_time
    on_tick_and_append_step(spec, store, current_time, test_steps)

    signed_block, block_root = yield from _add_block_and_get_root(spec, state, store, test_steps)

    envelope = _build_invalid_envelope(
        spec,
        state,
        block_root,
        signed_block,
        parent_hash=spec.Hash32(b"\x42" * 32),
    )
    yield from add_execution_payload(spec, store, envelope, test_steps, valid=False)

    assert block_root not in store.payloads

    yield "steps", test_steps


@with_gloas_and_later
@spec_state_test
def test_on_execution_payload_envelope__wrong_timestamp(spec, state):
    test_steps = []
    store, anchor_block = get_genesis_forkchoice_store_and_block(spec, state)
    yield "anchor_state", state
    yield "anchor_block", anchor_block

    current_time = state.slot * (spec.config.SLOT_DURATION_MS // 1000) + store.genesis_time
    on_tick_and_append_step(spec, store, current_time, test_steps)

    signed_block, block_root = yield from _add_block_and_get_root(spec, state, store, test_steps)

    envelope = _build_invalid_envelope(
        spec,
        state,
        block_root,
        signed_block,
        timestamp=spec.compute_time_at_slot(state, state.slot) + 1,
    )
    yield from add_execution_payload(spec, store, envelope, test_steps, valid=False)

    assert block_root not in store.payloads

    yield "steps", test_steps
