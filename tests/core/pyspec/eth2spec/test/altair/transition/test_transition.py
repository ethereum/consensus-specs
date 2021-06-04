import random
from eth2spec.test.context import fork_transition_test
from eth2spec.test.helpers.constants import PHASE0, ALTAIR
from eth2spec.test.helpers.state import state_transition_and_sign_block, next_slot, next_epoch_via_signed_block
from eth2spec.test.helpers.block import build_empty_block_for_next_slot, build_empty_block, sign_block
from eth2spec.test.helpers.attestations import next_slots_with_attestations


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
    assert spec.get_current_epoch(state) == fork_epoch

    state = post_spec.upgrade_to_altair(state)

    assert state.fork.epoch == fork_epoch
    assert state.fork.previous_version == post_spec.config.GENESIS_FORK_VERSION
    assert state.fork.current_version == post_spec.config.ALTAIR_FORK_VERSION

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
    assert post_spec.get_current_epoch(state) == fork_epoch + 1

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
    assert post_spec.get_current_epoch(state) == fork_epoch + 1

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
    assert post_spec.get_current_epoch(state) == fork_epoch + 1

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
    assert post_spec.get_current_epoch(state) == fork_epoch + 1

    slots_with_blocks = [block.message.slot for block in blocks]
    assert len(slots_with_blocks) == 1
    assert slots_with_blocks[0] == last_slot

    yield "blocks", blocks
    yield "post", state


def _run_transition_test_with_attestations(state,
                                           fork_epoch,
                                           spec,
                                           post_spec,
                                           pre_tag,
                                           post_tag,
                                           participation_fn=None,
                                           expect_finality=True):
    yield "pre", state

    current_epoch = spec.get_current_epoch(state)
    assert current_epoch < fork_epoch
    assert current_epoch == spec.GENESIS_EPOCH

    # skip genesis epoch to avoid dealing with some edge cases...
    block = next_epoch_via_signed_block(spec, state)

    # regular state transition until fork:
    fill_cur_epoch = False
    fill_prev_epoch = True
    blocks = [pre_tag(block)]
    current_epoch = spec.get_current_epoch(state)
    for _ in range(current_epoch, fork_epoch - 1):
        _, blocks_in_epoch, state = next_slots_with_attestations(
            spec,
            state,
            spec.SLOTS_PER_EPOCH,
            fill_cur_epoch,
            fill_prev_epoch,
            participation_fn=participation_fn,
        )
        blocks.extend([pre_tag(block) for block in blocks_in_epoch])

    _, blocks_in_epoch, state = next_slots_with_attestations(
        spec,
        state,
        spec.SLOTS_PER_EPOCH - 1,
        fill_cur_epoch,
        fill_prev_epoch,
        participation_fn=participation_fn,
    )
    blocks.extend([pre_tag(block) for block in blocks_in_epoch])
    assert spec.get_current_epoch(state) == fork_epoch - 1
    assert (state.slot + 1) % spec.SLOTS_PER_EPOCH == 0

    # irregular state transition to handle fork:
    state, block = _do_altair_fork(state, spec, post_spec, fork_epoch)
    blocks.append(post_tag(block))

    # continue regular state transition with new spec into next epoch
    for _ in range(4):
        _, blocks_in_epoch, state = next_slots_with_attestations(
            post_spec,
            state,
            post_spec.SLOTS_PER_EPOCH,
            fill_cur_epoch,
            fill_prev_epoch,
            participation_fn=participation_fn,
        )
        blocks.extend([post_tag(block) for block in blocks_in_epoch])

    assert state.slot % post_spec.SLOTS_PER_EPOCH == 0
    assert post_spec.get_current_epoch(state) == fork_epoch + 4

    if expect_finality:
        assert state.current_justified_checkpoint.epoch == fork_epoch + 2
        assert state.finalized_checkpoint.epoch == fork_epoch
    else:
        assert state.current_justified_checkpoint.epoch == spec.GENESIS_EPOCH
        assert state.finalized_checkpoint.epoch == spec.GENESIS_EPOCH

    assert len(blocks) == (fork_epoch + 3) * post_spec.SLOTS_PER_EPOCH + 1
    assert len(blocks) == len(set(blocks))

    blocks_without_attestations = [block for block in blocks if len(block.message.body.attestations) == 0]
    assert len(blocks_without_attestations) == 2
    slots_without_attestations = [b.message.slot for b in blocks_without_attestations]

    assert set(slots_without_attestations) == set([spec.SLOTS_PER_EPOCH, fork_epoch * spec.SLOTS_PER_EPOCH])

    yield "blocks", blocks
    yield "post", state


@fork_transition_test(PHASE0, ALTAIR, fork_epoch=3)
def test_transition_with_finality(state, fork_epoch, spec, post_spec, pre_tag, post_tag):
    """
    Transition from the initial ``state`` to the epoch after the ``fork_epoch``,
    including attestations so as to produce finality through the fork boundary.
    """
    yield from _run_transition_test_with_attestations(state, fork_epoch, spec, post_spec, pre_tag, post_tag)


@fork_transition_test(PHASE0, ALTAIR, fork_epoch=3)
def test_transition_with_random_three_quarters_participation(state, fork_epoch, spec, post_spec, pre_tag, post_tag):
    """
    Transition from the initial ``state`` to the epoch after the ``fork_epoch``,
    including attestations so as to produce finality through the fork boundary.
    """
    rng = random.Random(1337)

    def _drop_random_quarter(_slot, _index, indices):
        # still finalize, but drop some attestations
        committee_len = len(indices)
        assert committee_len >= 4
        filter_len = committee_len // 4
        participant_count = committee_len - filter_len
        return rng.sample(indices, participant_count)

    yield from _run_transition_test_with_attestations(
        state,
        fork_epoch,
        spec,
        post_spec,
        pre_tag,
        post_tag,
        participation_fn=_drop_random_quarter
    )


@fork_transition_test(PHASE0, ALTAIR, fork_epoch=3)
def test_transition_with_random_half_participation(state, fork_epoch, spec, post_spec, pre_tag, post_tag):
    rng = random.Random(2020)

    def _drop_random_half(_slot, _index, indices):
        # drop enough attestations to not finalize
        committee_len = len(indices)
        assert committee_len >= 2
        filter_len = committee_len // 2
        participant_count = committee_len - filter_len
        return rng.sample(indices, participant_count)

    yield from _run_transition_test_with_attestations(
        state,
        fork_epoch,
        spec,
        post_spec,
        pre_tag,
        post_tag,
        participation_fn=_drop_random_half,
        expect_finality=False
    )


@fork_transition_test(PHASE0, ALTAIR, fork_epoch=2)
def test_transition_with_no_attestations_until_after_fork(state, fork_epoch, spec, post_spec, pre_tag, post_tag):
    """
    Transition from the initial ``state`` to the ``fork_epoch`` with no attestations,
    then transition forward with enough attestations to finalize the fork epoch.
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

    # continue regular state transition but add attestations
    # for enough epochs to finalize the ``fork_epoch``
    block = next_epoch_via_signed_block(post_spec, state)
    blocks.append(post_tag(block))
    for _ in range(4):
        _, blocks_in_epoch, state = next_slots_with_attestations(
            post_spec,
            state,
            post_spec.SLOTS_PER_EPOCH,
            False,
            True,
        )
        blocks.extend([post_tag(block) for block in blocks_in_epoch])

    assert state.slot % post_spec.SLOTS_PER_EPOCH == 0
    assert post_spec.get_current_epoch(state) == fork_epoch + 5

    assert state.current_justified_checkpoint.epoch == fork_epoch + 3
    assert state.finalized_checkpoint.epoch == fork_epoch + 1

    yield "blocks", blocks
    yield "post", state
