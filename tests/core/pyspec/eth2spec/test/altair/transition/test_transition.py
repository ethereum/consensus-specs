from eth2spec.test.context import fork_transition_test
from eth2spec.test.helpers.constants import PHASE0, ALTAIR
from eth2spec.test.helpers.state import state_transition_and_sign_block
from eth2spec.test.helpers.block import build_empty_block_for_next_slot, build_empty_block, sign_block


def _state_transition_and_sign_block_at_slot(spec, state):
    """
    Cribbed from `transition_unsigned_block` helper
    where the early parts of the state transition have already
    been applied to `state`.

    Used to produce a block during an irregular state transition.
    """
    block = build_empty_block(spec, state)

    assert state.latest_block_header.slot < block.slot
    assert state.slot == block.slot
    spec.process_block(state, block)
    block.state_root = state.hash_tree_root()
    return sign_block(spec, state, block)


@fork_transition_test(PHASE0, ALTAIR, fork_epoch=2)
def test_normal_transition(state, fork_epoch, spec, post_spec, pre_tag, post_tag):
    yield "pre", state

    assert spec.get_current_epoch(state) < fork_epoch

    blocks = []
    # regular state transition until fork:
    for _ in range(state.slot, fork_epoch * spec.SLOTS_PER_EPOCH - 1):
        block = build_empty_block_for_next_slot(spec, state)
        signed_block = state_transition_and_sign_block(spec, state, block)
        blocks.append(pre_tag(signed_block))

    # irregular state transition to handle fork:
    spec.process_slots(state, state.slot + 1)

    assert state.slot % spec.SLOTS_PER_EPOCH == 0
    assert spec.compute_epoch_at_slot(state.slot) == fork_epoch

    state = post_spec.upgrade_to_altair(state)

    assert state.fork.epoch == fork_epoch
    assert state.fork.previous_version == post_spec.GENESIS_FORK_VERSION
    assert state.fork.current_version == post_spec.ALTAIR_FORK_VERSION

    signed_block = _state_transition_and_sign_block_at_slot(post_spec, state)
    blocks.append(post_tag(signed_block))

    # continue regular state transition with new spec into next epoch
    for _ in range(post_spec.SLOTS_PER_EPOCH):
        block = build_empty_block_for_next_slot(post_spec, state)
        signed_block = state_transition_and_sign_block(post_spec, state, block)
        blocks.append(post_tag(signed_block))

    assert state.slot % post_spec.SLOTS_PER_EPOCH == 0
    assert post_spec.compute_epoch_at_slot(state.slot) == fork_epoch + 1

    slots_with_blocks = [block.message.slot for block in blocks]
    assert len(set(slots_with_blocks)) == len(slots_with_blocks)
    assert set(range(1, state.slot + 1)) == set(slots_with_blocks)

    yield "blocks", blocks
    yield "post", state
