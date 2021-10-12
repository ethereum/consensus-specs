import random

from eth2spec.test.helpers.state import (
    next_slot,
    state_transition_and_sign_block,
    transition_to,
)
from eth2spec.test.helpers.block import (
    build_empty_block_for_next_slot,
    build_empty_block,
    sign_block,
)


def _state_transition_and_sign_block_at_slot(spec, state, deposits=None):
    """
    Cribbed from ``transition_unsigned_block`` helper
    where the early parts of the state transition have already
    been applied to ``state``.

    Used to produce a block during an irregular state transition.
    """
    block = build_empty_block(spec, state)
    # FIXME: not just passing `deposits`
    if deposits is not None:
        block.body.deposits = deposits

    assert state.latest_block_header.slot < block.slot
    assert state.slot == block.slot
    spec.process_block(state, block)
    block.state_root = state.hash_tree_root()
    return sign_block(spec, state, block)


def _all_blocks(_):
    return True


def skip_slots(*slots):
    """
    Skip making a block if its slot is
    passed as an argument to this filter
    """
    def f(state_at_prior_slot):
        return state_at_prior_slot.slot + 1 not in slots
    return f


def no_blocks(_):
    return False


def only_at(slot):
    """
    Only produce a block if its slot is ``slot``.
    """
    def f(state_at_prior_slot):
        return state_at_prior_slot.slot + 1 == slot
    return f


def state_transition_across_slots(spec, state, to_slot, block_filter=_all_blocks):
    assert state.slot < to_slot
    while state.slot < to_slot:
        should_make_block = block_filter(state)
        if should_make_block:
            block = build_empty_block_for_next_slot(spec, state)
            signed_block = state_transition_and_sign_block(spec, state, block)
            yield signed_block
        else:
            next_slot(spec, state)


def state_transition_across_slots_with_ignoring_proposers(spec, state, to_slot, ignoring_proposers):
    """
    The slashed validators can't be proposers. Here we ignore the given `ignoring_proposers`
    and ensure that the result state was computed with a block with slot >= to_slot.
    """
    assert state.slot < to_slot

    found_valid = False
    while state.slot < to_slot or not found_valid:
        future_state = state.copy()
        next_slot(spec, future_state)
        proposer_index = spec.get_beacon_proposer_index(future_state)
        if proposer_index not in ignoring_proposers:
            block = build_empty_block_for_next_slot(spec, state)
            signed_block = state_transition_and_sign_block(spec, state, block)
            yield signed_block
            if state.slot >= to_slot:
                found_valid = True
        else:
            next_slot(spec, state)


def do_altair_fork(state, spec, post_spec, fork_epoch, with_block=True, deposits=None):
    spec.process_slots(state, state.slot + 1)

    assert state.slot % spec.SLOTS_PER_EPOCH == 0
    assert spec.get_current_epoch(state) == fork_epoch

    state = post_spec.upgrade_to_altair(state)

    assert state.fork.epoch == fork_epoch
    assert state.fork.previous_version == post_spec.config.GENESIS_FORK_VERSION
    assert state.fork.current_version == post_spec.config.ALTAIR_FORK_VERSION

    if with_block:
        return state, _state_transition_and_sign_block_at_slot(post_spec, state, deposits=deposits)
    else:
        return state, None


def set_validators_exit_epoch(spec, state, exit_epoch, rng=random.Random(40404040), fraction=0.25):
    """
    Set some valdiators' exit_epoch.
    """
    selected_count = int(len(state.validators) * fraction)
    selected_indices = rng.sample(range(len(state.validators)), selected_count)
    for validator_index in selected_indices:
        state.validators[validator_index].exit_epoch = exit_epoch
        state.validators[validator_index].withdrawable_epoch = (
            exit_epoch + spec.config.MIN_VALIDATOR_WITHDRAWABILITY_DELAY
        )
    return selected_indices


def transition_until_fork(spec, state, fork_epoch):
    to_slot = fork_epoch * spec.SLOTS_PER_EPOCH - 1
    transition_to(spec, state, to_slot)
