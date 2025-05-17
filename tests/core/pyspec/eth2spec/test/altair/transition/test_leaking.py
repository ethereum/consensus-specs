from eth2spec.test.context import (
    ForkMeta,
    with_fork_metas,
)
from eth2spec.test.helpers.constants import (
    ALL_PRE_POST_FORKS,
)
from eth2spec.test.helpers.fork_transition import (
    do_fork,
    transition_to_next_epoch_and_append_blocks,
    transition_until_fork,
)


@with_fork_metas(
    [
        ForkMeta(pre_fork_name=pre, post_fork_name=post, fork_epoch=7)
        for pre, post in ALL_PRE_POST_FORKS
    ]
)
def test_transition_with_leaking_pre_fork(state, fork_epoch, spec, post_spec, pre_tag, post_tag):
    """
    Leaking starts at epoch 6 (MIN_EPOCHS_TO_INACTIVITY_PENALTY + 2).
    The leaking starts before the fork transition in this case.
    """
    transition_until_fork(spec, state, fork_epoch)

    assert spec.is_in_inactivity_leak(state)
    assert spec.get_current_epoch(state) < fork_epoch

    yield "pre", state

    # irregular state transition to handle fork:
    blocks = []
    state, block = do_fork(state, spec, post_spec, fork_epoch)
    blocks.append(post_tag(block))

    # check post transition state
    assert spec.is_in_inactivity_leak(state)

    # continue regular state transition with new spec into next epoch
    transition_to_next_epoch_and_append_blocks(
        post_spec, state, post_tag, blocks, only_last_block=True
    )

    yield "blocks", blocks
    yield "post", state


@with_fork_metas(
    [
        ForkMeta(pre_fork_name=pre, post_fork_name=post, fork_epoch=6)
        for pre, post in ALL_PRE_POST_FORKS
    ]
)
def test_transition_with_leaking_at_fork(state, fork_epoch, spec, post_spec, pre_tag, post_tag):
    """
    Leaking starts at epoch 6 (MIN_EPOCHS_TO_INACTIVITY_PENALTY + 2).
    The leaking starts at the fork transition in this case.
    """
    transition_until_fork(spec, state, fork_epoch)

    assert not spec.is_in_inactivity_leak(state)
    assert spec.get_current_epoch(state) < fork_epoch

    yield "pre", state

    # irregular state transition to handle fork:
    blocks = []
    state, block = do_fork(state, spec, post_spec, fork_epoch)
    blocks.append(post_tag(block))

    # check post transition state
    assert spec.is_in_inactivity_leak(state)

    # continue regular state transition with new spec into next epoch
    transition_to_next_epoch_and_append_blocks(
        post_spec, state, post_tag, blocks, only_last_block=True
    )

    yield "blocks", blocks
    yield "post", state
