import random
from eth2spec.test.context import fork_transition_test
from eth2spec.test.helpers.constants import PHASE0, ALTAIR
from eth2spec.test.helpers.fork_transition import (
    do_altair_fork,
    transition_until_fork,
    transition_to_next_epoch_and_append_blocks,
)
from eth2spec.test.helpers.random import (
    exit_random_validators,
    set_some_new_deposits,
)


#
# Exit
#

@fork_transition_test(PHASE0, ALTAIR, fork_epoch=2)
def test_transition_with_one_fourth_exiting_validators_exit_post_fork(state,
                                                                      fork_epoch,
                                                                      spec,
                                                                      post_spec,
                                                                      pre_tag,
                                                                      post_tag):
    """
    1/4 validators initiated voluntary exit before the fork,
    and are exiting but still active *after* the fork transition.
    """
    exited_indices = exit_random_validators(
        spec, state, rng=random.Random(5566), fraction=0.25, exit_epoch=10, forward=False)

    transition_until_fork(spec, state, fork_epoch)

    # check pre state
    assert len(exited_indices) > 0
    for index in exited_indices:
        validator = state.validators[index]
        assert not validator.slashed
        assert fork_epoch < validator.exit_epoch < spec.FAR_FUTURE_EPOCH
        assert spec.is_active_validator(validator, spec.get_current_epoch(state))
    assert not spec.is_in_inactivity_leak(state)
    assert spec.get_current_epoch(state) < fork_epoch

    yield "pre", state

    # irregular state transition to handle fork:
    blocks = []
    state, block = do_altair_fork(state, spec, post_spec, fork_epoch)
    blocks.append(post_tag(block))

    # ensure that some of the current sync committee members are exiting
    exited_pubkeys = [state.validators[index].pubkey for index in exited_indices]
    assert any(set(exited_pubkeys).intersection(list(state.current_sync_committee.pubkeys)))
    assert any(set(exited_pubkeys).difference(list(state.current_sync_committee.pubkeys)))

    # continue regular state transition with new spec into next epoch
    transition_to_next_epoch_and_append_blocks(post_spec, state, post_tag, blocks, only_last_block=True)

    # check state
    for index in exited_indices:
        validator = state.validators[index]
        assert not validator.slashed
        assert post_spec.is_active_validator(validator, post_spec.get_current_epoch(state))
    assert not post_spec.is_in_inactivity_leak(state)

    yield "blocks", blocks
    yield "post", state


@fork_transition_test(PHASE0, ALTAIR, fork_epoch=2)
def test_transition_with_one_fourth_exiting_validators_exit_at_fork(state,
                                                                    fork_epoch,
                                                                    spec,
                                                                    post_spec,
                                                                    pre_tag,
                                                                    post_tag):
    """
    1/4 validators initiated voluntary exit before the fork,
    and being exited and inactive *right after* the fork transition.
    """
    exited_indices = exit_random_validators(
        spec, state, rng=random.Random(5566), fraction=0.25, exit_epoch=fork_epoch, forward=False)

    transition_until_fork(spec, state, fork_epoch)

    # check pre state
    assert len(exited_indices) > 0
    for index in exited_indices:
        validator = state.validators[index]
        assert not validator.slashed
        assert fork_epoch == validator.exit_epoch < spec.FAR_FUTURE_EPOCH
        assert spec.is_active_validator(validator, spec.get_current_epoch(state))
    assert not spec.is_in_inactivity_leak(state)
    assert spec.get_current_epoch(state) < fork_epoch

    yield "pre", state

    # irregular state transition to handle fork:
    blocks = []
    state, block = do_altair_fork(state, spec, post_spec, fork_epoch)
    blocks.append(post_tag(block))

    # check post transition state
    for index in exited_indices:
        validator = state.validators[index]
        assert not validator.slashed
        assert not post_spec.is_active_validator(validator, post_spec.get_current_epoch(state))
    assert not post_spec.is_in_inactivity_leak(state)

    # ensure that none of the current sync committee members are exited validators
    exited_pubkeys = [state.validators[index].pubkey for index in exited_indices]
    assert not any(set(exited_pubkeys).intersection(list(state.current_sync_committee.pubkeys)))

    # continue regular state transition with new spec into next epoch
    transition_to_next_epoch_and_append_blocks(post_spec, state, post_tag, blocks, only_last_block=True)

    yield "blocks", blocks
    yield "post", state


#
# Activation
#


@fork_transition_test(PHASE0, ALTAIR, fork_epoch=2)
def test_transition_with_non_empty_activation_queue(state, fork_epoch, spec, post_spec, pre_tag, post_tag):
    """
    Create some deposits before the transition
    """
    transition_until_fork(spec, state, fork_epoch)

    queuing_indices = set_some_new_deposits(spec, state, rng=random.Random(5566))

    assert spec.get_current_epoch(state) < fork_epoch
    assert len(queuing_indices) > 0
    for validator_index in queuing_indices:
        assert not spec.is_active_validator(state.validators[validator_index], spec.get_current_epoch(state))

    yield "pre", state

    # irregular state transition to handle fork:
    blocks = []
    state, block = do_altair_fork(state, spec, post_spec, fork_epoch)
    blocks.append(post_tag(block))

    # continue regular state transition with new spec into next epoch
    transition_to_next_epoch_and_append_blocks(post_spec, state, post_tag, blocks, only_last_block=True)

    yield "blocks", blocks
    yield "post", state
