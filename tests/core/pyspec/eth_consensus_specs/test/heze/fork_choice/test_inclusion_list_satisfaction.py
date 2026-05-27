from eth_consensus_specs.test.context import (
    spec_state_test,
    with_heze_and_later,
)
from eth_consensus_specs.test.helpers.block import (
    build_empty_block_for_next_slot,
)
from eth_consensus_specs.test.helpers.fork_choice import (
    get_genesis_forkchoice_store_and_block,
    on_tick_and_append_step,
    tick_and_add_block,
)
from eth_consensus_specs.test.helpers.inclusion_list import (
    get_sample_signed_inclusion_list,
    run_with_inclusion_list_store,
)
from eth_consensus_specs.test.helpers.state import (
    state_transition_and_sign_block,
)


def _setup_test(spec, state):
    test_steps = []
    store, anchor_block = get_genesis_forkchoice_store_and_block(spec, state)
    yield "anchor_state", state
    yield "anchor_block", anchor_block
    current_time = state.slot * (spec.config.SLOT_DURATION_MS // 1000) + store.genesis_time
    on_tick_and_append_step(spec, store, current_time, test_steps)
    block = build_empty_block_for_next_slot(spec, state)
    signed_block = state_transition_and_sign_block(spec, state, block)
    yield from tick_and_add_block(spec, store, signed_block, test_steps)
    block_root = signed_block.message.hash_tree_root()
    return store, signed_block, block_root, test_steps


@with_heze_and_later
@spec_state_test
def test_payload_satisfies_empty_inclusion_list(spec, state):
    """
    A payload satisfies the IL constraints when there are no IL transactions.
    """
    def run_func():
        store, signed_block, block_root, test_steps = yield from _setup_test(spec, state)
        # No ILs submitted — satisfaction should be True
        assert spec.is_payload_inclusion_list_satisfied(store, block_root)

    run_with_inclusion_list_store(spec, run_func)


@with_heze_and_later
@spec_state_test
def test_should_extend_payload_false_when_il_unsatisfied(spec, state):
    """
    should_extend_payload returns False when IL constraints are not satisfied.
    """
    def run_func():
        store, signed_block, block_root, test_steps = yield from _setup_test(spec, state)
        inclusion_list_committee = spec.get_inclusion_list_committee(state, state.slot)

        # Submit an IL with transactions
        signed_il = get_sample_signed_inclusion_list(
            spec, state, validator_index=inclusion_list_committee[0]
        )
        spec.on_inclusion_list(store, signed_il)

        # Mark payload as NOT satisfying IL constraints
        store.payload_inclusion_list_satisfaction[block_root] = False

        # should_extend_payload must return False
        assert not spec.should_extend_payload(store, block_root)

    run_with_inclusion_list_store(spec, run_func)


@with_heze_and_later
@spec_state_test
def test_equivocating_il_member_transactions_excluded(spec, state):
    """
    Transactions from an equivocating IL committee member are excluded
    from get_inclusion_list_transactions (degraded 1-of-(N-equivocators) guarantee).
    """
    def run_func():
        store, signed_block, block_root, test_steps = yield from _setup_test(spec, state)
        inclusion_list_committee = spec.get_inclusion_list_committee(state, state.slot)
        validator_index = inclusion_list_committee[0]

        # Submit two different ILs from same validator (equivocation)
        signed_il_1 = get_sample_signed_inclusion_list(
            spec, state, validator_index=validator_index
        )
        signed_il_2 = get_sample_signed_inclusion_list(
            spec, state, validator_index=validator_index
        )
        spec.on_inclusion_list(store, signed_il_1)
        spec.on_inclusion_list(store, signed_il_2)

        inclusion_list_store = spec.get_inclusion_list_store()
        txs = spec.get_inclusion_list_transactions(inclusion_list_store, state, state.slot)

        # Equivocator's transactions must be excluded
        assert txs == []

    run_with_inclusion_list_store(spec, run_func)


@with_heze_and_later
@spec_state_test
def test_get_inclusion_list_transactions_only_timely_false(spec, state):
    """
    When only_timely=False, late IL transactions are included in the result.
    """
    def run_func():
        store, signed_block, block_root, test_steps = yield from _setup_test(spec, state)
        inclusion_list_committee = spec.get_inclusion_list_committee(state, state.slot)

        signed_il = get_sample_signed_inclusion_list(
            spec, state, validator_index=inclusion_list_committee[0]
        )

        # Advance time past inclusion list due deadline
        inclusion_list_due_ceiling = spec.get_inclusion_list_due_ms() // 1000 + 1
        store.time += inclusion_list_due_ceiling

        # Submit IL after deadline — marked as not timely
        spec.on_inclusion_list(store, signed_il)

        inclusion_list_store = spec.get_inclusion_list_store()

        # With only_timely=True (default), late IL is excluded
        txs_timely = spec.get_inclusion_list_transactions(
            inclusion_list_store, state, state.slot, only_timely=True
        )
        assert txs_timely == []

        # With only_timely=False, late IL is included
        txs_all = spec.get_inclusion_list_transactions(
            inclusion_list_store, state, state.slot, only_timely=False
        )
        assert set(txs_all) == set(signed_il.message.transactions)

    run_with_inclusion_list_store(spec, run_func)
