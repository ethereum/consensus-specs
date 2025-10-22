from eth2spec.test.context import (
    default_activation_threshold,
    single_phase,
    spec_state_test,
    spec_test,
    with_custom_state,
    with_eip7805_and_later,
)
from eth2spec.test.helpers.fork_choice import get_genesis_forkchoice_store
from eth2spec.test.helpers.inclusion_list import (
    get_empty_signed_inclusion_list,
    get_sample_inclusion_list,
    get_sample_signed_inclusion_list,
    get_sample_transactions,
    run_with_inclusion_list_store,
    sign_inclusion_list,
)
from tests.core.pyspec.eth2spec.utils.hash_function import ZERO_BYTES32


@with_eip7805_and_later
@spec_state_test
def test_inclusion_list_store_transaction_uniqueness(spec, state):
    def run_func():
        forkchoice_store = get_genesis_forkchoice_store(spec, state)
        inclusion_list_store = spec.get_inclusion_list_store()
        inclusion_list_committee = spec.get_inclusion_list_committee(state, state.slot)

        signed_inclusion_lists = []

        # An empty IL.
        signed_inclusion_lists.append(
            get_empty_signed_inclusion_list(
                spec, state, validator_index=inclusion_list_committee[0]
            )
        )

        # An IL with empty transactions.
        signed_inclusion_lists.append(
            get_sample_signed_inclusion_list(
                spec,
                state,
                validator_index=inclusion_list_committee[1],
                max_transaction_size=0,
                max_transaction_count=5,
            )
        )

        # Two ILs that have the same list of transactions.
        transactions = get_sample_transactions(spec)
        signed_inclusion_lists.append(
            get_sample_signed_inclusion_list(
                spec,
                state,
                validator_index=inclusion_list_committee[2],
                transactions=transactions,
            )
        )
        signed_inclusion_lists.append(
            get_sample_signed_inclusion_list(
                spec,
                state,
                validator_index=inclusion_list_committee[3],
                transactions=transactions,
            )
        )

        # An IL with non-overlapping transactions with other ILs.
        signed_inclusion_lists.append(
            get_sample_signed_inclusion_list(
                spec,
                state,
                validator_index=inclusion_list_committee[4],
            )
        )

        # A full-sized IL with 1 transaction.
        signed_inclusion_lists.append(
            get_sample_signed_inclusion_list(
                spec,
                state,
                validator_index=inclusion_list_committee[5],
                max_transaction_size=spec.config.MAX_BYTES_PER_INCLUSION_LIST,
                max_transaction_count=1,
            )
        )

        # A full-sized IL with multiple transactions.
        signed_inclusion_lists.append(
            get_sample_signed_inclusion_list(
                spec,
                state,
                validator_index=inclusion_list_committee[6],
                max_transaction_size=spec.config.MAX_BYTES_PER_INCLUSION_LIST // 16,
                max_transaction_count=16,
            )
        )

        # A full-sized IL with transactions each of which is 1 byte.
        signed_inclusion_lists.append(
            get_sample_signed_inclusion_list(
                spec,
                state,
                validator_index=inclusion_list_committee[7],
                max_transaction_size=1,
                max_transaction_count=spec.config.MAX_BYTES_PER_INCLUSION_LIST,
            )
        )

        for signed_inclusion_list in signed_inclusion_lists:
            spec.on_inclusion_list(forkchoice_store, signed_inclusion_list)

        inclusion_list_transactions = spec.get_inclusion_list_transactions(
            inclusion_list_store, state, state.slot
        )

        assert len(inclusion_list_transactions) == len(set(inclusion_list_transactions))
        assert set(inclusion_list_transactions) == set(
            transaction
            for signed_inclusion_list in signed_inclusion_lists
            for transaction in signed_inclusion_list.message.transactions
        )

    run_with_inclusion_list_store(spec, run_func)


@with_eip7805_and_later
@spec_state_test
def test_inclusion_list_store_by_slot_and_committee_root(spec, state):
    def run_func():
        forkchoice_store = get_genesis_forkchoice_store(spec, state)
        inclusion_list_store = spec.get_inclusion_list_store()

        signed_inclusion_list_slot_0 = get_sample_signed_inclusion_list(spec, state)

        spec.on_inclusion_list(forkchoice_store, signed_inclusion_list_slot_0)

        inclusion_list_transactions_slot_0 = spec.get_inclusion_list_transactions(
            inclusion_list_store, state, state.slot
        )
        inclusion_list_transactions_slot_1 = spec.get_inclusion_list_transactions(
            inclusion_list_store, state, state.slot + 1
        )

        assert set(inclusion_list_transactions_slot_0) == set(
            signed_inclusion_list_slot_0.message.transactions
        )
        assert inclusion_list_transactions_slot_1 == []

        # Advance state to slot 1.
        spec.process_slots(state, state.slot + 1)

        signed_inclusion_list_slot_1 = get_sample_signed_inclusion_list(spec, state)
        inclusion_list = get_sample_inclusion_list(spec, state)
        inclusion_list.inclusion_list_committee_root = ZERO_BYTES32
        signed_inclusion_list_slot_1_different_committee_root = sign_inclusion_list(
            spec, state, inclusion_list
        )

        spec.on_inclusion_list(forkchoice_store, signed_inclusion_list_slot_1)
        spec.on_inclusion_list(
            forkchoice_store, signed_inclusion_list_slot_1_different_committee_root
        )

        inclusion_list_transactions_slot_1 = spec.get_inclusion_list_transactions(
            inclusion_list_store, state, state.slot
        )

        assert set(inclusion_list_transactions_slot_1) == set(
            signed_inclusion_list_slot_1.message.transactions
        )

    run_with_inclusion_list_store(spec, run_func)


@with_eip7805_and_later
@spec_state_test
def test_inclusion_list_store_equivocation(spec, state):
    def run_func():
        forkchoice_store = get_genesis_forkchoice_store(spec, state)
        inclusion_list_store = spec.get_inclusion_list_store()
        inclusion_list_committee = spec.get_inclusion_list_committee(state, state.slot)

        signed_inclusion_list_1 = get_sample_signed_inclusion_list(
            spec, state, validator_index=inclusion_list_committee[0]
        )
        signed_inclusion_list_2 = get_sample_signed_inclusion_list(
            spec, state, validator_index=inclusion_list_committee[0]
        )
        signed_inclusion_list_3 = get_sample_signed_inclusion_list(
            spec, state, validator_index=inclusion_list_committee[0]
        )
        signed_inclusion_list_4 = get_sample_signed_inclusion_list(
            spec, state, validator_index=inclusion_list_committee[1]
        )

        # The first IL from an IL committee member should be stored successfully.
        spec.on_inclusion_list(forkchoice_store, signed_inclusion_list_1)

        inclusion_list_transactions = spec.get_inclusion_list_transactions(
            inclusion_list_store, state, state.slot
        )

        assert set(inclusion_list_transactions) == set(signed_inclusion_list_1.message.transactions)

        # The IL committee member equivocates. This will empty all ILs from that equivocator.
        spec.on_inclusion_list(forkchoice_store, signed_inclusion_list_2)

        inclusion_list_transactions = spec.get_inclusion_list_transactions(
            inclusion_list_store, state, state.slot
        )

        assert inclusion_list_transactions == []

        # An IL from another IL committee member should be stored successfully.
        spec.on_inclusion_list(forkchoice_store, signed_inclusion_list_4)

        inclusion_list_transactions = spec.get_inclusion_list_transactions(
            inclusion_list_store, state, state.slot
        )

        assert set(inclusion_list_transactions) == set(signed_inclusion_list_4.message.transactions)

        # The equivocator equivocates again. This should not affect other ILs.
        spec.on_inclusion_list(forkchoice_store, signed_inclusion_list_3)

        inclusion_list_transactions = spec.get_inclusion_list_transactions(
            inclusion_list_store, state, state.slot
        )

        assert set(inclusion_list_transactions) == set(signed_inclusion_list_4.message.transactions)

    run_with_inclusion_list_store(spec, run_func)


@with_eip7805_and_later
@spec_test
@with_custom_state(
    balances_fn=lambda spec: [spec.MAX_EFFECTIVE_BALANCE] * spec.INCLUSION_LIST_COMMITTEE_SIZE,
    threshold_fn=default_activation_threshold,
)
@single_phase
def test_inclusion_list_store_equivocation_scope(spec, state):
    def run_func():
        forkchoice_store = get_genesis_forkchoice_store(spec, state)
        inclusion_list_store = spec.get_inclusion_list_store()
        inclusion_list_committee = spec.get_inclusion_list_committee(state, state.slot)
        validator_index = inclusion_list_committee[0]

        signed_inclusion_list_1 = get_sample_signed_inclusion_list(
            spec, state, validator_index=validator_index
        )
        signed_inclusion_list_2 = get_sample_signed_inclusion_list(
            spec, state, validator_index=validator_index
        )

        # An IL committee member equivocates.
        spec.on_inclusion_list(forkchoice_store, signed_inclusion_list_1)
        spec.on_inclusion_list(forkchoice_store, signed_inclusion_list_2)

        inclusion_list_transactions = spec.get_inclusion_list_transactions(
            inclusion_list_store, state, state.slot
        )

        assert inclusion_list_transactions == []

        # Advance state to slot 1.
        spec.process_slots(state, state.slot + 1)

        inclusion_list_committee = spec.get_inclusion_list_committee(state, state.slot)
        assert validator_index in inclusion_list_committee

        # After the equivocated slot, the IL committee member should be able to participate successfully.
        signed_inclusion_list_3 = get_sample_signed_inclusion_list(
            spec, state, validator_index=validator_index
        )

        spec.on_inclusion_list(forkchoice_store, signed_inclusion_list_3)

        inclusion_list_transactions = spec.get_inclusion_list_transactions(
            inclusion_list_store, state, state.slot
        )

        assert set(inclusion_list_transactions) == set(signed_inclusion_list_3.message.transactions)

    run_with_inclusion_list_store(spec, run_func)


@with_eip7805_and_later
@spec_state_test
def test_inclusion_list_store_view_freeze_cutoff(spec, state):
    def run_func():
        forkchoice_store = get_genesis_forkchoice_store(spec, state)
        inclusion_list_store = spec.get_inclusion_list_store()
        inclusion_list_committee = spec.get_inclusion_list_committee(state, state.slot)

        signed_inclusion_list_1 = get_sample_signed_inclusion_list(
            spec, state, validator_index=inclusion_list_committee[0]
        )
        signed_inclusion_list_2 = get_sample_signed_inclusion_list(
            spec, state, validator_index=inclusion_list_committee[0]
        )
        signed_inclusion_list_3 = get_sample_signed_inclusion_list(
            spec, state, validator_index=inclusion_list_committee[1]
        )

        # An IL received before the view freeze cutoff should be stored successfully.
        spec.on_inclusion_list(forkchoice_store, signed_inclusion_list_1)

        inclusion_list_transactions = spec.get_inclusion_list_transactions(
            inclusion_list_store, state, state.slot
        )

        assert set(inclusion_list_transactions) == set(signed_inclusion_list_1.message.transactions)

        # Advance time to after the view freeze cutoff.
        epoch = spec.get_current_store_epoch(forkchoice_store)
        view_freeze_cutoff_ceiling = spec.get_view_freeze_cutoff_ms(epoch) // 1000 + 1
        assert view_freeze_cutoff_ceiling < spec.config.SECONDS_PER_SLOT

        time = forkchoice_store.time + view_freeze_cutoff_ceiling
        spec.on_tick(forkchoice_store, time)
        assert forkchoice_store.time == time

        # An IL received after the view freeze cutoff should be ignored.
        spec.on_inclusion_list(forkchoice_store, signed_inclusion_list_3)

        inclusion_list_transactions = spec.get_inclusion_list_transactions(
            inclusion_list_store, state, state.slot
        )

        assert set(inclusion_list_transactions) == set(signed_inclusion_list_1.message.transactions)

        # Any equivocation after the view freeze cutoff should still be handled.
        spec.on_inclusion_list(forkchoice_store, signed_inclusion_list_2)

        inclusion_list_transactions = spec.get_inclusion_list_transactions(
            inclusion_list_store, state, state.slot
        )

        assert inclusion_list_transactions == []

    run_with_inclusion_list_store(spec, run_func)
