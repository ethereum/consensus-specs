from eth2spec.test.context import (
    with_capella_and_later, spec_state_test
)
from eth2spec.test.helpers.state import (
    state_transition_and_sign_block,
)
from eth2spec.test.helpers.block import (
    build_empty_block_for_next_slot,
    build_empty_block,
)
from eth2spec.test.helpers.bls_to_execution_changes import get_signed_address_change
from eth2spec.test.helpers.state import (
    next_slot,
)
from eth2spec.test.helpers.withdrawals import (
    set_validator_fully_withdrawable,
    set_validator_partially_withdrawable,
    prepare_expected_withdrawals,
)
from eth2spec.test.helpers.voluntary_exits import prepare_signed_exits


#
# BLSToExecutionChange
#

@with_capella_and_later
@spec_state_test
def test_success_bls_change(spec, state):
    index = 0
    signed_address_change = get_signed_address_change(spec, state, validator_index=index)
    pre_credentials = state.validators[index].withdrawal_credentials
    yield 'pre', state

    block = build_empty_block_for_next_slot(spec, state)
    block.body.bls_to_execution_changes.append(signed_address_change)

    signed_block = state_transition_and_sign_block(spec, state, block)

    yield 'blocks', [signed_block]
    yield 'post', state

    post_credentials = state.validators[index].withdrawal_credentials
    assert pre_credentials != post_credentials
    assert post_credentials[:1] == spec.ETH1_ADDRESS_WITHDRAWAL_PREFIX
    assert post_credentials[1:12] == b'\x00' * 11
    assert post_credentials[12:] == signed_address_change.message.to_execution_address


@with_capella_and_later
@spec_state_test
def test_success_exit_and_bls_change(spec, state):
    # move state forward SHARD_COMMITTEE_PERIOD epochs to allow for exit
    state.slot += spec.config.SHARD_COMMITTEE_PERIOD * spec.SLOTS_PER_EPOCH

    index = 0
    signed_address_change = get_signed_address_change(spec, state, validator_index=index)
    signed_exit = prepare_signed_exits(spec, state, [index])[0]

    yield 'pre', state

    block = build_empty_block_for_next_slot(spec, state)
    block.body.voluntary_exits.append(signed_exit)
    block.body.bls_to_execution_changes.append(signed_address_change)

    signed_block = state_transition_and_sign_block(spec, state, block)

    yield 'blocks', [signed_block]
    yield 'post', state

    validator = state.validators[index]
    balance = state.balances[index]
    current_epoch = spec.get_current_epoch(state)
    assert not spec.is_fully_withdrawable_validator(validator, balance, current_epoch)
    assert validator.withdrawable_epoch < spec.FAR_FUTURE_EPOCH
    assert spec.is_fully_withdrawable_validator(validator, balance, validator.withdrawable_epoch)


@with_capella_and_later
@spec_state_test
def test_invalid_duplicate_bls_changes_same_block(spec, state):
    index = 0
    signed_address_change = get_signed_address_change(spec, state, validator_index=index)
    yield 'pre', state

    block = build_empty_block_for_next_slot(spec, state)

    # Double BLSToExecutionChange of the same validator
    for _ in range(2):
        block.body.bls_to_execution_changes.append(signed_address_change)

    signed_block = state_transition_and_sign_block(spec, state, block, expect_fail=True)

    yield 'blocks', [signed_block]
    yield 'post', None


@with_capella_and_later
@spec_state_test
def test_invalid_two_bls_changes_of_different_addresses_same_validator_same_block(spec, state):
    index = 0

    signed_address_change_1 = get_signed_address_change(spec, state, validator_index=index,
                                                        to_execution_address=b'\x12' * 20)
    signed_address_change_2 = get_signed_address_change(spec, state, validator_index=index,
                                                        to_execution_address=b'\x34' * 20)
    assert signed_address_change_1 != signed_address_change_2

    yield 'pre', state

    block = build_empty_block_for_next_slot(spec, state)

    block.body.bls_to_execution_changes.append(signed_address_change_1)
    block.body.bls_to_execution_changes.append(signed_address_change_2)

    signed_block = state_transition_and_sign_block(spec, state, block, expect_fail=True)

    yield 'blocks', [signed_block]
    yield 'post', None


#
# Withdrawals
#

@with_capella_and_later
@spec_state_test
def test_full_withdrawal_in_epoch_transition(spec, state):
    index = 0
    current_epoch = spec.get_current_epoch(state)
    set_validator_fully_withdrawable(spec, state, index, current_epoch)
    assert len(spec.get_expected_withdrawals(state)) == 1

    yield 'pre', state

    # trigger epoch transition
    block = build_empty_block(spec, state, state.slot + spec.SLOTS_PER_EPOCH)
    signed_block = state_transition_and_sign_block(spec, state, block)

    yield 'blocks', [signed_block]
    yield 'post', state

    assert state.balances[index] == 0
    assert len(spec.get_expected_withdrawals(state)) == 0


@with_capella_and_later
@spec_state_test
def test_partial_withdrawal_in_epoch_transition(spec, state):
    index = state.next_withdrawal_index
    set_validator_partially_withdrawable(spec, state, index, excess_balance=1000000000000)
    pre_balance = state.balances[index]

    assert len(spec.get_expected_withdrawals(state)) == 1

    yield 'pre', state

    # trigger epoch transition
    block = build_empty_block(spec, state, state.slot + spec.SLOTS_PER_EPOCH)
    signed_block = state_transition_and_sign_block(spec, state, block)

    yield 'blocks', [signed_block]
    yield 'post', state

    assert state.balances[index] < pre_balance
    # Potentially less than due to sync committee penalty
    assert state.balances[index] <= spec.MAX_EFFECTIVE_BALANCE
    assert len(spec.get_expected_withdrawals(state)) == 0


@with_capella_and_later
@spec_state_test
def test_many_partial_withdrawals_in_epoch_transition(spec, state):
    assert len(state.validators) > spec.MAX_WITHDRAWALS_PER_PAYLOAD

    for i in range(spec.MAX_WITHDRAWALS_PER_PAYLOAD + 1):
        index = (i + state.next_withdrawal_index) % len(state.validators)
        set_validator_partially_withdrawable(spec, state, index, excess_balance=1000000000000)

    assert len(spec.get_expected_withdrawals(state)) == spec.MAX_WITHDRAWALS_PER_PAYLOAD

    yield 'pre', state

    # trigger epoch transition
    block = build_empty_block(spec, state, state.slot + spec.SLOTS_PER_EPOCH)
    signed_block = state_transition_and_sign_block(spec, state, block)

    yield 'blocks', [signed_block]
    yield 'post', state

    assert len(spec.get_expected_withdrawals(state)) == 1


def _perform_valid_withdrawal(spec, state):
    fully_withdrawable_indices, partial_withdrawals_indices = prepare_expected_withdrawals(
        spec, state, num_partial_withdrawals=spec.MAX_WITHDRAWALS_PER_PAYLOAD * 2,
        num_full_withdrawals=spec.MAX_WITHDRAWALS_PER_PAYLOAD * 2)

    next_slot(spec, state)
    pre_next_withdrawal_index = state.next_withdrawal_index

    expected_withdrawals = spec.get_expected_withdrawals(state)

    pre_state = state.copy()

    # Block 1
    block = build_empty_block_for_next_slot(spec, state)
    signed_block_1 = state_transition_and_sign_block(spec, state, block)

    withdrawn_indices = [withdrawal.validator_index for withdrawal in expected_withdrawals]
    fully_withdrawable_indices = list(set(fully_withdrawable_indices).difference(set(withdrawn_indices)))
    partial_withdrawals_indices = list(set(partial_withdrawals_indices).difference(set(withdrawn_indices)))
    assert state.next_withdrawal_index == pre_next_withdrawal_index + spec.MAX_WITHDRAWALS_PER_PAYLOAD

    withdrawn_indices = [withdrawal.validator_index for withdrawal in expected_withdrawals]
    fully_withdrawable_indices = list(set(fully_withdrawable_indices).difference(set(withdrawn_indices)))
    partial_withdrawals_indices = list(set(partial_withdrawals_indices).difference(set(withdrawn_indices)))
    assert state.next_withdrawal_index == pre_next_withdrawal_index + spec.MAX_WITHDRAWALS_PER_PAYLOAD

    return pre_state, signed_block_1, pre_next_withdrawal_index


@with_capella_and_later
@spec_state_test
def test_withdrawal_success_two_blocks(spec, state):
    pre_state, signed_block_1, pre_next_withdrawal_index = _perform_valid_withdrawal(spec, state)

    yield 'pre', pre_state

    # Block 2
    block = build_empty_block_for_next_slot(spec, state)
    signed_block_2 = state_transition_and_sign_block(spec, state, block)

    assert state.next_withdrawal_index == pre_next_withdrawal_index + spec.MAX_WITHDRAWALS_PER_PAYLOAD * 2

    yield 'blocks', [signed_block_1, signed_block_2]
    yield 'post', state


@with_capella_and_later
@spec_state_test
def test_invalid_withdrawal_fail_second_block_payload_isnt_compatible(spec, state):
    _perform_valid_withdrawal(spec, state)

    # Block 2
    block = build_empty_block_for_next_slot(spec, state)

    # Modify state.next_withdrawal_index to incorrect number
    state.next_withdrawal_index += 1

    # Only need to output the state transition of signed_block_2
    yield 'pre', state

    signed_block_2 = state_transition_and_sign_block(spec, state, block, expect_fail=True)

    yield 'blocks', [signed_block_2]
    yield 'post', None
