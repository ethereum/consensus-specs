import eth2spec.phase0.spec as spec

from eth2spec.phase0.spec import process_slots
from eth2spec.test.helpers.state import get_state_root
from eth2spec.test.context import spec_state_test


@spec_state_test
def test_slots_1(state):
    pre_slot = state.slot
    pre_root = state.hash_tree_root()
    yield 'pre', state

    slots = 1
    yield 'slots', slots
    process_slots(state, state.slot + slots)

    yield 'post', state
    assert state.slot == pre_slot + 1
    assert get_state_root(state, pre_slot) == pre_root


@spec_state_test
def test_slots_2(state):
    yield 'pre', state
    slots = 2
    yield 'slots', slots
    process_slots(state, state.slot + slots)
    yield 'post', state


@spec_state_test
def test_empty_epoch(state):
    yield 'pre', state
    slots = spec.SLOTS_PER_EPOCH
    yield 'slots', slots
    process_slots(state, state.slot + slots)
    yield 'post', state


@spec_state_test
def test_double_empty_epoch(state):
    yield 'pre', state
    slots = spec.SLOTS_PER_EPOCH * 2
    yield 'slots', slots
    process_slots(state, state.slot + slots)
    yield 'post', state


@spec_state_test
def test_over_epoch_boundary(state):
    process_slots(state, state.slot + (spec.SLOTS_PER_EPOCH // 2))
    yield 'pre', state
    slots = spec.SLOTS_PER_EPOCH
    yield 'slots', slots
    process_slots(state, state.slot + slots)
    yield 'post', state
