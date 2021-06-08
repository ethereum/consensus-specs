from eth2spec.test.context import expect_assertion_error
from eth2spec.test.helpers.block import apply_empty_block, sign_block, transition_unsigned_block


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
    if slots > 0:
        spec.process_slots(state, state.slot + slots)


def transition_to(spec, state, slot):
    """
    Transition to ``slot``.
    """
    assert state.slot <= slot
    for _ in range(slot - state.slot):
        next_slot(spec, state)
    assert state.slot == slot


def transition_to_slot_via_block(spec, state, slot):
    """
    Transition to ``slot`` via an empty block transition
    """
    assert state.slot < slot
    apply_empty_block(spec, state, slot)
    assert state.slot == slot


def transition_to_valid_shard_slot(spec, state):
    """
    Transition to slot `compute_epoch_at_slot(spec.config.SHARDING_FORK_EPOCH) + 1`
    and fork at `compute_epoch_at_slot(spec.config.SHARDING_FORK_EPOCH)`.
    """
    transition_to(spec, state, spec.compute_epoch_at_slot(spec.config.SHARDING_FORK_EPOCH))
    next_slot(spec, state)


def next_epoch(spec, state):
    """
    Transition to the start slot of the next epoch
    """
    slot = state.slot + spec.SLOTS_PER_EPOCH - (state.slot % spec.SLOTS_PER_EPOCH)
    if slot > state.slot:
        spec.process_slots(state, slot)


def next_epoch_via_block(spec, state, insert_state_root=False):
    """
    Transition to the start slot of the next epoch via a full block transition
    """
    block = apply_empty_block(spec, state, state.slot + spec.SLOTS_PER_EPOCH - state.slot % spec.SLOTS_PER_EPOCH)
    if insert_state_root:
        block.state_root = state.hash_tree_root()
    return block


def next_epoch_via_signed_block(spec, state):
    block = next_epoch_via_block(spec, state, insert_state_root=True)
    return sign_block(spec, state, block)


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
