from eth_consensus_specs.test.context import (
    spec_state_test_with_matching_config,
    with_heze_and_later,
)
from eth_consensus_specs.test.gloas.networking.test_gossip_proposer_preferences import (
    setup_store_with_advanced_state,
)
from eth_consensus_specs.test.helpers.block import (
    build_empty_block,
    build_empty_block_for_next_slot,
)
from eth_consensus_specs.test.helpers.gossip import (
    add_pending_block_to_store,
    get_filename,
    get_seen,
    run_validate_gossip,
)
from eth_consensus_specs.test.helpers.inclusion_list import (
    get_empty_inclusion_list,
    get_sample_inclusion_list,
    get_sample_signed_inclusion_list,
    sign_inclusion_list,
)
from eth_consensus_specs.test.helpers.state import state_transition_and_sign_block


def setup_store_for_inclusion_list(spec, state, target_epoch=None):
    """Build a chain to an epoch with a non-genesis dependent root by default."""
    if target_epoch is None:
        target_epoch = spec.Epoch(spec.MIN_SEED_LOOKAHEAD + 1)
    target_slot = spec.compute_start_slot_at_epoch(spec.Epoch(target_epoch))
    return setup_store_with_advanced_state(spec, state, target_slot)


@with_heze_and_later
@spec_state_test_with_matching_config
def test_gossip_inclusion_list__valid(spec, state):
    """A well-formed SignedInclusionList from a committee member is valid."""
    anchor_state = state.copy()
    yield "topic", "meta", "inclusion_list"

    store, blocks = setup_store_for_inclusion_list(spec, state)

    yield "state", anchor_state
    seen = get_seen(spec)
    for signed in blocks:
        yield get_filename(signed), signed
    yield "blocks", "meta", [{"block": get_filename(b)} for b in blocks]

    signed_il = get_sample_signed_inclusion_list(spec, store, state)
    yield get_filename(signed_il), signed_il

    time_ms = spec.compute_time_at_slot_ms(store, state.slot)
    yield "current_time_ms", "meta", int(time_ms)
    messages = []

    time_ms += 100
    result, reason = run_validate_gossip(
        spec,
        seen=seen,
        store=store,
        signed_inclusion_list=signed_il,
        current_time_ms=time_ms,
    )
    assert result == "valid"
    assert reason is None
    messages.append(
        {
            "current_time_ms": int(time_ms),
            "message": get_filename(signed_il),
            "expected": result,
        }
    )

    yield "messages", "meta", messages


@with_heze_and_later
@spec_state_test_with_matching_config
def test_gossip_inclusion_list__ignore_third_message_from_validator(spec, state):
    """The first two distinct messages from a validator are valid; the third is ignored."""
    anchor_state = state.copy()
    yield "topic", "meta", "inclusion_list"

    store, blocks = setup_store_for_inclusion_list(spec, state)

    yield "state", anchor_state
    seen = get_seen(spec)
    for signed in blocks:
        yield get_filename(signed), signed
    yield "blocks", "meta", [{"block": get_filename(b)} for b in blocks]

    validator_index = spec.get_inclusion_list_committee(state, state.slot)[0]
    signed_ils = [
        get_sample_signed_inclusion_list(
            spec,
            store,
            state,
            validator_index=validator_index,
            transactions=spec.Transactions(data=[spec.Transaction(data=[i])]),
        )
        for i in range(3)
    ]

    time_ms = spec.compute_time_at_slot_ms(store, state.slot)
    yield "current_time_ms", "meta", int(time_ms)
    messages = []

    for i, signed_il in enumerate(signed_ils):
        yield get_filename(signed_il), signed_il
        time_ms += 100
        result, reason = run_validate_gossip(
            spec,
            seen=seen,
            store=store,
            signed_inclusion_list=signed_il,
            current_time_ms=time_ms,
        )
        entry = {
            "current_time_ms": int(time_ms),
            "message": get_filename(signed_il),
            "expected": result,
        }
        if i < 2:
            assert result == "valid"
            assert reason is None
        else:
            assert result == "ignore"
            assert reason == "already seen two valid inclusion lists from this validator"
            entry["reason"] = reason
        messages.append(entry)
        key = (signed_il.message.slot, signed_il.message.dependent_root, validator_index)
        assert seen.inclusion_list_counts[key] == min(i + 1, 2)

    yield "messages", "meta", messages


@with_heze_and_later
@spec_state_test_with_matching_config
def test_gossip_inclusion_list__ignore_not_current_slot(spec, state):
    """An inclusion list from an earlier slot is ignored."""
    anchor_state = state.copy()
    yield "topic", "meta", "inclusion_list"

    store, blocks = setup_store_for_inclusion_list(spec, state)

    yield "state", anchor_state
    seen = get_seen(spec)
    for signed in blocks:
        yield get_filename(signed), signed
    yield "blocks", "meta", [{"block": get_filename(b)} for b in blocks]

    signed_il = get_sample_signed_inclusion_list(spec, store, state)
    yield get_filename(signed_il), signed_il

    time_ms = spec.compute_time_at_slot_ms(store, spec.Slot(state.slot + 2))
    yield "current_time_ms", "meta", int(time_ms)
    messages = []

    time_ms += 100
    result, reason = run_validate_gossip(
        spec,
        seen=seen,
        store=store,
        signed_inclusion_list=signed_il,
        current_time_ms=time_ms,
    )
    assert result == "ignore"
    assert reason == "inclusion list is not for the current slot"
    messages.append(
        {
            "current_time_ms": int(time_ms),
            "message": get_filename(signed_il),
            "expected": result,
            "reason": reason,
        }
    )

    yield "messages", "meta", messages


@with_heze_and_later
@spec_state_test_with_matching_config
def test_gossip_inclusion_list__valid_slot_at_lower_disparity(spec, state):
    """An inclusion list at the lower clock-disparity edge is valid."""
    anchor_state = state.copy()
    yield "topic", "meta", "inclusion_list"

    store, blocks = setup_store_for_inclusion_list(spec, state)

    yield "state", anchor_state
    seen = get_seen(spec)
    for signed in blocks:
        yield get_filename(signed), signed
    yield "blocks", "meta", [{"block": get_filename(b)} for b in blocks]

    signed_il = get_sample_signed_inclusion_list(spec, store, state)
    yield get_filename(signed_il), signed_il

    time_ms = (
        spec.compute_time_at_slot_ms(store, state.slot) - spec.config.MAXIMUM_GOSSIP_CLOCK_DISPARITY
    )
    yield "current_time_ms", "meta", int(time_ms)
    messages = []

    result, reason = run_validate_gossip(
        spec,
        seen=seen,
        store=store,
        signed_inclusion_list=signed_il,
        current_time_ms=time_ms,
    )
    assert result == "valid"
    assert reason is None
    messages.append(
        {
            "current_time_ms": int(time_ms),
            "message": get_filename(signed_il),
            "expected": result,
        }
    )

    yield "messages", "meta", messages


@with_heze_and_later
@spec_state_test_with_matching_config
def test_gossip_inclusion_list__ignore_slot_outside_lower_disparity(spec, state):
    """An inclusion list 1ms before the lower clock-disparity edge is ignored."""
    anchor_state = state.copy()
    yield "topic", "meta", "inclusion_list"

    store, blocks = setup_store_for_inclusion_list(spec, state)

    yield "state", anchor_state
    seen = get_seen(spec)
    for signed in blocks:
        yield get_filename(signed), signed
    yield "blocks", "meta", [{"block": get_filename(b)} for b in blocks]

    signed_il = get_sample_signed_inclusion_list(spec, store, state)
    yield get_filename(signed_il), signed_il

    time_ms = (
        spec.compute_time_at_slot_ms(store, state.slot)
        - spec.config.MAXIMUM_GOSSIP_CLOCK_DISPARITY
        - 1
    )
    yield "current_time_ms", "meta", int(time_ms)
    messages = []

    result, reason = run_validate_gossip(
        spec,
        seen=seen,
        store=store,
        signed_inclusion_list=signed_il,
        current_time_ms=time_ms,
    )
    assert result == "ignore"
    assert reason == "inclusion list is not for the current slot"
    messages.append(
        {
            "current_time_ms": int(time_ms),
            "message": get_filename(signed_il),
            "expected": result,
            "reason": reason,
        }
    )

    yield "messages", "meta", messages


@with_heze_and_later
@spec_state_test_with_matching_config
def test_gossip_inclusion_list__valid_slot_at_upper_disparity(spec, state):
    """An inclusion list at the upper clock-disparity edge is valid."""
    anchor_state = state.copy()
    yield "topic", "meta", "inclusion_list"

    store, blocks = setup_store_for_inclusion_list(spec, state)

    yield "state", anchor_state
    seen = get_seen(spec)
    for signed in blocks:
        yield get_filename(signed), signed
    yield "blocks", "meta", [{"block": get_filename(b)} for b in blocks]

    signed_il = get_sample_signed_inclusion_list(spec, store, state)
    yield get_filename(signed_il), signed_il

    time_ms = (
        spec.compute_time_at_slot_ms(store, spec.Slot(state.slot + 1))
        + spec.config.MAXIMUM_GOSSIP_CLOCK_DISPARITY
    )
    yield "current_time_ms", "meta", int(time_ms)
    messages = []

    result, reason = run_validate_gossip(
        spec,
        seen=seen,
        store=store,
        signed_inclusion_list=signed_il,
        current_time_ms=time_ms,
    )
    assert result == "valid"
    assert reason is None
    messages.append(
        {
            "current_time_ms": int(time_ms),
            "message": get_filename(signed_il),
            "expected": result,
        }
    )

    yield "messages", "meta", messages


@with_heze_and_later
@spec_state_test_with_matching_config
def test_gossip_inclusion_list__ignore_slot_outside_upper_disparity(spec, state):
    """An inclusion list 1ms past the upper clock-disparity edge is ignored."""
    anchor_state = state.copy()
    yield "topic", "meta", "inclusion_list"

    store, blocks = setup_store_for_inclusion_list(spec, state)

    yield "state", anchor_state
    seen = get_seen(spec)
    for signed in blocks:
        yield get_filename(signed), signed
    yield "blocks", "meta", [{"block": get_filename(b)} for b in blocks]

    signed_il = get_sample_signed_inclusion_list(spec, store, state)
    yield get_filename(signed_il), signed_il

    time_ms = (
        spec.compute_time_at_slot_ms(store, spec.Slot(state.slot + 1))
        + spec.config.MAXIMUM_GOSSIP_CLOCK_DISPARITY
        + 1
    )
    yield "current_time_ms", "meta", int(time_ms)
    messages = []

    result, reason = run_validate_gossip(
        spec,
        seen=seen,
        store=store,
        signed_inclusion_list=signed_il,
        current_time_ms=time_ms,
    )
    assert result == "ignore"
    assert reason == "inclusion list is not for the current slot"
    messages.append(
        {
            "current_time_ms": int(time_ms),
            "message": get_filename(signed_il),
            "expected": result,
            "reason": reason,
        }
    )

    yield "messages", "meta", messages


@with_heze_and_later
@spec_state_test_with_matching_config
def test_gossip_inclusion_list__ignore_transactions_empty(spec, state):
    """An inclusion list with no transactions is ignored."""
    anchor_state = state.copy()
    yield "topic", "meta", "inclusion_list"

    store, blocks = setup_store_for_inclusion_list(spec, state)

    yield "state", anchor_state
    seen = get_seen(spec)
    for signed in blocks:
        yield get_filename(signed), signed
    yield "blocks", "meta", [{"block": get_filename(b)} for b in blocks]

    inclusion_list = get_empty_inclusion_list(spec, store, state)
    signed_il = sign_inclusion_list(spec, state, inclusion_list)
    yield get_filename(signed_il), signed_il

    time_ms = spec.compute_time_at_slot_ms(store, state.slot)
    yield "current_time_ms", "meta", int(time_ms)
    messages = []

    time_ms += 100
    result, reason = run_validate_gossip(
        spec,
        seen=seen,
        store=store,
        signed_inclusion_list=signed_il,
        current_time_ms=time_ms,
    )
    assert result == "ignore"
    assert reason == "inclusion list contains no transactions"
    messages.append(
        {
            "current_time_ms": int(time_ms),
            "message": get_filename(signed_il),
            "expected": result,
            "reason": reason,
        }
    )

    yield "messages", "meta", messages


@with_heze_and_later
@spec_state_test_with_matching_config
def test_gossip_inclusion_list__valid_transactions_at_size_limit(spec, state):
    """An inclusion list exactly at the transaction byte limit is valid."""
    anchor_state = state.copy()
    yield "topic", "meta", "inclusion_list"

    store, blocks = setup_store_for_inclusion_list(spec, state)

    yield "state", anchor_state
    seen = get_seen(spec)
    for signed in blocks:
        yield get_filename(signed), signed
    yield "blocks", "meta", [{"block": get_filename(b)} for b in blocks]

    size_limit = int(spec.config.MAX_TRANSACTIONS_BYTES_PER_INCLUSION_LIST)
    signed_il = get_sample_signed_inclusion_list(
        spec,
        store,
        state,
        transactions=spec.Transactions(data=[spec.Transaction(data=[0] * size_limit)]),
    )
    yield get_filename(signed_il), signed_il

    time_ms = spec.compute_time_at_slot_ms(store, state.slot)
    yield "current_time_ms", "meta", int(time_ms)
    messages = []

    time_ms += 100
    result, reason = run_validate_gossip(
        spec,
        seen=seen,
        store=store,
        signed_inclusion_list=signed_il,
        current_time_ms=time_ms,
    )
    assert result == "valid"
    assert reason is None
    messages.append(
        {
            "current_time_ms": int(time_ms),
            "message": get_filename(signed_il),
            "expected": result,
        }
    )

    yield "messages", "meta", messages


@with_heze_and_later
@spec_state_test_with_matching_config
def test_gossip_inclusion_list__reject_transactions_too_large(spec, state):
    """An inclusion list whose transactions exceed the byte limit is rejected."""
    anchor_state = state.copy()
    yield "topic", "meta", "inclusion_list"

    store, blocks = setup_store_for_inclusion_list(spec, state)

    yield "state", anchor_state
    seen = get_seen(spec)
    for signed in blocks:
        yield get_filename(signed), signed
    yield "blocks", "meta", [{"block": get_filename(b)} for b in blocks]

    over_limit_size = int(spec.config.MAX_TRANSACTIONS_BYTES_PER_INCLUSION_LIST) + 1
    signed_il = get_sample_signed_inclusion_list(
        spec,
        store,
        state,
        transactions=spec.Transactions(data=[spec.Transaction(data=[0] * over_limit_size)]),
    )
    yield get_filename(signed_il), signed_il

    time_ms = spec.compute_time_at_slot_ms(store, state.slot)
    yield "current_time_ms", "meta", int(time_ms)
    messages = []

    time_ms += 100
    result, reason = run_validate_gossip(
        spec,
        seen=seen,
        store=store,
        signed_inclusion_list=signed_il,
        current_time_ms=time_ms,
    )
    assert result == "reject"
    assert reason == "inclusion list transactions exceed the maximum size"
    messages.append(
        {
            "current_time_ms": int(time_ms),
            "message": get_filename(signed_il),
            "expected": result,
            "reason": reason,
        }
    )

    yield "messages", "meta", messages


@with_heze_and_later
@spec_state_test_with_matching_config
def test_gossip_inclusion_list__reject_transactions_too_large_multiple_transactions(spec, state):
    """Transactions within the individual byte limit but exceeding it in total are rejected."""
    anchor_state = state.copy()
    yield "topic", "meta", "inclusion_list"

    store, blocks = setup_store_for_inclusion_list(spec, state)

    yield "state", anchor_state
    seen = get_seen(spec)
    for signed in blocks:
        yield get_filename(signed), signed
    yield "blocks", "meta", [{"block": get_filename(b)} for b in blocks]

    size_limit = int(spec.config.MAX_TRANSACTIONS_BYTES_PER_INCLUSION_LIST)
    signed_il = get_sample_signed_inclusion_list(
        spec,
        store,
        state,
        transactions=spec.Transactions(
            data=[
                spec.Transaction(data=[0] * size_limit),
                spec.Transaction(data=[1]),
            ]
        ),
    )
    yield get_filename(signed_il), signed_il

    time_ms = spec.compute_time_at_slot_ms(store, state.slot)
    yield "current_time_ms", "meta", int(time_ms)
    messages = []

    time_ms += 100
    result, reason = run_validate_gossip(
        spec,
        seen=seen,
        store=store,
        signed_inclusion_list=signed_il,
        current_time_ms=time_ms,
    )
    assert result == "reject"
    assert reason == "inclusion list transactions exceed the maximum size"
    messages.append(
        {
            "current_time_ms": int(time_ms),
            "message": get_filename(signed_il),
            "expected": result,
            "reason": reason,
        }
    )

    yield "messages", "meta", messages


@with_heze_and_later
@spec_state_test_with_matching_config
def test_gossip_inclusion_list__reject_empty_transaction(spec, state):
    """An empty transaction alongside a non-empty transaction is rejected."""
    anchor_state = state.copy()
    yield "topic", "meta", "inclusion_list"

    store, blocks = setup_store_for_inclusion_list(spec, state)

    yield "state", anchor_state
    seen = get_seen(spec)
    for signed in blocks:
        yield get_filename(signed), signed
    yield "blocks", "meta", [{"block": get_filename(b)} for b in blocks]

    signed_il = get_sample_signed_inclusion_list(
        spec,
        store,
        state,
        transactions=spec.Transactions(data=[spec.Transaction(data=[1]), spec.Transaction()]),
    )
    yield get_filename(signed_il), signed_il

    time_ms = spec.compute_time_at_slot_ms(store, state.slot)
    yield "current_time_ms", "meta", int(time_ms)
    messages = []

    time_ms += 100
    result, reason = run_validate_gossip(
        spec,
        seen=seen,
        store=store,
        signed_inclusion_list=signed_il,
        current_time_ms=time_ms,
    )
    assert result == "reject"
    assert reason == "inclusion list contains an empty transaction"
    messages.append(
        {
            "current_time_ms": int(time_ms),
            "message": get_filename(signed_il),
            "expected": result,
            "reason": reason,
        }
    )

    yield "messages", "meta", messages


@with_heze_and_later
@spec_state_test_with_matching_config
def test_gossip_inclusion_list__ignore_dependent_block_unseen(spec, state):
    """An inclusion list whose dependent block has not been seen is ignored."""
    anchor_state = state.copy()
    yield "topic", "meta", "inclusion_list"

    store, blocks = setup_store_for_inclusion_list(spec, state)

    yield "state", anchor_state
    seen = get_seen(spec)
    for signed in blocks:
        yield get_filename(signed), signed
    yield "blocks", "meta", [{"block": get_filename(b)} for b in blocks]

    inclusion_list = get_sample_inclusion_list(spec, store, state)
    inclusion_list.dependent_root = spec.Root(b"\xab" * 32)
    signed_il = sign_inclusion_list(spec, state, inclusion_list)
    yield get_filename(signed_il), signed_il

    time_ms = spec.compute_time_at_slot_ms(store, state.slot)
    yield "current_time_ms", "meta", int(time_ms)
    messages = []

    time_ms += 100
    result, reason = run_validate_gossip(
        spec,
        seen=seen,
        store=store,
        signed_inclusion_list=signed_il,
        current_time_ms=time_ms,
    )
    assert result == "ignore"
    assert reason == "dependent block has not been seen"
    messages.append(
        {
            "current_time_ms": int(time_ms),
            "message": get_filename(signed_il),
            "expected": result,
            "reason": reason,
        }
    )

    yield "messages", "meta", messages


@with_heze_and_later
@spec_state_test_with_matching_config
def test_gossip_inclusion_list__ignore_dependent_block_state_unavailable(spec, state):
    """An inclusion list whose dependent block has no post-state is ignored."""
    anchor_state = state.copy()
    yield "topic", "meta", "inclusion_list"

    store, blocks = setup_store_for_inclusion_list(spec, state)
    epoch = spec.get_current_epoch(state)
    dependent_slot = spec.compute_shuffling_dependent_slot(epoch)
    fork_parent_root = spec.get_block_root_at_slot(state, spec.Slot(dependent_slot - 1))
    fork_state = store.block_states[fork_parent_root].copy()
    fork_block = build_empty_block_for_next_slot(spec, fork_state)
    fork_block.body.graffiti = spec.Bytes32(b"\x42" * 32)
    signed_fork_block = state_transition_and_sign_block(spec, fork_state, fork_block)
    dependent_root = signed_fork_block.message.hash_tree_root()

    # Construct the message before adding a pending leaf, which get_head cannot resolve.
    spec.process_slots(fork_state, spec.compute_shuffling_lookahead_start_slot(epoch))
    inclusion_list = get_sample_inclusion_list(spec, store, fork_state, slot=state.slot)
    inclusion_list.dependent_root = dependent_root
    signed_il = sign_inclusion_list(spec, fork_state, inclusion_list)
    add_pending_block_to_store(store, signed_fork_block)

    yield "state", anchor_state
    seen = get_seen(spec)
    for signed in blocks:
        yield get_filename(signed), signed
    yield get_filename(signed_fork_block), signed_fork_block
    yield (
        "blocks",
        "meta",
        [{"block": get_filename(b)} for b in blocks]
        + [{"block": get_filename(signed_fork_block), "pending": True}],
    )

    yield get_filename(signed_il), signed_il

    time_ms = spec.compute_time_at_slot_ms(store, state.slot)
    yield "current_time_ms", "meta", int(time_ms)
    messages = []

    time_ms += 100
    result, reason = run_validate_gossip(
        spec,
        seen=seen,
        store=store,
        signed_inclusion_list=signed_il,
        current_time_ms=time_ms,
    )
    assert result == "ignore"
    assert reason == "dependent block failed validation"
    messages.append(
        {
            "current_time_ms": int(time_ms),
            "message": get_filename(signed_il),
            "expected": result,
            "reason": reason,
        }
    )

    yield "messages", "meta", messages


@with_heze_and_later
@spec_state_test_with_matching_config
def test_gossip_inclusion_list__reject_dependent_block_at_lookahead_epoch_start(spec, state):
    """A dependent block at the shuffling decision slot is too late."""
    anchor_state = state.copy()
    yield "topic", "meta", "inclusion_list"

    store, blocks = setup_store_for_inclusion_list(spec, state)

    yield "state", anchor_state
    seen = get_seen(spec)
    for signed in blocks:
        yield get_filename(signed), signed
    yield "blocks", "meta", [{"block": get_filename(b)} for b in blocks]

    lookahead_start_slot = spec.compute_shuffling_lookahead_start_slot(
        spec.get_current_epoch(state)
    )
    dependent_root = spec.get_block_root_at_slot(state, lookahead_start_slot)
    inclusion_list = get_sample_inclusion_list(spec, store, state)
    inclusion_list.dependent_root = dependent_root
    signed_il = sign_inclusion_list(spec, state, inclusion_list)
    yield get_filename(signed_il), signed_il

    time_ms = spec.compute_time_at_slot_ms(store, state.slot)
    yield "current_time_ms", "meta", int(time_ms)
    messages = []

    time_ms += 100
    result, reason = run_validate_gossip(
        spec,
        seen=seen,
        store=store,
        signed_inclusion_list=signed_il,
        current_time_ms=time_ms,
    )
    assert result == "reject"
    assert reason == "dependent block is after the shuffling dependent slot"
    messages.append(
        {
            "current_time_ms": int(time_ms),
            "message": get_filename(signed_il),
            "expected": result,
            "reason": reason,
        }
    )

    yield "messages", "meta", messages


@with_heze_and_later
@spec_state_test_with_matching_config
def test_gossip_inclusion_list__valid_genesis_dependent_root_in_genesis_epoch(spec, state):
    """An inclusion list in the genesis epoch can use the genesis dependent root."""
    anchor_state = state.copy()
    yield "topic", "meta", "inclusion_list"

    store, blocks = setup_store_for_inclusion_list(spec, state, target_epoch=spec.GENESIS_EPOCH)

    yield "state", anchor_state
    seen = get_seen(spec)
    for signed in blocks:
        yield get_filename(signed), signed
    yield "blocks", "meta", [{"block": get_filename(b)} for b in blocks]

    signed_il = get_sample_signed_inclusion_list(spec, store, state)
    yield get_filename(signed_il), signed_il

    time_ms = spec.compute_time_at_slot_ms(store, state.slot)
    yield "current_time_ms", "meta", int(time_ms)
    messages = []

    time_ms += 100
    result, reason = run_validate_gossip(
        spec,
        seen=seen,
        store=store,
        signed_inclusion_list=signed_il,
        current_time_ms=time_ms,
    )
    assert result == "valid"
    assert reason is None
    messages.append(
        {
            "current_time_ms": int(time_ms),
            "message": get_filename(signed_il),
            "expected": result,
        }
    )

    yield "messages", "meta", messages


@with_heze_and_later
@spec_state_test_with_matching_config
def test_gossip_inclusion_list__reject_non_genesis_dependent_root_in_genesis_epoch(spec, state):
    """A non-genesis dependent block is too late for the genesis epoch."""
    anchor_state = state.copy()
    yield "topic", "meta", "inclusion_list"

    store, blocks = setup_store_with_advanced_state(spec, state, spec.Slot(1))

    yield "state", anchor_state
    seen = get_seen(spec)
    for signed in blocks:
        yield get_filename(signed), signed
    yield "blocks", "meta", [{"block": get_filename(b)} for b in blocks]

    inclusion_list = get_sample_inclusion_list(spec, store, state)
    inclusion_list.dependent_root = blocks[-1].message.hash_tree_root()
    signed_il = sign_inclusion_list(spec, state, inclusion_list)
    yield get_filename(signed_il), signed_il

    time_ms = spec.compute_time_at_slot_ms(store, state.slot)
    yield "current_time_ms", "meta", int(time_ms)
    messages = []

    time_ms += 100
    result, reason = run_validate_gossip(
        spec,
        seen=seen,
        store=store,
        signed_inclusion_list=signed_il,
        current_time_ms=time_ms,
    )
    assert result == "reject"
    assert reason == "dependent block is after the shuffling dependent slot"
    messages.append(
        {
            "current_time_ms": int(time_ms),
            "message": get_filename(signed_il),
            "expected": result,
            "reason": reason,
        }
    )

    yield "messages", "meta", messages


@with_heze_and_later
@spec_state_test_with_matching_config
def test_gossip_inclusion_list__valid_genesis_dependent_root_at_lookahead_epoch(spec, state):
    """Genesis remains a valid dependent root at MIN_SEED_LOOKAHEAD."""
    anchor_state = state.copy()
    yield "topic", "meta", "inclusion_list"

    store, blocks = setup_store_for_inclusion_list(spec, state, target_epoch=spec.GENESIS_EPOCH)
    inclusion_list_slot = spec.compute_start_slot_at_epoch(spec.Epoch(spec.MIN_SEED_LOOKAHEAD))

    yield "state", anchor_state
    seen = get_seen(spec)
    for signed in blocks:
        yield get_filename(signed), signed
    yield "blocks", "meta", [{"block": get_filename(b)} for b in blocks]

    signed_il = get_sample_signed_inclusion_list(spec, store, state, slot=inclusion_list_slot)
    yield get_filename(signed_il), signed_il

    time_ms = spec.compute_time_at_slot_ms(store, inclusion_list_slot)
    yield "current_time_ms", "meta", int(time_ms)
    messages = []

    time_ms += 100
    result, reason = run_validate_gossip(
        spec,
        seen=seen,
        store=store,
        signed_inclusion_list=signed_il,
        current_time_ms=time_ms,
    )
    assert result == "valid"
    assert reason is None
    messages.append(
        {
            "current_time_ms": int(time_ms),
            "message": get_filename(signed_il),
            "expected": result,
        }
    )

    yield "messages", "meta", messages


@with_heze_and_later
@spec_state_test_with_matching_config
def test_gossip_inclusion_list__reject_non_genesis_dependent_root_at_lookahead_epoch(spec, state):
    """A non-genesis dependent block is too late at MIN_SEED_LOOKAHEAD."""
    anchor_state = state.copy()
    yield "topic", "meta", "inclusion_list"

    store, blocks = setup_store_with_advanced_state(spec, state, spec.Slot(1))
    genesis_state = store.block_states[blocks[0].message.hash_tree_root()]
    inclusion_list_slot = spec.compute_start_slot_at_epoch(spec.Epoch(spec.MIN_SEED_LOOKAHEAD))

    yield "state", anchor_state
    seen = get_seen(spec)
    for signed in blocks:
        yield get_filename(signed), signed
    yield "blocks", "meta", [{"block": get_filename(b)} for b in blocks]

    inclusion_list = get_sample_inclusion_list(spec, store, genesis_state, slot=inclusion_list_slot)
    inclusion_list.dependent_root = blocks[-1].message.hash_tree_root()
    signed_il = sign_inclusion_list(spec, genesis_state, inclusion_list)
    yield get_filename(signed_il), signed_il

    time_ms = spec.compute_time_at_slot_ms(store, inclusion_list_slot)
    yield "current_time_ms", "meta", int(time_ms)
    messages = []

    time_ms += 100
    result, reason = run_validate_gossip(
        spec,
        seen=seen,
        store=store,
        signed_inclusion_list=signed_il,
        current_time_ms=time_ms,
    )
    assert result == "reject"
    assert reason == "dependent block is after the shuffling dependent slot"
    messages.append(
        {
            "current_time_ms": int(time_ms),
            "message": get_filename(signed_il),
            "expected": result,
            "reason": reason,
        }
    )

    yield "messages", "meta", messages


@with_heze_and_later
@spec_state_test_with_matching_config
def test_gossip_inclusion_list__ignore_dependent_block_not_possible(spec, state):
    """A dependent block superseded before the dependent slot on every branch is ignored."""
    anchor_state = state.copy()
    yield "topic", "meta", "inclusion_list"

    store, blocks = setup_store_for_inclusion_list(spec, state)

    yield "state", anchor_state
    seen = get_seen(spec)
    for signed in blocks:
        yield get_filename(signed), signed
    yield "blocks", "meta", [{"block": get_filename(b)} for b in blocks]

    epoch = spec.get_current_epoch(state)
    dependent_slot = spec.compute_shuffling_dependent_slot(epoch)
    dependent_root = spec.get_block_root_at_slot(state, spec.Slot(dependent_slot - 1))
    dependent_state = store.block_states[dependent_root].copy()
    spec.process_slots(dependent_state, spec.compute_shuffling_lookahead_start_slot(epoch))
    inclusion_list = get_sample_inclusion_list(spec, store, dependent_state, slot=state.slot)
    inclusion_list.dependent_root = dependent_root
    signed_il = sign_inclusion_list(spec, dependent_state, inclusion_list)
    yield get_filename(signed_il), signed_il

    time_ms = spec.compute_time_at_slot_ms(store, state.slot)
    yield "current_time_ms", "meta", int(time_ms)
    messages = []

    time_ms += 100
    result, reason = run_validate_gossip(
        spec,
        seen=seen,
        store=store,
        signed_inclusion_list=signed_il,
        current_time_ms=time_ms,
    )
    assert result == "ignore"
    assert reason == "dependent block is not a possible dependent block"
    messages.append(
        {
            "current_time_ms": int(time_ms),
            "message": get_filename(signed_il),
            "expected": result,
            "reason": reason,
        }
    )

    yield "messages", "meta", messages


@with_heze_and_later
@spec_state_test_with_matching_config
def test_gossip_inclusion_list__valid_dependent_block_is_head(spec, state):
    """An inclusion list is valid when its dependent block is the head with no children."""
    anchor_state = state.copy()
    yield "topic", "meta", "inclusion_list"

    epoch = spec.Epoch(spec.MIN_SEED_LOOKAHEAD + 1)
    inclusion_list_slot = spec.compute_start_slot_at_epoch(epoch)
    dependent_slot = spec.compute_shuffling_dependent_slot(epoch)
    store, blocks = setup_store_with_advanced_state(spec, state, dependent_slot)
    dependent_root = blocks[-1].message.hash_tree_root()
    assert spec.get_head(store).root == dependent_root
    assert not any(block.parent_root == dependent_root for block in store.blocks.values())

    # Advance the committee state without importing a child of the head.
    spec.process_slots(state, spec.compute_shuffling_lookahead_start_slot(epoch))

    yield "state", anchor_state
    seen = get_seen(spec)
    for signed in blocks:
        yield get_filename(signed), signed
    yield "blocks", "meta", [{"block": get_filename(b)} for b in blocks]

    signed_il = get_sample_signed_inclusion_list(spec, store, state, slot=inclusion_list_slot)
    assert signed_il.message.dependent_root == dependent_root
    yield get_filename(signed_il), signed_il

    time_ms = spec.compute_time_at_slot_ms(store, inclusion_list_slot)
    yield "current_time_ms", "meta", int(time_ms)
    messages = []

    time_ms += 100
    result, reason = run_validate_gossip(
        spec,
        seen=seen,
        store=store,
        signed_inclusion_list=signed_il,
        current_time_ms=time_ms,
    )
    assert result == "valid"
    assert reason is None
    messages.append(
        {
            "current_time_ms": int(time_ms),
            "message": get_filename(signed_il),
            "expected": result,
        }
    )

    yield "messages", "meta", messages


@with_heze_and_later
@spec_state_test_with_matching_config
def test_gossip_inclusion_list__valid_dependent_block_on_fork(spec, state):
    """A dependent block with a child past the dependent slot on another branch is valid."""
    anchor_state = state.copy()
    yield "topic", "meta", "inclusion_list"

    store, blocks = setup_store_for_inclusion_list(spec, state)
    epoch = spec.get_current_epoch(state)
    lookahead_start_slot = spec.compute_shuffling_lookahead_start_slot(epoch)
    fork_parent_root = spec.get_block_root_at_slot(state, spec.Slot(lookahead_start_slot - 2))
    fork_state = store.block_states[fork_parent_root].copy()
    fork_blocks = []
    for _ in range(2):
        block = build_empty_block_for_next_slot(spec, fork_state)
        block.body.graffiti = spec.Bytes32(b"\x42" * 32)
        signed_fork_block = state_transition_and_sign_block(spec, fork_state, block)
        block_root = signed_fork_block.message.hash_tree_root()
        store.blocks[block_root] = signed_fork_block.message
        store.block_states[block_root] = fork_state.copy()
        fork_blocks.append(signed_fork_block)
    dependent_root = fork_blocks[0].message.hash_tree_root()
    assert store.blocks[dependent_root].slot == lookahead_start_slot - 1
    assert fork_blocks[1].message.slot == lookahead_start_slot
    assert spec.get_head(store).root != dependent_root
    blocks += fork_blocks

    yield "state", anchor_state
    seen = get_seen(spec)
    for signed in blocks:
        yield get_filename(signed), signed
    yield "blocks", "meta", [{"block": get_filename(b)} for b in blocks]

    inclusion_list = get_sample_inclusion_list(spec, store, fork_state, slot=state.slot)
    inclusion_list.dependent_root = dependent_root
    signed_il = sign_inclusion_list(spec, fork_state, inclusion_list)
    yield get_filename(signed_il), signed_il

    time_ms = spec.compute_time_at_slot_ms(store, state.slot)
    yield "current_time_ms", "meta", int(time_ms)
    messages = []

    time_ms += 100
    result, reason = run_validate_gossip(
        spec,
        seen=seen,
        store=store,
        signed_inclusion_list=signed_il,
        current_time_ms=time_ms,
    )
    assert result == "valid"
    assert reason is None
    messages.append(
        {
            "current_time_ms": int(time_ms),
            "message": get_filename(signed_il),
            "expected": result,
        }
    )

    yield "messages", "meta", messages


@with_heze_and_later
@spec_state_test_with_matching_config
def test_gossip_inclusion_list__valid_dependent_block_across_empty_epochs(spec, state):
    """An old dependent state is advanced to derive the committee after two empty epochs."""
    anchor_state = state.copy()
    yield "topic", "meta", "inclusion_list"

    epoch = spec.Epoch(spec.MIN_SEED_LOOKAHEAD + 3)
    lookahead_start_slot = spec.compute_shuffling_lookahead_start_slot(epoch)
    first_empty_epoch = spec.Epoch(epoch - spec.MIN_SEED_LOOKAHEAD - 2)
    dependent_slot = spec.Slot(spec.compute_start_slot_at_epoch(first_empty_epoch) - 1)
    store, blocks = setup_store_with_advanced_state(spec, state, dependent_slot)
    dependent_root = blocks[-1].message.hash_tree_root()
    dependent_state = state.copy()

    # Skip two epochs before importing the next block.
    boundary_block = build_empty_block(spec, state, slot=lookahead_start_slot)
    signed_boundary_block = state_transition_and_sign_block(spec, state, boundary_block)
    boundary_root = signed_boundary_block.message.hash_tree_root()
    store.blocks[boundary_root] = signed_boundary_block.message
    store.block_states[boundary_root] = state.copy()
    blocks.append(signed_boundary_block)
    assert (
        spec.get_shuffling_dependent_root(store, boundary_root, spec.Epoch(epoch - 1))
        == dependent_root
    )
    assert spec.get_shuffling_dependent_root(store, boundary_root, epoch) == dependent_root

    # Choose a member that an unadvanced dependent state would not assign.
    for offset in range(spec.SLOTS_PER_EPOCH):
        inclusion_list_slot = spec.Slot(spec.compute_start_slot_at_epoch(epoch) + offset)
        committee = spec.get_inclusion_list_committee(state, inclusion_list_slot)
        stale_committee = spec.get_inclusion_list_committee(dependent_state, inclusion_list_slot)
        validator_index = next((index for index in committee if index not in stale_committee), None)
        if validator_index is not None:
            break
    else:
        raise AssertionError("expected advanced inclusion list committee to differ")

    yield "state", anchor_state
    seen = get_seen(spec)
    for signed in blocks:
        yield get_filename(signed), signed
    yield "blocks", "meta", [{"block": get_filename(b)} for b in blocks]

    signed_il = get_sample_signed_inclusion_list(
        spec, store, state, slot=inclusion_list_slot, validator_index=validator_index
    )
    assert signed_il.message.dependent_root == dependent_root
    yield get_filename(signed_il), signed_il

    time_ms = spec.compute_time_at_slot_ms(store, inclusion_list_slot)
    yield "current_time_ms", "meta", int(time_ms)
    messages = []

    time_ms += 100
    result, reason = run_validate_gossip(
        spec,
        seen=seen,
        store=store,
        signed_inclusion_list=signed_il,
        current_time_ms=time_ms,
    )
    assert result == "valid"
    assert reason is None
    messages.append(
        {
            "current_time_ms": int(time_ms),
            "message": get_filename(signed_il),
            "expected": result,
        }
    )

    yield "messages", "meta", messages


@with_heze_and_later
@spec_state_test_with_matching_config
def test_gossip_inclusion_list__reject_includer_not_in_committee(spec, state):
    """An inclusion list from a validator outside the committee is rejected."""
    anchor_state = state.copy()
    yield "topic", "meta", "inclusion_list"

    store, blocks = setup_store_for_inclusion_list(spec, state)

    yield "state", anchor_state
    seen = get_seen(spec)
    for signed in blocks:
        yield get_filename(signed), signed
    yield "blocks", "meta", [{"block": get_filename(b)} for b in blocks]

    committee = spec.get_inclusion_list_committee(state, state.slot)
    non_member = spec.ValidatorIndex(
        next(i for i in range(len(state.validators)) if i not in committee)
    )
    inclusion_list = get_sample_inclusion_list(spec, store, state)
    inclusion_list.validator_index = non_member
    signed_il = sign_inclusion_list(spec, state, inclusion_list)
    yield get_filename(signed_il), signed_il

    time_ms = spec.compute_time_at_slot_ms(store, state.slot)
    yield "current_time_ms", "meta", int(time_ms)
    messages = []

    time_ms += 100
    result, reason = run_validate_gossip(
        spec,
        seen=seen,
        store=store,
        signed_inclusion_list=signed_il,
        current_time_ms=time_ms,
    )
    assert result == "reject"
    assert reason == "includer is not a member of the committee"
    messages.append(
        {
            "current_time_ms": int(time_ms),
            "message": get_filename(signed_il),
            "expected": result,
            "reason": reason,
        }
    )

    yield "messages", "meta", messages


@with_heze_and_later
@spec_state_test_with_matching_config
def test_gossip_inclusion_list__reject_invalid_signature(spec, state):
    """An inclusion list with an invalid signature is rejected."""
    anchor_state = state.copy()
    yield "topic", "meta", "inclusion_list"

    store, blocks = setup_store_for_inclusion_list(spec, state)

    yield "state", anchor_state
    seen = get_seen(spec)
    for signed in blocks:
        yield get_filename(signed), signed
    yield "blocks", "meta", [{"block": get_filename(b)} for b in blocks]

    inclusion_list = get_sample_inclusion_list(spec, store, state)
    signed_il = spec.SignedInclusionList(message=inclusion_list, signature=spec.BLSSignature())
    yield get_filename(signed_il), signed_il

    time_ms = spec.compute_time_at_slot_ms(store, state.slot)
    yield "current_time_ms", "meta", int(time_ms)
    messages = []

    time_ms += 100
    result, reason = run_validate_gossip(
        spec,
        seen=seen,
        store=store,
        signed_inclusion_list=signed_il,
        current_time_ms=time_ms,
    )
    assert result == "reject"
    assert reason == "invalid inclusion list signature"
    messages.append(
        {
            "current_time_ms": int(time_ms),
            "message": get_filename(signed_il),
            "expected": result,
            "reason": reason,
        }
    )

    yield "messages", "meta", messages
