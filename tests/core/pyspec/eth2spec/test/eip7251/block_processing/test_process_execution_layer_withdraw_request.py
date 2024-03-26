from eth2spec.test.context import (
    spec_state_test,
    expect_assertion_error,
    with_eip7251_and_later,
    with_presets, 
)
from eth2spec.test.helpers.constants import MINIMAL
from eth2spec.test.helpers.state import (
    next_epoch,
    next_slot,
)
from eth2spec.test.helpers.withdrawals import (
    prepare_expected_withdrawals,
    set_eth1_withdrawal_credential_with_balance,
    set_validator_fully_withdrawable,
    set_validator_partially_withdrawable,
)

from eth2spec.test.context import expect_assertion_error
from eth2spec.test.helpers.state import get_validator_index_by_pubkey
from eth2spec.test.helpers.withdrawals import set_eth1_withdrawal_credential_with_balance


## Only failing test from capella process_withdrawals is 
## test_success_excess_balance_but_no_max_effective_balance


#### Modified tests from 7002. Just testing EL-triggered exits, not partial withdrawals

@with_eip7251_and_later
@spec_state_test
def test_basic_exit(spec, state):
    # move state forward SHARD_COMMITTEE_PERIOD epochs to allow for exit
    state.slot += spec.config.SHARD_COMMITTEE_PERIOD * spec.SLOTS_PER_EPOCH

    current_epoch = spec.get_current_epoch(state)
    validator_index = spec.get_active_validator_indices(state, current_epoch)[0]
    validator_pubkey = state.validators[validator_index].pubkey
    address = b'\x22' * 20
    set_eth1_withdrawal_credential_with_balance(spec, state, validator_index, address=address)
    execution_layer_withdraw_request = spec.ExecutionLayerWithdrawRequest(
        source_address=address,
        validator_pubkey=validator_pubkey,
        amount = 0,
    )

    yield from run_execution_layer_withdraw_request_processing(spec, state, execution_layer_withdraw_request)


@with_eip7251_and_later
@spec_state_test
def test_incorrect_source_address(spec, state):
    # move state forward SHARD_COMMITTEE_PERIOD epochs to allow for exit
    state.slot += spec.config.SHARD_COMMITTEE_PERIOD * spec.SLOTS_PER_EPOCH

    current_epoch = spec.get_current_epoch(state)
    validator_index = spec.get_active_validator_indices(state, current_epoch)[0]
    validator_pubkey = state.validators[validator_index].pubkey
    address = b'\x22' * 20
    incorrect_address = b'\x33' * 20
    set_eth1_withdrawal_credential_with_balance(spec, state, validator_index, address=address)
    execution_layer_withdraw_request = spec.ExecutionLayerWithdrawRequest(
        source_address=incorrect_address,
        validator_pubkey=validator_pubkey,
        amount=0,
    )

    yield from run_execution_layer_withdraw_request_processing(spec, state, execution_layer_withdraw_request, success=False)


@with_eip7251_and_later
@spec_state_test
def test_incorrect_withdrawal_credential_prefix(spec, state):
    # move state forward SHARD_COMMITTEE_PERIOD epochs to allow for exit
    state.slot += spec.config.SHARD_COMMITTEE_PERIOD * spec.SLOTS_PER_EPOCH

    current_epoch = spec.get_current_epoch(state)
    validator_index = spec.get_active_validator_indices(state, current_epoch)[0]
    validator_pubkey = state.validators[validator_index].pubkey
    address = b'\x22' * 20
    set_eth1_withdrawal_credential_with_balance(spec, state, validator_index, address=address)
    # Set incorrect prefix
    state.validators[validator_index].withdrawal_credentials = (
        spec.BLS_WITHDRAWAL_PREFIX
        + state.validators[validator_index].withdrawal_credentials[1:]
    )
    execution_layer_withdraw_request = spec.ExecutionLayerWithdrawRequest(
        source_address=address,
        validator_pubkey=validator_pubkey,
        amount=0,
    )

    yield from run_execution_layer_withdraw_request_processing(spec, state, execution_layer_withdraw_request, success=False)


@with_eip7251_and_later
@spec_state_test
def test_on_exit_initiated_validator(spec, state):
    # move state forward SHARD_COMMITTEE_PERIOD epochs to allow for exit
    state.slot += spec.config.SHARD_COMMITTEE_PERIOD * spec.SLOTS_PER_EPOCH

    current_epoch = spec.get_current_epoch(state)
    validator_index = spec.get_active_validator_indices(state, current_epoch)[0]
    validator_pubkey = state.validators[validator_index].pubkey
    address = b'\x22' * 20
    set_eth1_withdrawal_credential_with_balance(spec, state, validator_index, address=address)
    # Initiate exit earlier
    spec.initiate_validator_exit(state, validator_index)
    execution_layer_withdraw_request = spec.ExecutionLayerWithdrawRequest(
        source_address=address,
        validator_pubkey=validator_pubkey,
        amount=0,
    )

    yield from run_execution_layer_withdraw_request_processing(spec, state, execution_layer_withdraw_request, success=False)


@with_eip7251_and_later
@spec_state_test
def test_activation_epoch_less_than_shard_committee_period(spec, state):
    current_epoch = spec.get_current_epoch(state)
    validator_index = spec.get_active_validator_indices(state, current_epoch)[0]
    validator_pubkey = state.validators[validator_index].pubkey
    address = b'\x22' * 20
    set_eth1_withdrawal_credential_with_balance(spec, state, validator_index, address=address)
    execution_layer_withdraw_request = spec.ExecutionLayerWithdrawRequest(
        source_address=address,
        validator_pubkey=validator_pubkey,
        amount=0,
    )

    assert spec.get_current_epoch(state) < (
        state.validators[validator_index].activation_epoch + spec.config.SHARD_COMMITTEE_PERIOD
    )

    yield from run_execution_layer_withdraw_request_processing(spec, state, execution_layer_withdraw_request, success=False)



## Partial withdrawals tests
    

@with_eip7251_and_later
@spec_state_test
@with_presets([MINIMAL])
def test_partial_withdrawal_queue_full(spec, state):
    state.slot += spec.config.SHARD_COMMITTEE_PERIOD * spec.SLOTS_PER_EPOCH
    current_epoch = spec.get_current_epoch(state)
    validator_index = spec.get_active_validator_indices(state, current_epoch)[0]
    validator_pubkey = state.validators[validator_index].pubkey
    address = b'\x22' * 20
    set_eth1_withdrawal_credential_with_balance(spec, state, validator_index, address=address)
    execution_layer_withdraw_request = spec.ExecutionLayerWithdrawRequest(
        source_address=address,
        validator_pubkey=validator_pubkey,
        amount = 10**9,
    )

    partial_withdrawal = spec.PartialWithdrawal(index=0,amount=1,withdrawable_epoch=current_epoch)
    state.pending_partial_withdrawals = [partial_withdrawal] * spec.PENDING_PARTIAL_WITHDRAWALS_LIMIT
    yield from run_execution_layer_withdraw_request_processing(spec, state, execution_layer_withdraw_request, success=False)



#
# Run processing
#


def run_execution_layer_withdraw_request_processing(spec, state, execution_layer_withdraw_request, valid=True, success=True):
    """
    Run ``process_execution_layer_withdraw_request``, yielding:
      - pre-state ('pre')
      - execution_layer_withdraw_request ('execution_layer_withdraw_request')
      - post-state ('post').
    If ``valid == False``, run expecting ``AssertionError``
    If ``success == False``, it doesn't initiate exit successfully
    """
    validator_index = get_validator_index_by_pubkey(state, execution_layer_withdraw_request.validator_pubkey)

    yield 'pre', state
    yield 'execution_layer_withdraw_request', execution_layer_withdraw_request

    if not valid:
        expect_assertion_error(lambda: spec.process_execution_layer_withdraw_request(state, execution_layer_withdraw_request))
        yield 'post', None
        return

    pre_exit_epoch = state.validators[validator_index].exit_epoch
    pre_pending_partial_withdrawals = state.pending_partial_withdrawals
    pre_balance = state.balances[validator_index]

    spec.process_execution_layer_withdraw_request(state, execution_layer_withdraw_request)

    yield 'post', state

    if execution_layer_withdraw_request.amount == 0:
        if success:
            assert pre_exit_epoch == spec.FAR_FUTURE_EPOCH
            assert state.validators[validator_index].exit_epoch < spec.FAR_FUTURE_EPOCH
        else:
            assert state.validators[validator_index].exit_epoch == pre_exit_epoch
    else:
        if success:
            assert state.validators[validator_index].exit_epoch == spec.FAR_FUTURE_EPOCH
            assert state.balances[validator_index] == pre_balance
            post_length = len(state.pending_partial_withdrawals)
            assert post_length == len(pre_pending_partial_withdrawals) + 1
            assert post_length < spec.PENDING_PARTIAL_WITHDRAWALS_LIMIT
            assert state.pending_partial_withdrawals[post_length-1].validator_index == validator_index
        else:
            assert state.pending_partial_withdrawals == pre_pending_partial_withdrawals
