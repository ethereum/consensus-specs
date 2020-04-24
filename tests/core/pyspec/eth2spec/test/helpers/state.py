from eth2spec.test.context import expect_assertion_error
from eth2spec.test.helpers.block import sign_block, transition_unsigned_block


def get_balance(state, index):
    return state.balances[index]


def next_slot(spec, state):
    """
    Transition to the next slot.
    """
    spec.process_slots(state, state.slot + 1)


def next_slots(spec, state, slots):
    """
    Transition given slots forward.
    """
    spec.process_slots(state, state.slot + slots)


def transition_to(spec, state, slot):
    """
    Transition to ``slot``.
    """
    assert state.slot <= slot
    for _ in range(slot - state.slot):
        next_slot(spec, state)
    assert state.slot == slot


def next_epoch(spec, state):
    """
    Transition to the start slot of the next epoch
    """
    slot = state.slot + spec.SLOTS_PER_EPOCH - (state.slot % spec.SLOTS_PER_EPOCH)
    spec.process_slots(state, slot)


def get_state_root(spec, state, slot) -> bytes:
    """
    Return the state root at a recent ``slot``.
    """
    assert slot < state.slot <= slot + spec.SLOTS_PER_HISTORICAL_ROOT
    return state.state_roots[slot % spec.SLOTS_PER_HISTORICAL_ROOT]


def state_transition_and_sign_block(spec, state, block, expect_fail=False):
    """
    State transition via the provided ``block``
    then package the block with the correct state root and signature.
    """
    if expect_fail:
        expect_assertion_error(lambda: transition_unsigned_block(spec, state, block))
    else:
        transition_unsigned_block(spec, state, block)
    block.state_root = state.hash_tree_root()
    return sign_block(spec, state, block)
