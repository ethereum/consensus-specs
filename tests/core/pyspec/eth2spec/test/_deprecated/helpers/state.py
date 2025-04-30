from eth2spec.test.context import expect_assertion_error
from eth2spec.test.helpers.block import apply_empty_block, sign_block, transition_unsigned_block


def transition_to(spec, state, slot):
    """
    Transition to ``slot``.
    """
    assert state.slot <= slot
    for _ in range(slot - state.slot):
        next_slot(spec, state)
    assert state.slot == slot


def transition_to_valid_shard_slot(spec, state):
    """
    Transition to slot `compute_epoch_at_slot(spec.config.SHARDING_FORK_EPOCH) + 1`
    and fork at `compute_epoch_at_slot(spec.config.SHARDING_FORK_EPOCH)`.
    """
    transition_to(spec, state, spec.compute_epoch_at_slot(spec.config.SHARDING_FORK_EPOCH))
    next_slot(spec, state)

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

def next_epoch_via_block(spec, state, insert_state_root=False):
    """
    Transition to the start slot of the next epoch via a full block transition
    """
    block = apply_empty_block(
        spec, state, state.slot + spec.SLOTS_PER_EPOCH - state.slot % spec.SLOTS_PER_EPOCH
    )
    if insert_state_root:
        block.state_root = state.hash_tree_root()
    return block
