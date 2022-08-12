from eth2spec.test.helpers.random import (
    randomize_state,
)
from eth2spec.test.context import (
    ForkMeta,
    with_fork_metas,
)
from eth2spec.test.helpers.constants import (
    AFTER_BELLATRIX_PRE_POST_FORKS,
)
from eth2spec.test.helpers.fork_transition import (
    do_fork,
    transition_to_next_epoch_and_append_blocks,
    transition_until_fork,
)


@with_fork_metas([
    ForkMeta(pre_fork_name=pre, post_fork_name=post, fork_epoch=2) for pre, post in AFTER_BELLATRIX_PRE_POST_FORKS
])
def test_sample_transition(state, fork_epoch, spec, post_spec, pre_tag, post_tag):
    transition_until_fork(spec, state, fork_epoch)

    # check pre state
    assert spec.get_current_epoch(state) < fork_epoch

    yield "pre", state

    # irregular state transition to handle fork:
    blocks = []
    state, block = do_fork(state, spec, post_spec, fork_epoch)
    blocks.append(post_tag(block))

    # continue regular state transition with new spec into next epoch
    transition_to_next_epoch_and_append_blocks(post_spec, state, post_tag, blocks, only_last_block=True)

    yield "blocks", blocks
    yield "post", state


@with_fork_metas([
    ForkMeta(pre_fork_name=pre, post_fork_name=post, fork_epoch=8) for pre, post in AFTER_BELLATRIX_PRE_POST_FORKS
])
def test_transition_randomized_state(state, fork_epoch, spec, post_spec, pre_tag, post_tag):
    randomize_state(spec, state)

    transition_until_fork(spec, state, fork_epoch)

    # check pre state
    assert spec.get_current_epoch(state) < fork_epoch

    yield "pre", state

    # irregular state transition to handle fork:
    blocks = []
    # since there are slashed validators, set with_block=False here
    state, _ = do_fork(state, spec, post_spec, fork_epoch, with_block=False)
    slashed_indices = [index for index, validator in enumerate(state.validators) if validator.slashed]

    # continue regular state transition with new spec into next epoch
    transition_to_next_epoch_and_append_blocks(
        post_spec,
        state,
        post_tag,
        blocks,
        only_last_block=True,
        ignoring_proposers=slashed_indices,
    )

    yield "blocks", blocks
    yield "post", state
