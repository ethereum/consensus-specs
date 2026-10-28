from eth_consensus_specs.test.context import (
    always_bls,
    spec_state_test,
    with_heze_and_later,
)
from eth_consensus_specs.test.helpers.fork_choice import (
    add_inclusion_list,
    get_genesis_forkchoice_store_and_block,
    setup_one_block_store,
    tick_store_to_slot,
)
from eth_consensus_specs.test.helpers.inclusion_list import (
    cached_inclusion_list_store,
    get_sample_inclusion_list,
    get_sample_signed_inclusion_list,
    sign_inclusion_list,
)


def _run_on_inclusion_list(
    spec, state, modify_inclusion_list=None, slot_offset=0, current_slot_offset=0, valid=True
):
    """
    Build an inclusion list for ``slot_offset`` slots after slot 1 from the first
    member of its committee, apply ``modify_inclusion_list``, sign it and run
    ``on_inclusion_list`` ``current_slot_offset`` slots after slot 1. A stored
    inclusion list must be timely only if it arrived in its own slot.
    """
    with cached_inclusion_list_store(spec):
        store, _, block_state, _, test_steps = yield from setup_one_block_store(spec, state)

        inclusion_list = get_sample_inclusion_list(
            spec, store, block_state, slot=block_state.slot + slot_offset
        )
        if modify_inclusion_list is not None:
            modify_inclusion_list(spec, store, block_state, inclusion_list)
        signed_inclusion_list = sign_inclusion_list(spec, block_state, inclusion_list)

        tick_store_to_slot(spec, store, block_state.slot + current_slot_offset, test_steps)
        yield from add_inclusion_list(spec, store, signed_inclusion_list, test_steps, valid=valid)

        key = (inclusion_list.slot, inclusion_list.dependent_root)
        entries = spec.get_inclusion_list_store().inclusion_lists[key]
        assert (inclusion_list.validator_index in entries) == valid
        if valid:
            entry = entries[inclusion_list.validator_index]
            assert entry.timely == (inclusion_list.slot == spec.get_current_slot(store))

    yield "steps", test_steps


@with_heze_and_later
@spec_state_test
def test_on_inclusion_list_valid(spec, state):
    """
    Test that a valid inclusion list for the current slot is stored.
    """
    yield from _run_on_inclusion_list(spec, state)


@with_heze_and_later
@spec_state_test
def test_on_inclusion_list_future_slot(spec, state):
    """
    Test that an inclusion list for a future slot is rejected.
    """
    yield from _run_on_inclusion_list(spec, state, slot_offset=1, valid=False)


@with_heze_and_later
@spec_state_test
def test_on_inclusion_list_slot_outside_retention_window(spec, state):
    """
    Test that an inclusion list older than the retention window is rejected.
    """
    yield from _run_on_inclusion_list(
        spec,
        state,
        current_slot_offset=spec.config.MIN_SLOTS_FOR_INCLUSION_LISTS_REQUESTS + 1,
        valid=False,
    )


@with_heze_and_later
@spec_state_test
def test_on_inclusion_list_previous_slot_within_retention_window(spec, state):
    """
    Test that an inclusion list for the previous slot is still stored.
    """
    yield from _run_on_inclusion_list(
        spec, state, current_slot_offset=spec.config.MIN_SLOTS_FOR_INCLUSION_LISTS_REQUESTS
    )


def _set_transactions(transactions_fn):
    def modify_inclusion_list(spec, store, state, inclusion_list):
        inclusion_list.transactions = spec.Transactions(data=transactions_fn(spec))

    return modify_inclusion_list


@with_heze_and_later
@spec_state_test
def test_on_inclusion_list_empty_transactions(spec, state):
    """
    Test that an inclusion list without transactions is rejected.
    """
    yield from _run_on_inclusion_list(spec, state, _set_transactions(lambda spec: []), valid=False)


@with_heze_and_later
@spec_state_test
def test_on_inclusion_list_transactions_at_max_size(spec, state):
    """
    Test that an inclusion list whose transactions total exactly
    MAX_TRANSACTIONS_BYTES_PER_INCLUSION_LIST bytes is stored.
    """
    yield from _run_on_inclusion_list(
        spec,
        state,
        _set_transactions(
            lambda spec: [
                spec.Transaction(data=[1] * spec.config.MAX_TRANSACTIONS_BYTES_PER_INCLUSION_LIST)
            ]
        ),
    )


@with_heze_and_later
@spec_state_test
def test_on_inclusion_list_transactions_over_max_size(spec, state):
    """
    Test that an inclusion list whose transactions total more than
    MAX_TRANSACTIONS_BYTES_PER_INCLUSION_LIST bytes is rejected.
    """
    yield from _run_on_inclusion_list(
        spec,
        state,
        _set_transactions(
            lambda spec: [
                spec.Transaction(data=[1] * spec.config.MAX_TRANSACTIONS_BYTES_PER_INCLUSION_LIST),
                spec.Transaction(data=[1]),
            ]
        ),
        valid=False,
    )


@with_heze_and_later
@spec_state_test
def test_on_inclusion_list_empty_transaction(spec, state):
    """
    Test that an inclusion list containing an empty transaction is rejected.
    """
    yield from _run_on_inclusion_list(
        spec,
        state,
        _set_transactions(lambda spec: [spec.Transaction(data=[1]), spec.Transaction()]),
        valid=False,
    )


@with_heze_and_later
@spec_state_test
def test_on_inclusion_list_unknown_dependent_root(spec, state):
    """
    Test that an inclusion list with an unknown dependent root is rejected.
    """

    def modify_inclusion_list(spec, store, state, inclusion_list):
        inclusion_list.dependent_root = spec.Root(b"\x42" * 32)

    yield from _run_on_inclusion_list(spec, state, modify_inclusion_list, valid=False)


@with_heze_and_later
@spec_state_test
def test_on_inclusion_list_dependent_root_after_dependent_slot(spec, state):
    """
    Test that an inclusion list whose dependent block is after the shuffling
    dependent slot is rejected.
    """

    def modify_inclusion_list(spec, store, state, inclusion_list):
        head_root = spec.get_head(store).root
        epoch = spec.compute_epoch_at_slot(inclusion_list.slot)
        assert store.blocks[head_root].slot > spec.compute_shuffling_dependent_slot(epoch)
        inclusion_list.dependent_root = head_root

    yield from _run_on_inclusion_list(spec, state, modify_inclusion_list, valid=False)


@with_heze_and_later
@spec_state_test
def test_on_inclusion_list_dependent_root_is_head(spec, state):
    """
    Test that an inclusion list whose dependent block is the head, with no
    descendants, is stored.
    """
    with cached_inclusion_list_store(spec):
        test_steps = []
        store, anchor_block = get_genesis_forkchoice_store_and_block(spec, state)
        yield "anchor_state", state
        yield "anchor_block", anchor_block

        signed_inclusion_list = get_sample_signed_inclusion_list(spec, store, state)
        assert signed_inclusion_list.message.dependent_root == spec.get_head(store).root
        yield from add_inclusion_list(spec, store, signed_inclusion_list, test_steps)

    yield "steps", test_steps


@with_heze_and_later
@spec_state_test
def test_on_inclusion_list_dependent_root_superseded(spec, state):
    """
    Test that an inclusion list whose dependent block has a descendant at or
    before the shuffling dependent slot is rejected.
    """
    with cached_inclusion_list_store(spec):
        store, _, _, signed_block, test_steps = yield from setup_one_block_store(spec, state)

        # The genesis block is superseded by its child at slot 1
        epoch = spec.MIN_SEED_LOOKAHEAD + 1
        superseded_root = signed_block.message.parent_root
        dependent_slot = spec.compute_shuffling_dependent_slot(epoch)
        assert not spec.is_valid_dependent_root(store, superseded_root, dependent_slot)
        tick_store_to_slot(spec, store, spec.compute_start_slot_at_epoch(epoch), test_steps)

        # Pick a committee member under the superseded block's shuffling so that
        # only the dependent root check fails
        dependent_state = store.block_states[superseded_root].copy()
        spec.process_slots(dependent_state, spec.compute_shuffling_lookahead_start_slot(epoch))
        inclusion_list = get_sample_inclusion_list(
            spec, store, dependent_state, slot=spec.get_current_slot(store)
        )
        assert inclusion_list.dependent_root != superseded_root
        inclusion_list.dependent_root = superseded_root
        signed_inclusion_list = sign_inclusion_list(spec, dependent_state, inclusion_list)
        yield from add_inclusion_list(spec, store, signed_inclusion_list, test_steps, valid=False)

    yield "steps", test_steps


@with_heze_and_later
@spec_state_test
def test_on_inclusion_list_validator_not_in_committee(spec, state):
    """
    Test that an inclusion list from a validator outside the inclusion list
    committee is rejected.
    """

    def modify_inclusion_list(spec, store, state, inclusion_list):
        committee = spec.get_inclusion_list_committee(state, inclusion_list.slot)
        inclusion_list.validator_index = next(
            index for index in range(len(state.validators)) if index not in committee
        )

    yield from _run_on_inclusion_list(spec, state, modify_inclusion_list, valid=False)


@with_heze_and_later
@spec_state_test
@always_bls
def test_on_inclusion_list_invalid_signature(spec, state):
    """
    Test that an inclusion list with an invalid signature is rejected.
    """
    with cached_inclusion_list_store(spec):
        store, _, block_state, _, test_steps = yield from setup_one_block_store(spec, state)
        inclusion_list = get_sample_inclusion_list(spec, store, block_state)
        signed_inclusion_list = spec.SignedInclusionList(
            message=inclusion_list, signature=spec.BLSSignature()
        )
        yield from add_inclusion_list(spec, store, signed_inclusion_list, test_steps, valid=False)

    yield "steps", test_steps
