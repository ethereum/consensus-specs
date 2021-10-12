import random
from eth2spec.test.context import fork_transition_test
from eth2spec.test.helpers.constants import PHASE0, ALTAIR
from eth2spec.test.helpers.state import (
    next_epoch_via_signed_block,
    next_slot,
    state_transition_and_sign_block,
    transition_to,
)
from eth2spec.test.helpers.block import build_empty_block_for_next_slot, build_empty_block, sign_block
from eth2spec.test.helpers.deposits import (
    prepare_state_and_deposit,
)
from eth2spec.test.helpers.attestations import next_slots_with_attestations
from eth2spec.test.helpers.random import set_some_new_deposits
from eth2spec.test.helpers.inactivity_scores import (
    slash_some_validators_for_inactivity_scores_test,
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


def _state_transition_across_slots_with_ignoring_proposers(spec, state, to_slot, ignoring_proposers):
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


def _do_altair_fork(state, spec, post_spec, fork_epoch, with_block=True, deposits=None):
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


def _set_validators_exit_epoch(spec, state, exit_epoch, rng=random.Random(40404040), fraction=0.25):
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


def _transition_until_fork(spec, state, fork_epoch):
    to_slot = fork_epoch * spec.SLOTS_PER_EPOCH - 1
    transition_to(spec, state, to_slot)


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


@fork_transition_test(PHASE0, ALTAIR, fork_epoch=1)
def test_transition_with_one_fourth_slashed_active_validators_pre_fork(
        state, fork_epoch, spec, post_spec, pre_tag, post_tag):
    """
    1/4 validators are slashed but still active at the fork transition.
    """
    # slash 1/4 validators
    slashed_indices = slash_some_validators_for_inactivity_scores_test(
        spec, state, rng=random.Random(5566), fraction=0.25)
    assert len(slashed_indices) > 0

    # check if some validators are slashed but still active
    for validator_index in slashed_indices:
        validator = state.validators[validator_index]
        assert validator.slashed
        assert spec.is_active_validator(validator, spec.get_current_epoch(state))
    assert not spec.is_in_inactivity_leak(state)

    _transition_until_fork(spec, state, fork_epoch)

    assert spec.get_current_epoch(state) < fork_epoch

    yield "pre", state

    # irregular state transition to handle fork:
    blocks = []
    state, block = _do_altair_fork(state, spec, post_spec, fork_epoch)
    blocks.append(post_tag(block))

    # ensure that some of the current sync committee members are the slashed
    slashed_pubkeys = [state.validators[index].pubkey for index in slashed_indices]
    assert any(set(slashed_pubkeys).intersection(list(state.current_sync_committee.pubkeys)))

    # continue regular state transition with new spec into next epoch
    to_slot = post_spec.SLOTS_PER_EPOCH + state.slot
    # since the proposer might have been slashed, here we only create blocks with non-slashed proposers
    blocks.extend([
        post_tag(block) for block in
        _state_transition_across_slots_with_ignoring_proposers(post_spec, state, to_slot, slashed_indices)
    ])

    # check post state
    for validator in state.validators:
        assert post_spec.is_active_validator(validator, post_spec.get_current_epoch(state))
    assert not post_spec.is_in_inactivity_leak(state)

    yield "blocks", blocks
    yield "post", state


@fork_transition_test(PHASE0, ALTAIR, fork_epoch=2)
def test_transition_with_one_fourth_exiting_validators_exit_post_fork(
        state, fork_epoch, spec, post_spec, pre_tag, post_tag):
    """
    1/4 exiting but still active validators at the fork transition.
    """
    exited_indices = _set_validators_exit_epoch(spec, state, exit_epoch=10, rng=random.Random(5566), fraction=0.25)

    _transition_until_fork(spec, state, fork_epoch)

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
    state, block = _do_altair_fork(state, spec, post_spec, fork_epoch)
    blocks.append(post_tag(block))

    # ensure that some of the current sync committee members are exiting
    exited_pubkeys = [state.validators[index].pubkey for index in exited_indices]
    assert any(set(exited_pubkeys).intersection(list(state.current_sync_committee.pubkeys)))

    # continue regular state transition with new spec into next epoch
    to_slot = post_spec.SLOTS_PER_EPOCH + state.slot
    blocks.extend([
        post_tag(block) for block in
        _state_transition_across_slots(post_spec, state, to_slot)
    ])

    # check state
    for index in exited_indices:
        validator = state.validators[index]
        assert not validator.slashed
        assert post_spec.is_active_validator(validator, post_spec.get_current_epoch(state))
    assert not post_spec.is_in_inactivity_leak(state)

    yield "blocks", blocks
    yield "post", state


@fork_transition_test(PHASE0, ALTAIR, fork_epoch=2)
def test_transition_with_one_fourth_exiting_validators_exit_at_fork(
        state, fork_epoch, spec, post_spec, pre_tag, post_tag):
    """
    1/4 exiting but still active validators at the fork transition.
    """
    exited_indices = _set_validators_exit_epoch(spec, state, exit_epoch=2, rng=random.Random(5566), fraction=0.25)

    _transition_until_fork(spec, state, fork_epoch)

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
    state, block = _do_altair_fork(state, spec, post_spec, fork_epoch)
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
    to_slot = post_spec.SLOTS_PER_EPOCH + state.slot
    blocks.extend([
        post_tag(block) for block in
        _state_transition_across_slots(post_spec, state, to_slot)
    ])

    yield "blocks", blocks
    yield "post", state


@fork_transition_test(PHASE0, ALTAIR, fork_epoch=7)
def test_transition_with_leaking_pre_fork(state, fork_epoch, spec, post_spec, pre_tag, post_tag):
    """
    Leaking starts at epoch 6 (MIN_EPOCHS_TO_INACTIVITY_PENALTY + 2).
    The leaking starts before the fork transition in this case.
    """
    _transition_until_fork(spec, state, fork_epoch)

    assert spec.is_in_inactivity_leak(state)
    assert spec.get_current_epoch(state) < fork_epoch

    yield "pre", state

    # irregular state transition to handle fork:
    blocks = []
    state, block = _do_altair_fork(state, spec, post_spec, fork_epoch)
    blocks.append(post_tag(block))

    # check post transition state
    assert spec.is_in_inactivity_leak(state)

    # continue regular state transition with new spec into next epoch
    to_slot = post_spec.SLOTS_PER_EPOCH + state.slot
    blocks.extend([
        post_tag(block) for block in
        _state_transition_across_slots(post_spec, state, to_slot)
    ])

    yield "blocks", blocks
    yield "post", state


@fork_transition_test(PHASE0, ALTAIR, fork_epoch=6)
def test_transition_with_leaking_at_fork(state, fork_epoch, spec, post_spec, pre_tag, post_tag):
    """
    Leaking starts at epoch 6 (MIN_EPOCHS_TO_INACTIVITY_PENALTY + 2).
    The leaking starts at the fork transition in this case.
    """
    _transition_until_fork(spec, state, fork_epoch)

    assert not spec.is_in_inactivity_leak(state)
    assert spec.get_current_epoch(state) < fork_epoch

    yield "pre", state

    # irregular state transition to handle fork:
    blocks = []
    state, block = _do_altair_fork(state, spec, post_spec, fork_epoch)
    blocks.append(post_tag(block))

    # check post transition state
    assert spec.is_in_inactivity_leak(state)

    # continue regular state transition with new spec into next epoch
    to_slot = post_spec.SLOTS_PER_EPOCH + state.slot
    blocks.extend([
        post_tag(block) for block in
        _state_transition_across_slots(post_spec, state, to_slot)
    ])

    yield "blocks", blocks
    yield "post", state


@fork_transition_test(PHASE0, ALTAIR, fork_epoch=5)
def test_transition_with_leaking_post_fork(state, fork_epoch, spec, post_spec, pre_tag, post_tag):
    """
    Leaking starts at epoch 6 (MIN_EPOCHS_TO_INACTIVITY_PENALTY + 2).
    The leaking starts after the fork transition in this case.
    """
    _transition_until_fork(spec, state, fork_epoch)

    assert not spec.is_in_inactivity_leak(state)
    assert spec.get_current_epoch(state) < fork_epoch

    yield "pre", state

    # irregular state transition to handle fork:
    blocks = []
    state, block = _do_altair_fork(state, spec, post_spec, fork_epoch)
    blocks.append(post_tag(block))

    # check post transition state
    assert not spec.is_in_inactivity_leak(state)

    # continue regular state transition with new spec into next epoch
    to_slot = post_spec.SLOTS_PER_EPOCH + state.slot
    blocks.extend([
        post_tag(block) for block in
        _state_transition_across_slots(post_spec, state, to_slot)
    ])

    # check state again
    assert spec.is_in_inactivity_leak(state)

    yield "blocks", blocks
    yield "post", state


@fork_transition_test(PHASE0, ALTAIR, fork_epoch=10)
def test_transition_with_non_empty_activation_queue(state, fork_epoch, spec, post_spec, pre_tag, post_tag):
    """
    Create some deposits before the transition
    """
    _transition_until_fork(spec, state, fork_epoch)

    _, queuing_indices = set_some_new_deposits(spec, state, rng=random.Random(5566))

    assert spec.get_current_epoch(state) < fork_epoch
    assert len(queuing_indices) > 0
    for validator_index in queuing_indices:
        assert not spec.is_active_validator(state.validators[validator_index], spec.get_current_epoch(state))

    yield "pre", state

    # irregular state transition to handle fork:
    blocks = []
    state, block = _do_altair_fork(state, spec, post_spec, fork_epoch)
    blocks.append(post_tag(block))

    # continue regular state transition with new spec into next epoch
    to_slot = post_spec.SLOTS_PER_EPOCH + state.slot
    blocks.extend([
        post_tag(block) for block in
        _state_transition_across_slots(post_spec, state, to_slot)
    ])

    yield "blocks", blocks
    yield "post", state


@fork_transition_test(PHASE0, ALTAIR, fork_epoch=10)
def test_transition_with_deposit_at_fork(state, fork_epoch, spec, post_spec, pre_tag, post_tag):
    """
    Create a deposit at the transition
    """
    _transition_until_fork(spec, state, fork_epoch)

    yield "pre", state

    # create a new deposit
    validator_index = len(state.validators)
    amount = post_spec.MAX_EFFECTIVE_BALANCE
    deposit = prepare_state_and_deposit(post_spec, state, validator_index, amount, signed=True)

    # irregular state transition to handle fork:
    state, block = _do_altair_fork(state, spec, post_spec, fork_epoch, deposits=[deposit])
    blocks = []
    blocks.append(post_tag(block))

    assert not post_spec.is_active_validator(state.validators[validator_index], post_spec.get_current_epoch(state))

    # continue regular state transition with new spec into next epoch
    to_slot = post_spec.SLOTS_PER_EPOCH + state.slot
    blocks.extend([
        post_tag(block) for block in
        _state_transition_across_slots(post_spec, state, to_slot)
    ])

    # finalize activation_eligibility_epoch
    _, blocks_in_epoch, state = next_slots_with_attestations(
        post_spec,
        state,
        spec.SLOTS_PER_EPOCH * 2,
        fill_cur_epoch=True,
        fill_prev_epoch=True,
    )
    blocks.extend([pre_tag(block) for block in blocks_in_epoch])
    assert state.finalized_checkpoint.epoch == state.validators[validator_index].activation_eligibility_epoch

    # continue regular state transition with new spec into next epoch
    to_slot = post_spec.SLOTS_PER_EPOCH + state.slot
    blocks.extend([
        post_tag(block) for block in
        _state_transition_across_slots(post_spec, state, to_slot)
    ])

    assert state.validators[validator_index].activation_epoch < post_spec.FAR_FUTURE_EPOCH

    to_slot = state.validators[validator_index].activation_epoch * post_spec.SLOTS_PER_EPOCH
    blocks.extend([
        post_tag(block) for block in
        _state_transition_across_slots(post_spec, state, to_slot)
    ])
    assert post_spec.is_active_validator(state.validators[validator_index], post_spec.get_current_epoch(state))

    yield "blocks", blocks
    yield "post", state
