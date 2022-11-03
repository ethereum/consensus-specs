from eth2spec.test.context import (
    with_capella_and_later, spec_state_test
)

from eth2spec.test.helpers.state import (
    state_transition_and_sign_block,
)
from eth2spec.test.helpers.block import (
    build_empty_block_for_next_slot, build_empty_block,
)
from eth2spec.test.helpers.bls_to_execution_changes import get_signed_address_change
from eth2spec.test.helpers.withdrawals import (
    set_validator_fully_withdrawable,
    set_validator_partially_withdrawable,
)
from eth2spec.test.helpers.voluntary_exits import prepare_signed_exits


@with_capella_and_later
@spec_state_test
def test_successful_bls_change(spec, state):
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


@with_capella_and_later
@spec_state_test
def test_exit_and_bls_change(spec, state):
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
