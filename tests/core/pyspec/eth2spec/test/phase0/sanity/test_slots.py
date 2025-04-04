from eth2spec.test.helpers.forks import (
    is_post_capella,
)
from eth2spec.test.context import (
    spec_state_test,
    with_all_phases,
)
from eth2spec.test.helpers.state import get_state_root, next_epoch, next_slot, transition_to


@with_all_phases
@spec_state_test
def test_slots_1(spec, state):
    pre_slot = state.slot
    pre_root = state.hash_tree_root()
    yield "pre", state

    slots = 1
    yield "slots", int(slots)
    spec.process_slots(state, state.slot + slots)

    yield "post", state
    assert state.slot == pre_slot + 1
    assert get_state_root(spec, state, pre_slot) == pre_root


@with_all_phases
@spec_state_test
def test_slots_2(spec, state):
    yield "pre", state
    slots = 2
    yield "slots", int(slots)
    spec.process_slots(state, state.slot + slots)
    yield "post", state


@with_all_phases
@spec_state_test
def test_empty_epoch(spec, state):
    yield "pre", state
    slots = spec.SLOTS_PER_EPOCH
    yield "slots", int(slots)
    spec.process_slots(state, state.slot + slots)
    yield "post", state


@with_all_phases
@spec_state_test
def test_double_empty_epoch(spec, state):
    yield "pre", state
    slots = spec.SLOTS_PER_EPOCH * 2
    yield "slots", int(slots)
    spec.process_slots(state, state.slot + slots)
    yield "post", state


@with_all_phases
@spec_state_test
def test_over_epoch_boundary(spec, state):
    if spec.SLOTS_PER_EPOCH > 1:
        spec.process_slots(state, state.slot + (spec.SLOTS_PER_EPOCH // 2))
    yield "pre", state
    slots = spec.SLOTS_PER_EPOCH
    yield "slots", int(slots)
    spec.process_slots(state, state.slot + slots)
    yield "post", state


@with_all_phases
@spec_state_test
def test_historical_accumulator(spec, state):
    pre_historical_roots = state.historical_roots.copy()

    if is_post_capella(spec):
        pre_historical_summaries = state.historical_summaries.copy()

    yield "pre", state
    slots = spec.SLOTS_PER_HISTORICAL_ROOT
    yield "slots", int(slots)
    spec.process_slots(state, state.slot + slots)
    yield "post", state

    # check history update
    if is_post_capella(spec):
        # Frozen `historical_roots`
        assert state.historical_roots == pre_historical_roots
        assert len(state.historical_summaries) == len(pre_historical_summaries) + 1
    else:
        assert len(state.historical_roots) == len(pre_historical_roots) + 1


@with_all_phases
@spec_state_test
def test_balance_change_affects_proposer(spec, state):
    # Brute-force an instance where a validator's balance change prevents it from proposing.
    # We must brute-force this because sometimes the balance change doesn't make a difference.
    # Give this approach 100 attempts to find such a case.
    for _ in range(100):
        original_state = state.copy()

        # Get the proposer of the first slot in the next epoch
        next_epoch_state = state.copy()
        next_epoch(spec, next_epoch_state)
        proposer_next_epoch = spec.get_beacon_proposer_index(next_epoch_state)

        # Reduce the validator's balance, making it less likely to propose
        # The validator's effective balance will be updated during epoch processing
        spec.decrease_balance(state, proposer_next_epoch, 10 * spec.EFFECTIVE_BALANCE_INCREMENT)

        # Check if the proposer changed as a result of the balance change
        tmp_state = state.copy()
        next_epoch(spec, tmp_state)
        if proposer_next_epoch != spec.get_beacon_proposer_index(tmp_state):
            # Use this state
            break
        else:
            # Try another state
            state = original_state.copy()
            next_epoch(spec, state)

    # Transition to the last slot of the current epoch
    slot = state.slot + spec.SLOTS_PER_EPOCH - (state.slot % spec.SLOTS_PER_EPOCH) - 1
    transition_to(spec, state, slot)

    yield "pre", state
    yield "slots", 1

    # Transition to the next epoch
    next_slot(spec, state)

    yield "post", state

    # Verify that the proposer changed because of the balance change
    proposer_next_epoch_after_change = spec.get_beacon_proposer_index(state)
    assert proposer_next_epoch != proposer_next_epoch_after_change
