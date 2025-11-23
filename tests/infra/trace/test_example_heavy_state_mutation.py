from eth2spec.test.context import (
    spec_state_test,
    with_all_phases,
)
from eth2spec.test.helpers.state import get_state_root, next_epoch, next_slot, transition_to
from tests.infra.trace import record_spec_trace


@with_all_phases
@spec_state_test
@record_spec_trace
def test_example_test_slots_1(spec, state):
    pre_slot = state.slot
    pre_root = state.hash_tree_root()

    slots = 1
    spec.process_slots(state, state.slot + slots)

    assert state.slot == pre_slot + 1
    assert get_state_root(spec, state, pre_slot) == pre_root


@with_all_phases
@spec_state_test
@record_spec_trace
def test_example_test_balance_change_affects_proposer(spec, state):
    # Brute-force an instance where a validator's balance change prevents it from proposing.
    for _ in range(100):
        original_state = state.copy()

        # Get the proposer of the first slot in the next epoch
        next_epoch_state = state.copy()
        next_epoch(spec, next_epoch_state)
        proposer_next_epoch = spec.get_beacon_proposer_index(next_epoch_state)

        # Reduce the validator's balance
        spec.decrease_balance(state, proposer_next_epoch, 10 * spec.EFFECTIVE_BALANCE_INCREMENT)

        # Check if the proposer changed
        tmp_state = state.copy()
        next_epoch(spec, tmp_state)
        if proposer_next_epoch != spec.get_beacon_proposer_index(tmp_state):
            break
        else:
            state = original_state.copy()
            next_epoch(spec, state)

    # Transition to the last slot of the current epoch
    slot = state.slot + spec.SLOTS_PER_EPOCH - (state.slot % spec.SLOTS_PER_EPOCH) - 1
    transition_to(spec, state, slot)

    # Transition to the next epoch
    next_slot(spec, state)

    # Verify that the proposer changed
    proposer_next_epoch_after_change = spec.get_beacon_proposer_index(state)
    assert proposer_next_epoch != proposer_next_epoch_after_change
