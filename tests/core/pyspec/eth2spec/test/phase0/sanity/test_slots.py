from eth2spec.test.helpers.forks import (
    is_post_capella,
)
from eth2spec.test.helpers.state import get_state_root
from eth2spec.test.context import (
    spec_state_test,
    with_all_phases,
)


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
