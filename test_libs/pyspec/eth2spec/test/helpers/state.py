def get_balance(state, index):
    return state.balances[index]


def next_slot(spec, state):
    """
    Transition to the next slot.
    """
    spec.process_slots(state, state.slot + 1)


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
    return state.latest_state_roots[slot % spec.SLOTS_PER_HISTORICAL_ROOT]
