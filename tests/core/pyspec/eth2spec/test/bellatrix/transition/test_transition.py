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
