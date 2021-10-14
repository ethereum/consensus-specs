import random
from eth2spec.test.context import fork_transition_test
from eth2spec.test.helpers.constants import PHASE0, ALTAIR
from eth2spec.test.helpers.attestations import next_slots_with_attestations
from eth2spec.test.helpers.deposits import prepare_state_and_deposit
from eth2spec.test.helpers.fork_transition import (
    do_altair_fork,
    state_transition_across_slots,
    transition_until_fork,
    transition_to_next_epoch_and_append_blocks,
)
from eth2spec.test.helpers.random import (
    exit_random_validators,
    set_some_new_deposits,
)
from eth2spec.test.helpers.voluntary_exits import prepare_signed_exits


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


@fork_transition_test(PHASE0, ALTAIR, fork_epoch=260)
def test_transition_with_voluntary_exit_at_fork(state, fork_epoch, spec, post_spec, pre_tag, post_tag):
    """
    Create a voluntary exit at the transition.
    fork_epoch=260 because mainnet `SHARD_COMMITTEE_PERIOD` is 256 epochs.
    """
    # Fast forward to the future epoch so that validator can do voluntary exit
    state.slot = spec.config.SHARD_COMMITTEE_PERIOD * spec.SLOTS_PER_EPOCH
    transition_until_fork(spec, state, fork_epoch)

    yield "pre", state

    validator_index = 0
    signed_exits = prepare_signed_exits(spec, state, [validator_index])
    operation_dict = {'voluntary_exits': signed_exits}

    # irregular state transition to handle fork:
    state, block = do_altair_fork(state, spec, post_spec, fork_epoch, operation_dict=operation_dict)
    blocks = []
    blocks.append(post_tag(block))

    validator = state.validators[validator_index]
    assert validator.exit_epoch < post_spec.FAR_FUTURE_EPOCH

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

    _, queuing_indices = set_some_new_deposits(spec, state, rng=random.Random(5566))

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


@fork_transition_test(PHASE0, ALTAIR, fork_epoch=2)
def test_transition_with_deposit_at_fork(state, fork_epoch, spec, post_spec, pre_tag, post_tag):
    """
    Create a deposit at the transition
    """
    transition_until_fork(spec, state, fork_epoch)

    yield "pre", state

    # create a new deposit
    validator_index = len(state.validators)
    amount = post_spec.MAX_EFFECTIVE_BALANCE
    deposit = prepare_state_and_deposit(post_spec, state, validator_index, amount, signed=True)
    deposit_old = prepare_state_and_deposit(spec, state, validator_index, amount, signed=True)
    # sanity check: deposit operation is independent of spec fork versions
    assert deposit_old == deposit
    operation_dict = {'deposits': [deposit]}
    # irregular state transition to handle fork:
    state, block = do_altair_fork(state, spec, post_spec, fork_epoch, operation_dict=operation_dict)
    blocks = []
    blocks.append(post_tag(block))

    assert not post_spec.is_active_validator(state.validators[validator_index], post_spec.get_current_epoch(state))

    # continue regular state transition with new spec into next epoch
    transition_to_next_epoch_and_append_blocks(post_spec, state, post_tag, blocks)

    # finalize activation_eligibility_epoch
    _, blocks_in_epoch, state = next_slots_with_attestations(
        post_spec,
        state,
        spec.SLOTS_PER_EPOCH * 2,
        fill_cur_epoch=True,
        fill_prev_epoch=True,
    )
    blocks.extend([post_tag(block) for block in blocks_in_epoch])
    assert state.finalized_checkpoint.epoch == state.validators[validator_index].activation_eligibility_epoch

    # continue regular state transition with new spec into next epoch
    transition_to_next_epoch_and_append_blocks(post_spec, state, post_tag, blocks, only_last_block=True)

    assert state.validators[validator_index].activation_epoch < post_spec.FAR_FUTURE_EPOCH

    to_slot = state.validators[validator_index].activation_epoch * post_spec.SLOTS_PER_EPOCH
    blocks.extend([
        post_tag(block) for block in
        state_transition_across_slots(post_spec, state, to_slot)
    ])
    assert post_spec.is_active_validator(state.validators[validator_index], post_spec.get_current_epoch(state))

    yield "blocks", blocks
    yield "post", state
