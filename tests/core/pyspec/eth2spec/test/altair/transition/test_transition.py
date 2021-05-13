from eth2spec.test.context import fork_transition_test
from eth2spec.test.helpers.constants import PHASE0, ALTAIR
from eth2spec.test.helpers.state import state_transition_and_sign_block, next_slot
from eth2spec.test.helpers.block import build_empty_block_for_next_slot, build_empty_block, sign_block


def _state_transition_and_sign_block_at_slot(spec, state):
    """
    Cribbed from ``transition_unsigned_block`` helper
    where the early parts of the state transition have already
    been applied to ``state``.

    Used to produce a block during an irregular state transition.
    """
    block = build_empty_block(spec, state)

    assert state.latest_block_header.slot < block.slot
    assert state.slot == block.slot
    spec.process_block(state, block)
    block.state_root = state.hash_tree_root()
    return sign_block(spec, state, block)


def _all_blocks(_):
    return True


def _skip_slots(*slots):
    """
    Skip making a block if its slot is
    passed as an argument to this filter
    """
    def f(state_at_prior_slot):
        return state_at_prior_slot.slot + 1 not in slots
    return f


def _no_blocks(_):
    return False


def _only_at(slot):
    """
    Only produce a block if its slot is ``slot``.
    """
    def f(state_at_prior_slot):
        return state_at_prior_slot.slot + 1 == slot
    return f


def _state_transition_across_slots(spec, state, to_slot, block_filter=_all_blocks):
    assert state.slot < to_slot
    while state.slot < to_slot:
        should_make_block = block_filter(state)
        if should_make_block:
            block = build_empty_block_for_next_slot(spec, state)
            signed_block = state_transition_and_sign_block(spec, state, block)
            yield signed_block
        else:
            next_slot(spec, state)


def _do_altair_fork(state, spec, post_spec, fork_epoch, with_block=True):
    spec.process_slots(state, state.slot + 1)

    assert state.slot % spec.SLOTS_PER_EPOCH == 0
    assert spec.compute_epoch_at_slot(state.slot) == fork_epoch

    state = post_spec.upgrade_to_altair(state)

    assert state.fork.epoch == fork_epoch
    assert state.fork.previous_version == post_spec.GENESIS_FORK_VERSION
    assert state.fork.current_version == post_spec.ALTAIR_FORK_VERSION

    if with_block:
        return state, _state_transition_and_sign_block_at_slot(post_spec, state)
    else:
        return state, None


@fork_transition_test(PHASE0, ALTAIR, fork_epoch=2)
def test_normal_transition(state, fork_epoch, spec, post_spec, pre_tag, post_tag):
    """
    Transition from the initial ``state`` to the epoch after the ``fork_epoch``,
    producing blocks for every slot along the way.
    """
    yield "pre", state

    assert spec.get_current_epoch(state) < fork_epoch

    # regular state transition until fork:
    to_slot = fork_epoch * spec.SLOTS_PER_EPOCH - 1
    blocks = []
    blocks.extend([
        pre_tag(block) for block in
        _state_transition_across_slots(spec, state, to_slot)
    ])

    # irregular state transition to handle fork:
    state, block = _do_altair_fork(state, spec, post_spec, fork_epoch)
    blocks.append(post_tag(block))

    # continue regular state transition with new spec into next epoch
    to_slot = post_spec.SLOTS_PER_EPOCH + state.slot
    blocks.extend([
        post_tag(block) for block in
        _state_transition_across_slots(post_spec, state, to_slot)
    ])

    assert state.slot % post_spec.SLOTS_PER_EPOCH == 0
    assert post_spec.compute_epoch_at_slot(state.slot) == fork_epoch + 1

    slots_with_blocks = [block.message.slot for block in blocks]
    assert len(set(slots_with_blocks)) == len(slots_with_blocks)
    assert set(range(1, state.slot + 1)) == set(slots_with_blocks)

    yield "blocks", blocks
    yield "post", state


@fork_transition_test(PHASE0, ALTAIR, fork_epoch=2)
def test_transition_missing_first_post_block(state, fork_epoch, spec, post_spec, pre_tag, post_tag):
    """
    Transition from the initial ``state`` to the epoch after the ``fork_epoch``,
    producing blocks for every slot along the way except for the first block
    of the new fork.
    """
    yield "pre", state

    assert spec.get_current_epoch(state) < fork_epoch

    # regular state transition until fork:
    to_slot = fork_epoch * spec.SLOTS_PER_EPOCH - 1
    blocks = []
    blocks.extend([
        pre_tag(block) for block in
        _state_transition_across_slots(spec, state, to_slot)
    ])

    # irregular state transition to handle fork:
    state, _ = _do_altair_fork(state, spec, post_spec, fork_epoch, with_block=False)

    # continue regular state transition with new spec into next epoch
    to_slot = post_spec.SLOTS_PER_EPOCH + state.slot
    blocks.extend([
        post_tag(block) for block in
        _state_transition_across_slots(post_spec, state, to_slot)
    ])

    assert state.slot % post_spec.SLOTS_PER_EPOCH == 0
    assert post_spec.compute_epoch_at_slot(state.slot) == fork_epoch + 1

    slots_with_blocks = [block.message.slot for block in blocks]
    assert len(set(slots_with_blocks)) == len(slots_with_blocks)
    expected_slots = set(range(1, state.slot + 1)).difference(set([fork_epoch * spec.SLOTS_PER_EPOCH]))
    assert expected_slots == set(slots_with_blocks)

    yield "blocks", blocks
    yield "post", state


@fork_transition_test(PHASE0, ALTAIR, fork_epoch=2)
def test_transition_missing_last_pre_fork_block(state, fork_epoch, spec, post_spec, pre_tag, post_tag):
    """
    Transition from the initial ``state`` to the epoch after the ``fork_epoch``,
    producing blocks for every slot along the way except for the last block
    of the old fork.
    """
    yield "pre", state

    assert spec.get_current_epoch(state) < fork_epoch

    # regular state transition until fork:
    last_slot_of_pre_fork = fork_epoch * spec.SLOTS_PER_EPOCH - 1
    to_slot = last_slot_of_pre_fork
    blocks = []
    blocks.extend([
        pre_tag(block) for block in
        _state_transition_across_slots(spec, state, to_slot, block_filter=_skip_slots(last_slot_of_pre_fork))
    ])

    # irregular state transition to handle fork:
    state, block = _do_altair_fork(state, spec, post_spec, fork_epoch)
    blocks.append(post_tag(block))

    # continue regular state transition with new spec into next epoch
    to_slot = post_spec.SLOTS_PER_EPOCH + state.slot
    blocks.extend([
        post_tag(block) for block in
        _state_transition_across_slots(post_spec, state, to_slot)
    ])

    assert state.slot % post_spec.SLOTS_PER_EPOCH == 0
    assert post_spec.compute_epoch_at_slot(state.slot) == fork_epoch + 1

    slots_with_blocks = [block.message.slot for block in blocks]
    assert len(set(slots_with_blocks)) == len(slots_with_blocks)
    expected_slots = set(range(1, state.slot + 1)).difference(set([last_slot_of_pre_fork]))
    assert expected_slots == set(slots_with_blocks)

    yield "blocks", blocks
    yield "post", state


@fork_transition_test(PHASE0, ALTAIR, fork_epoch=2)
def test_transition_only_blocks_post_fork(state, fork_epoch, spec, post_spec, pre_tag, post_tag):
    """
    Transition from the initial ``state`` to the epoch after the ``fork_epoch``,
    skipping blocks for every slot along the way except for the first block
    in the ending epoch.
    """
    yield "pre", state

    assert spec.get_current_epoch(state) < fork_epoch

    # regular state transition until fork:
    last_slot_of_pre_fork = fork_epoch * spec.SLOTS_PER_EPOCH - 1
    to_slot = last_slot_of_pre_fork
    blocks = []
    blocks.extend([
        pre_tag(block) for block in
        _state_transition_across_slots(spec, state, to_slot, block_filter=_no_blocks)
    ])

    # irregular state transition to handle fork:
    state, _ = _do_altair_fork(state, spec, post_spec, fork_epoch, with_block=False)

    # continue regular state transition with new spec into next epoch
    to_slot = post_spec.SLOTS_PER_EPOCH + state.slot
    last_slot = (fork_epoch + 1) * post_spec.SLOTS_PER_EPOCH
    blocks.extend([
        post_tag(block) for block in
        _state_transition_across_slots(post_spec, state, to_slot, block_filter=_only_at(last_slot))
    ])

    assert state.slot % post_spec.SLOTS_PER_EPOCH == 0
    assert post_spec.compute_epoch_at_slot(state.slot) == fork_epoch + 1

    slots_with_blocks = [block.message.slot for block in blocks]
    assert len(slots_with_blocks) == 1
    assert slots_with_blocks[0] == last_slot

    yield "blocks", blocks
    yield "post", state
