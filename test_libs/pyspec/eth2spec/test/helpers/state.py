# Access constants from spec pkg reference.
import eth2spec.phase0.spec as spec

from eth2spec.phase0.state_transition import state_transition_to, state_transition
from eth2spec.test.helpers.block import build_empty_block


def get_balance(state, index):
    return state.balances[index]


def next_slot(state):
    """
    Transition to the next slot.
    """
    state_transition_to(state, state.slot + 1)


def next_epoch(state):
    """
    Transition to the start slot of the next epoch
    """
    slot = state.slot + spec.SLOTS_PER_EPOCH - (state.slot % spec.SLOTS_PER_EPOCH)
    state_transition_to(state, slot)


def apply_empty_block(state):
    """
    Transition via an empty block (on current slot, assuming no block has been applied yet).
    :return: the empty block that triggered the transition.
    """
    block = build_empty_block(state)
    state_transition(state, block)
    return block


def get_state_root(state, slot) -> bytes:
    """
    Return the state root at a recent ``slot``.
    """
    assert slot < state.slot <= slot + spec.SLOTS_PER_HISTORICAL_ROOT
    return state.latest_state_roots[slot % spec.SLOTS_PER_HISTORICAL_ROOT]
