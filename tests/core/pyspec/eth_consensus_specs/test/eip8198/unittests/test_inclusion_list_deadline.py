from eth_consensus_specs.test.context import spec_configured_state_test, with_phases
from eth_consensus_specs.test.helpers.constants import EIP8198
from eth_consensus_specs.test.helpers.eip8198.schedule import slot_duration_schedule_entry
from eth_consensus_specs.test.helpers.fork_choice import get_genesis_forkchoice_store
from eth_consensus_specs.test.helpers.inclusion_list import (
    get_sample_signed_inclusion_list,
    run_with_inclusion_list_store,
)


@with_phases([EIP8198])
@spec_configured_state_test(
    {
        "EIP8198_FORK_EPOCH": 2,
        "SLOT_DURATION_SCHEDULE": (
            slot_duration_schedule_entry(0, 6000),
            slot_duration_schedule_entry(2, 5000),
        ),
    },
    activate_at_genesis=True,
)
def test_inclusion_lists_at_scheduled_deadline(spec, state):
    def run_test():
        store = get_genesis_forkchoice_store(spec, state)
        slot = spec.compute_start_slot_at_epoch(spec.Epoch(3))
        spec.process_slots(state, slot)
        slot_time_ms = spec.compute_time_at_slot_ms(store, slot)
        spec.on_tick_ms(store, slot_time_ms)
        committee = spec.get_inclusion_list_committee(state, slot)
        inclusion_list_store = spec.get_inclusion_list_store()
        deadline_ms = spec.get_inclusion_list_due_ms(slot)

        for index, offset in enumerate((-1, 0, 1)):
            transaction = spec.Transaction(data=[index + 1])
            signed = get_sample_signed_inclusion_list(
                spec,
                store,
                state,
                validator_index=committee[index],
                transactions=spec.Transactions(data=[transaction]),
            )
            spec.on_tick_ms(store, slot_time_ms + deadline_ms + offset)
            spec.on_inclusion_list(store, signed)
            timely = spec.get_inclusion_list_transactions(
                inclusion_list_store,
                slot,
                signed.message.dependent_root,
            )
            assert (transaction in timely) == (offset < 0)
            all_transactions = spec.get_inclusion_list_transactions(
                inclusion_list_store,
                slot,
                signed.message.dependent_root,
                only_timely=False,
            )
            assert transaction in all_transactions

    run_with_inclusion_list_store(spec, run_test)
