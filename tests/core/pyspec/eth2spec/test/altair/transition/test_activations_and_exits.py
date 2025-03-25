import random
from eth2spec.test.context import (
    ForkMeta,
    ALTAIR,
    with_presets,
    with_fork_metas,
)
from eth2spec.test.helpers.constants import (
    ALL_PRE_POST_FORKS,
    MINIMAL,
)
from eth2spec.test.helpers.fork_transition import (
    do_fork,
    transition_until_fork,
    transition_to_next_epoch_and_append_blocks,
)
from eth2spec.test.helpers.random import (
    exit_random_validators,
    set_some_activations,
    set_some_new_deposits,
)


#
# Exit
#


@with_fork_metas(
    [
        ForkMeta(pre_fork_name=pre, post_fork_name=post, fork_epoch=2)
        for pre, post in ALL_PRE_POST_FORKS
    ]
)
@with_presets(
    [MINIMAL],
    reason="only test with enough validators such that at least one exited index is not in sync committee",
)
def test_transition_with_one_fourth_exiting_validators_exit_post_fork(
    state, fork_epoch, spec, post_spec, pre_tag, post_tag
):
    """
    1/4 validators initiated voluntary exit before the fork,
    and are exiting but still active *after* the fork transition.
    """
    exited_indices = exit_random_validators(
        spec,
        state,
        rng=random.Random(5566),
        fraction=0.25,
        exit_epoch=10,
        from_epoch=spec.get_current_epoch(state),
    )

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
    state, block = do_fork(state, spec, post_spec, fork_epoch)
    blocks.append(post_tag(block))

    # ensure that some of the current sync committee members are exiting
    exited_pubkeys = [state.validators[index].pubkey for index in exited_indices]
    assert any(
        set(exited_pubkeys).intersection(list(state.current_sync_committee.pubkeys))
    )
    assert any(
        set(exited_pubkeys).difference(list(state.current_sync_committee.pubkeys))
    )

    # continue regular state transition with new spec into next epoch
    transition_to_next_epoch_and_append_blocks(
        post_spec, state, post_tag, blocks, only_last_block=True
    )

    # check state
    for index in exited_indices:
        validator = state.validators[index]
        assert not validator.slashed
        assert post_spec.is_active_validator(
            validator, post_spec.get_current_epoch(state)
        )
    assert not post_spec.is_in_inactivity_leak(state)

    yield "blocks", blocks
    yield "post", state


@with_fork_metas(
    [
        ForkMeta(pre_fork_name=pre, post_fork_name=post, fork_epoch=2)
        for pre, post in ALL_PRE_POST_FORKS
    ]
)
def test_transition_with_one_fourth_exiting_validators_exit_at_fork(
    state, fork_epoch, spec, post_spec, pre_tag, post_tag
):
    """
    1/4 validators initiated voluntary exit before the fork,
    and being exited and inactive *right after* the fork transition.
    """
    exited_indices = exit_random_validators(
        spec,
        state,
        rng=random.Random(5566),
        fraction=0.25,
        exit_epoch=fork_epoch,
        from_epoch=spec.get_current_epoch(state),
    )

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
    state, block = do_fork(state, spec, post_spec, fork_epoch)
    blocks.append(post_tag(block))

    # check post transition state
    for index in exited_indices:
        validator = state.validators[index]
        assert not validator.slashed
        assert not post_spec.is_active_validator(
            validator, post_spec.get_current_epoch(state)
        )
    assert not post_spec.is_in_inactivity_leak(state)

    exited_pubkeys = [state.validators[index].pubkey for index in exited_indices]
    some_sync_committee_exited = any(
        set(exited_pubkeys).intersection(list(state.current_sync_committee.pubkeys))
    )
    if post_spec.fork == ALTAIR:
        # in Altair fork, the sync committee members would be set with only active validators
        assert not some_sync_committee_exited
    else:
        assert some_sync_committee_exited

    # continue regular state transition with new spec into next epoch
    transition_to_next_epoch_and_append_blocks(
        post_spec, state, post_tag, blocks, only_last_block=True
    )

    yield "blocks", blocks
    yield "post", state


#
# Activation
#


@with_fork_metas(
    [
        ForkMeta(pre_fork_name=pre, post_fork_name=post, fork_epoch=2)
        for pre, post in ALL_PRE_POST_FORKS
    ]
)
def test_transition_with_non_empty_activation_queue(
    state, fork_epoch, spec, post_spec, pre_tag, post_tag
):
    """
    Create some deposits before the transition
    """
    transition_until_fork(spec, state, fork_epoch)

    deposited_indices = set_some_new_deposits(spec, state, rng=random.Random(5566))

    assert spec.get_current_epoch(state) < fork_epoch
    assert len(deposited_indices) > 0
    for validator_index in deposited_indices:
        assert not spec.is_active_validator(
            state.validators[validator_index], spec.get_current_epoch(state)
        )

    yield "pre", state

    # irregular state transition to handle fork:
    blocks = []
    state, block = do_fork(state, spec, post_spec, fork_epoch)
    blocks.append(post_tag(block))

    # continue regular state transition with new spec into next epoch
    transition_to_next_epoch_and_append_blocks(
        post_spec, state, post_tag, blocks, only_last_block=True
    )

    yield "blocks", blocks
    yield "post", state


@with_fork_metas(
    [
        ForkMeta(pre_fork_name=pre, post_fork_name=post, fork_epoch=2)
        for pre, post in ALL_PRE_POST_FORKS
    ]
)
def test_transition_with_activation_at_fork_epoch(
    state, fork_epoch, spec, post_spec, pre_tag, post_tag
):
    """
    Create some deposits before the transition
    """
    transition_until_fork(spec, state, fork_epoch)

    selected_indices = set_some_activations(
        spec, state, rng=random.Random(5566), activation_epoch=fork_epoch
    )

    assert spec.get_current_epoch(state) < fork_epoch
    assert len(selected_indices) > 0
    for validator_index in selected_indices:
        validator = state.validators[validator_index]
        assert not spec.is_active_validator(validator, spec.get_current_epoch(state))
        assert validator.activation_epoch == fork_epoch

    yield "pre", state

    # irregular state transition to handle fork:
    blocks = []
    state, block = do_fork(state, spec, post_spec, fork_epoch)
    blocks.append(post_tag(block))

    # continue regular state transition with new spec into next epoch
    transition_to_next_epoch_and_append_blocks(
        post_spec, state, post_tag, blocks, only_last_block=True
    )

    # now they are active
    for validator_index in selected_indices:
        validator = state.validators[validator_index]
        assert post_spec.is_active_validator(
            validator, post_spec.get_current_epoch(state)
        )

    yield "blocks", blocks
    yield "post", state
