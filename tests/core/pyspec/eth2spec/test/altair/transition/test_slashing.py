import random
from eth2spec.test.context import (
    ForkMeta,
    with_fork_metas,
    with_presets,
)
from eth2spec.test.helpers.constants import (
    ALL_PRE_POST_FORKS,
    MINIMAL,
)
from eth2spec.test.helpers.fork_transition import (
    do_fork,
    transition_to_next_epoch_and_append_blocks,
    transition_until_fork,
)
from eth2spec.test.helpers.random import (
    slash_random_validators,
)


@with_fork_metas(
    [
        ForkMeta(pre_fork_name=pre, post_fork_name=post, fork_epoch=1)
        for pre, post in ALL_PRE_POST_FORKS
    ]
)
@with_presets(
    [MINIMAL],
    reason="only test with enough validators such that at least one exited index is not in sync committee",
)
def test_transition_with_one_fourth_slashed_active_validators_pre_fork(
    state, fork_epoch, spec, post_spec, pre_tag, post_tag
):
    """
    1/4 validators are slashed but still active at the fork transition.
    """
    # slash 1/4 validators
    slashed_indices = slash_random_validators(spec, state, rng=random.Random(5566), fraction=0.25)
    assert len(slashed_indices) > 0

    # check if some validators are slashed but still active
    for validator_index in slashed_indices:
        validator = state.validators[validator_index]
        assert validator.slashed
        assert spec.is_active_validator(validator, spec.get_current_epoch(state))
    assert not spec.is_in_inactivity_leak(state)

    transition_until_fork(spec, state, fork_epoch)

    assert spec.get_current_epoch(state) < fork_epoch

    yield "pre", state

    # irregular state transition to handle fork:
    state, _ = do_fork(state, spec, post_spec, fork_epoch, with_block=False)

    # ensure that some of the current sync committee members are slashed
    slashed_pubkeys = [state.validators[index].pubkey for index in slashed_indices]
    assert any(set(slashed_pubkeys).intersection(list(state.current_sync_committee.pubkeys)))
    assert any(set(slashed_pubkeys).difference(list(state.current_sync_committee.pubkeys)))

    # continue regular state transition with new spec into next epoch
    # since the proposer might have been slashed, here we only create blocks with non-slashed proposers
    blocks = []
    transition_to_next_epoch_and_append_blocks(
        post_spec,
        state,
        post_tag,
        blocks,
        only_last_block=True,
        ignoring_proposers=slashed_indices,
    )

    # check post state
    for validator in state.validators:
        assert post_spec.is_active_validator(validator, post_spec.get_current_epoch(state))
    assert not post_spec.is_in_inactivity_leak(state)

    yield "blocks", blocks
    yield "post", state
