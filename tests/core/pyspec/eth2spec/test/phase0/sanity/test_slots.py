from eth2spec.test.helpers.forks import (
    is_post_capella,
)
from eth2spec.test.context import (
    spec_state_test,
    with_all_phases,
)
from eth2spec.test.helpers.state import (
    get_state_root,
    next_epoch,
    transition_to
)


@with_all_phases
@spec_state_test
def test_slots_1(spec, state):
    pre_slot = state.slot
    pre_root = state.hash_tree_root()
    yield 'pre', state

    slots = 1
    yield 'slots', int(slots)
    spec.process_slots(state, state.slot + slots)

    yield 'post', state
    assert state.slot == pre_slot + 1
    assert get_state_root(spec, state, pre_slot) == pre_root


@with_all_phases
@spec_state_test
def test_slots_2(spec, state):
    yield 'pre', state
    slots = 2
    yield 'slots', int(slots)
    spec.process_slots(state, state.slot + slots)
    yield 'post', state


@with_all_phases
@spec_state_test
def test_empty_epoch(spec, state):
    yield 'pre', state
    slots = spec.SLOTS_PER_EPOCH
    yield 'slots', int(slots)
    spec.process_slots(state, state.slot + slots)
    yield 'post', state


@with_all_phases
@spec_state_test
def test_double_empty_epoch(spec, state):
    yield 'pre', state
    slots = spec.SLOTS_PER_EPOCH * 2
    yield 'slots', int(slots)
    spec.process_slots(state, state.slot + slots)
    yield 'post', state


@with_all_phases
@spec_state_test
def test_over_epoch_boundary(spec, state):
    if spec.SLOTS_PER_EPOCH > 1:
        spec.process_slots(state, state.slot + (spec.SLOTS_PER_EPOCH // 2))
    yield 'pre', state
    slots = spec.SLOTS_PER_EPOCH
    yield 'slots', int(slots)
    spec.process_slots(state, state.slot + slots)
    yield 'post', state


@with_all_phases
@spec_state_test
def test_historical_accumulator(spec, state):
    pre_historical_roots = state.historical_roots.copy()

    if is_post_capella(spec):
        pre_historical_summaries = state.historical_summaries.copy()

    yield 'pre', state
    slots = spec.SLOTS_PER_HISTORICAL_ROOT
    yield 'slots', int(slots)
    spec.process_slots(state, state.slot + slots)
    yield 'post', state

    # check history update
    if is_post_capella(spec):
        # Frozen `historical_roots`
        assert state.historical_roots == pre_historical_roots
        assert len(state.historical_summaries) == len(pre_historical_summaries) + 1
    else:
        assert len(state.historical_roots) == len(pre_historical_roots) + 1


def run_epoch_processing(spec, state):
    slot = state.slot + spec.SLOTS_PER_EPOCH - (state.slot % spec.SLOTS_PER_EPOCH) - 1
    transition_to(spec, state, slot)
    yield 'pre', state
    yield 'slots', 1
    spec.process_slots(state, state.slot + 1)
    yield 'post', state


@with_all_phases
@spec_state_test
def test_balance_change_affects_proposer(spec, state):
    # Get 1 epoch in the future and get the proposer index selected
    future_state = state.copy()
    next_epoch(spec, future_state)
    proposer_next_epoch = spec.get_beacon_proposer_index(future_state)

    # Set the effective balance of the proposer selected to 0
    state.validators[proposer_next_epoch].effective_balance = 0

    # Process the epoch to go forward in time and ensure the balance
    # change is taken into account
    run_epoch_processing(spec, state)

    # Retrieve the index of the proposer selected
    proposer_next_epoch_after_change = spec.get_beacon_proposer_index(state)

    # Assert that the proposer selected did change
    assert proposer_next_epoch != proposer_next_epoch_after_change
