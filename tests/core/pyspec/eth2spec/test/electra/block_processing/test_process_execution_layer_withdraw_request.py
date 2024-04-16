from eth2spec.test.context import (
    spec_state_test,
    expect_assertion_error,
    with_electra_and_later,
    with_presets,
)
from eth2spec.test.helpers.constants import MINIMAL
from eth2spec.test.helpers.state import (
    get_validator_index_by_pubkey,
)
from eth2spec.test.helpers.withdrawals import (
    set_eth1_withdrawal_credential_with_balance,
    set_compounding_withdrawal_credential,
)


# Only failing test from capella process_withdrawals is
# test_success_excess_balance_but_no_max_effective_balance


# Modified tests from 7002. Just testing EL-triggered exits, not partial withdrawals

@with_electra_and_later
@spec_state_test
def test_basic_exit(spec, state):
    # move state forward SHARD_COMMITTEE_PERIOD epochs to allow for exit
    state.slot += spec.config.SHARD_COMMITTEE_PERIOD * spec.SLOTS_PER_EPOCH

    current_epoch = spec.get_current_epoch(state)
    validator_index = spec.get_active_validator_indices(state, current_epoch)[0]
    validator_pubkey = state.validators[validator_index].pubkey
    address = b"\x22" * 20
    set_eth1_withdrawal_credential_with_balance(
        spec, state, validator_index, address=address
    )
    execution_layer_withdraw_request = spec.ExecutionLayerWithdrawRequest(
        source_address=address,
        validator_pubkey=validator_pubkey,
        amount=spec.FULL_EXIT_REQUEST_AMOUNT,
    )

    yield from run_execution_layer_withdraw_request_processing(
        spec, state, execution_layer_withdraw_request
    )


@with_electra_and_later
@spec_state_test
def test_basic_exit_with_compounding_credentials(spec, state):
    # move state forward SHARD_COMMITTEE_PERIOD epochs to allow for exit
    state.slot += spec.config.SHARD_COMMITTEE_PERIOD * spec.SLOTS_PER_EPOCH

    current_epoch = spec.get_current_epoch(state)
    validator_index = spec.get_active_validator_indices(state, current_epoch)[0]
    validator_pubkey = state.validators[validator_index].pubkey
    address = b"\x22" * 20
    set_compounding_withdrawal_credential(spec, state, validator_index, address=address)
    execution_layer_withdraw_request = spec.ExecutionLayerWithdrawRequest(
        source_address=address,
        validator_pubkey=validator_pubkey,
        amount=spec.FULL_EXIT_REQUEST_AMOUNT,
    )

    yield from run_execution_layer_withdraw_request_processing(
        spec, state, execution_layer_withdraw_request
    )


@with_electra_and_later
@spec_state_test
@with_presets([MINIMAL], "need full partial withdrawal queue")
def test_basic_exit_with_full_partial_withdrawal_queue(spec, state):
    state.slot += spec.config.SHARD_COMMITTEE_PERIOD * spec.SLOTS_PER_EPOCH
    current_epoch = spec.get_current_epoch(state)
    validator_index = spec.get_active_validator_indices(state, current_epoch)[0]
    validator_pubkey = state.validators[validator_index].pubkey
    address = b"\x22" * 20
    set_eth1_withdrawal_credential_with_balance(
        spec, state, validator_index, address=address
    )
    execution_layer_withdraw_request = spec.ExecutionLayerWithdrawRequest(
        source_address=address,
        validator_pubkey=validator_pubkey,
        amount=spec.FULL_EXIT_REQUEST_AMOUNT,
    )

    # Fill the partial withdrawal queue to the max (with a different validator index)
    partial_withdrawal = spec.PendingPartialWithdrawal(
        index=1, amount=1, withdrawable_epoch=current_epoch
    )
    state.pending_partial_withdrawals = [
        partial_withdrawal
    ] * spec.PENDING_PARTIAL_WITHDRAWALS_LIMIT

    # Exit should still be processed
    yield from run_execution_layer_withdraw_request_processing(
        spec,
        state,
        execution_layer_withdraw_request,
    )


# Invalid tests


@with_electra_and_later
@spec_state_test
def test_incorrect_source_address(spec, state):
    # move state forward SHARD_COMMITTEE_PERIOD epochs to allow for exit
    state.slot += spec.config.SHARD_COMMITTEE_PERIOD * spec.SLOTS_PER_EPOCH

    current_epoch = spec.get_current_epoch(state)
    validator_index = spec.get_active_validator_indices(state, current_epoch)[0]
    validator_pubkey = state.validators[validator_index].pubkey
    address = b"\x22" * 20
    incorrect_address = b"\x33" * 20
    set_eth1_withdrawal_credential_with_balance(
        spec, state, validator_index, address=address
    )
    execution_layer_withdraw_request = spec.ExecutionLayerWithdrawRequest(
        source_address=incorrect_address,
        validator_pubkey=validator_pubkey,
        amount=spec.FULL_EXIT_REQUEST_AMOUNT,
    )

    yield from run_execution_layer_withdraw_request_processing(
        spec, state, execution_layer_withdraw_request, success=False
    )


@with_electra_and_later
@spec_state_test
def test_incorrect_withdrawal_credential_prefix(spec, state):
    # move state forward SHARD_COMMITTEE_PERIOD epochs to allow for exit
    state.slot += spec.config.SHARD_COMMITTEE_PERIOD * spec.SLOTS_PER_EPOCH

    current_epoch = spec.get_current_epoch(state)
    validator_index = spec.get_active_validator_indices(state, current_epoch)[0]
    validator_pubkey = state.validators[validator_index].pubkey
    address = b"\x22" * 20
    set_eth1_withdrawal_credential_with_balance(
        spec, state, validator_index, address=address
    )
    # Set incorrect prefix
    state.validators[validator_index].withdrawal_credentials = (
        spec.BLS_WITHDRAWAL_PREFIX
        + state.validators[validator_index].withdrawal_credentials[1:]
    )
    execution_layer_withdraw_request = spec.ExecutionLayerWithdrawRequest(
        source_address=address,
        validator_pubkey=validator_pubkey,
        amount=spec.FULL_EXIT_REQUEST_AMOUNT,
    )

    yield from run_execution_layer_withdraw_request_processing(
        spec, state, execution_layer_withdraw_request, success=False
    )


@with_electra_and_later
@spec_state_test
def test_on_exit_initiated_validator(spec, state):
    # move state forward SHARD_COMMITTEE_PERIOD epochs to allow for exit
    state.slot += spec.config.SHARD_COMMITTEE_PERIOD * spec.SLOTS_PER_EPOCH

    current_epoch = spec.get_current_epoch(state)
    validator_index = spec.get_active_validator_indices(state, current_epoch)[0]
    validator_pubkey = state.validators[validator_index].pubkey
    address = b"\x22" * 20
    set_eth1_withdrawal_credential_with_balance(
        spec, state, validator_index, address=address
    )
    # Initiate exit earlier
    spec.initiate_validator_exit(state, validator_index)
    execution_layer_withdraw_request = spec.ExecutionLayerWithdrawRequest(
        source_address=address,
        validator_pubkey=validator_pubkey,
        amount=spec.FULL_EXIT_REQUEST_AMOUNT,
    )

    yield from run_execution_layer_withdraw_request_processing(
        spec, state, execution_layer_withdraw_request, success=False
    )


@with_electra_and_later
@spec_state_test
def test_activation_epoch_less_than_shard_committee_period(spec, state):
    current_epoch = spec.get_current_epoch(state)
    validator_index = spec.get_active_validator_indices(state, current_epoch)[0]
    validator_pubkey = state.validators[validator_index].pubkey
    address = b"\x22" * 20
    set_eth1_withdrawal_credential_with_balance(
        spec, state, validator_index, address=address
    )
    execution_layer_withdraw_request = spec.ExecutionLayerWithdrawRequest(
        source_address=address,
        validator_pubkey=validator_pubkey,
        amount=spec.FULL_EXIT_REQUEST_AMOUNT,
    )

    assert spec.get_current_epoch(state) < (
        state.validators[validator_index].activation_epoch
        + spec.config.SHARD_COMMITTEE_PERIOD
    )

    yield from run_execution_layer_withdraw_request_processing(
        spec, state, execution_layer_withdraw_request, success=False
    )


# Partial withdrawals tests

@with_electra_and_later
@spec_state_test
@with_presets([MINIMAL])
def test_basic_partial_withdrawal_request(spec, state):
    state.slot += spec.config.SHARD_COMMITTEE_PERIOD * spec.SLOTS_PER_EPOCH
    current_epoch = spec.get_current_epoch(state)
    validator_index = spec.get_active_validator_indices(state, current_epoch)[0]
    validator_pubkey = state.validators[validator_index].pubkey
    address = b"\x22" * 20
    amount = spec.EFFECTIVE_BALANCE_INCREMENT
    # Set excess balance exactly to the requested amount
    state.balances[validator_index] += amount

    set_compounding_withdrawal_credential(spec, state, validator_index, address=address)
    execution_layer_withdraw_request = spec.ExecutionLayerWithdrawRequest(
        source_address=address,
        validator_pubkey=validator_pubkey,
        amount=amount,
    )

    yield from run_execution_layer_withdraw_request_processing(
        spec,
        state,
        execution_layer_withdraw_request,
    )

    # Check that the assigned exit epoch is correct
    assert state.earliest_exit_epoch == spec.compute_activation_exit_epoch(
        current_epoch
    )


@with_electra_and_later
@spec_state_test
@with_presets([MINIMAL])
def test_basic_partial_withdrawal_request_higher_excess_balance(spec, state):
    state.slot += spec.config.SHARD_COMMITTEE_PERIOD * spec.SLOTS_PER_EPOCH
    current_epoch = spec.get_current_epoch(state)
    validator_index = spec.get_active_validator_indices(state, current_epoch)[0]
    validator_pubkey = state.validators[validator_index].pubkey
    address = b"\x22" * 20
    amount = spec.EFFECTIVE_BALANCE_INCREMENT
    # Set excess balance higher than requested amount
    state.balances[validator_index] += 2 * amount

    set_compounding_withdrawal_credential(spec, state, validator_index, address=address)
    execution_layer_withdraw_request = spec.ExecutionLayerWithdrawRequest(
        source_address=address,
        validator_pubkey=validator_pubkey,
        amount=amount,
    )

    yield from run_execution_layer_withdraw_request_processing(
        spec,
        state,
        execution_layer_withdraw_request,
    )

    # Check that the assigned exit epoch is correct
    assert state.earliest_exit_epoch == spec.compute_activation_exit_epoch(
        current_epoch
    )


@with_electra_and_later
@spec_state_test
@with_presets([MINIMAL])
def test_basic_partial_withdrawal_request_lower_than_excess_balance(spec, state):
    state.slot += spec.config.SHARD_COMMITTEE_PERIOD * spec.SLOTS_PER_EPOCH
    current_epoch = spec.get_current_epoch(state)
    validator_index = spec.get_active_validator_indices(state, current_epoch)[0]
    validator_pubkey = state.validators[validator_index].pubkey
    address = b"\x22" * 20
    excess_balance = spec.EFFECTIVE_BALANCE_INCREMENT
    amount = 2 * excess_balance
    # Set excess balance higher than requested amount
    state.balances[validator_index] += excess_balance

    set_compounding_withdrawal_credential(spec, state, validator_index, address=address)
    execution_layer_withdraw_request = spec.ExecutionLayerWithdrawRequest(
        source_address=address,
        validator_pubkey=validator_pubkey,
        amount=amount,
    )

    yield from run_execution_layer_withdraw_request_processing(
        spec,
        state,
        execution_layer_withdraw_request,
    )

    # Check that the assigned exit epoch is correct
    assert state.earliest_exit_epoch == spec.compute_activation_exit_epoch(
        current_epoch
    )


@with_electra_and_later
@spec_state_test
@with_presets([MINIMAL])
def test_partial_withdrawal_request_with_pending_withdrawals(spec, state):
    state.slot += spec.config.SHARD_COMMITTEE_PERIOD * spec.SLOTS_PER_EPOCH
    current_epoch = spec.get_current_epoch(state)
    validator_index = spec.get_active_validator_indices(state, current_epoch)[0]
    validator_pubkey = state.validators[validator_index].pubkey
    address = b"\x22" * 20
    amount = spec.EFFECTIVE_BALANCE_INCREMENT

    set_compounding_withdrawal_credential(spec, state, validator_index, address=address)
    execution_layer_withdraw_request = spec.ExecutionLayerWithdrawRequest(
        source_address=address,
        validator_pubkey=validator_pubkey,
        amount=amount,
    )

    # Add pending withdrawals
    partial_withdrawal = spec.PendingPartialWithdrawal(
        index=validator_index, amount=amount, withdrawable_epoch=current_epoch
    )
    state.pending_partial_withdrawals = [partial_withdrawal] * 2

    # Set balance so that the validator still has excess balance even with the pending withdrawals
    state.balances[validator_index] += 3 * amount

    yield from run_execution_layer_withdraw_request_processing(
        spec,
        state,
        execution_layer_withdraw_request,
    )

    # Check that the assigned exit epoch is correct
    assert state.earliest_exit_epoch == spec.compute_activation_exit_epoch(
        current_epoch
    )


@with_electra_and_later
@spec_state_test
@with_presets([MINIMAL])
def test_partial_withdrawal_request_with_pending_withdrawals_and_high_amount(
    spec, state
):
    state.slot += spec.config.SHARD_COMMITTEE_PERIOD * spec.SLOTS_PER_EPOCH
    current_epoch = spec.get_current_epoch(state)
    validator_index = spec.get_active_validator_indices(state, current_epoch)[0]
    validator_pubkey = state.validators[validator_index].pubkey
    address = b"\x22" * 20
    amount = spec.UINT64_MAX

    set_compounding_withdrawal_credential(spec, state, validator_index, address=address)
    execution_layer_withdraw_request = spec.ExecutionLayerWithdrawRequest(
        source_address=address,
        validator_pubkey=validator_pubkey,
        amount=amount,
    )

    # Add many pending withdrawals
    partial_withdrawal = spec.PendingPartialWithdrawal(
        index=validator_index,
        amount=spec.EFFECTIVE_BALANCE_INCREMENT,
        withdrawable_epoch=current_epoch,
    )
    state.pending_partial_withdrawals = [partial_withdrawal] * (
        spec.PENDING_PARTIAL_WITHDRAWALS_LIMIT - 1
    )

    # Set balance so that the validator still has excess balance even with the pending withdrawals
    state.balances[validator_index] = spec.MAX_EFFECTIVE_BALANCE_ELECTRA

    yield from run_execution_layer_withdraw_request_processing(
        spec,
        state,
        execution_layer_withdraw_request,
    )


@with_electra_and_later
@spec_state_test
@with_presets([MINIMAL])
def test_partial_withdrawal_request_with_high_balance(spec, state):
    state.slot += spec.config.SHARD_COMMITTEE_PERIOD * spec.SLOTS_PER_EPOCH
    current_epoch = spec.get_current_epoch(state)
    validator_index = spec.get_active_validator_indices(state, current_epoch)[0]
    validator_pubkey = state.validators[validator_index].pubkey
    address = b"\x22" * 20
    amount = spec.MAX_EFFECTIVE_BALANCE_ELECTRA
    state.balances[validator_index] = 3 * spec.MAX_EFFECTIVE_BALANCE_ELECTRA
    state.validators[validator_index].effective_balance = (
        spec.MAX_EFFECTIVE_BALANCE_ELECTRA
    )

    set_compounding_withdrawal_credential(spec, state, validator_index, address=address)
    execution_layer_withdraw_request = spec.ExecutionLayerWithdrawRequest(
        source_address=address,
        validator_pubkey=validator_pubkey,
        amount=amount,
    )

    churn_limit = spec.get_activation_exit_churn_limit(state)

    yield from run_execution_layer_withdraw_request_processing(
        spec,
        state,
        execution_layer_withdraw_request,
    )

    # Check that the assigned exit epoch is correct
    exit_epoch = (
        spec.compute_activation_exit_epoch(current_epoch) + amount // churn_limit
    )
    assert state.earliest_exit_epoch == exit_epoch


@with_electra_and_later
@spec_state_test
@with_presets([MINIMAL])
def test_partial_withdrawal_request_with_high_amount(spec, state):
    state.slot += spec.config.SHARD_COMMITTEE_PERIOD * spec.SLOTS_PER_EPOCH
    current_epoch = spec.get_current_epoch(state)
    validator_index = spec.get_active_validator_indices(state, current_epoch)[0]
    validator_pubkey = state.validators[validator_index].pubkey
    address = b"\x22" * 20
    # Set high amount requested to withdraw
    amount = spec.UINT64_MAX
    # Give the validator some excess balance to withdraw
    state.balances[validator_index] += 1

    set_compounding_withdrawal_credential(spec, state, validator_index, address=address)
    execution_layer_withdraw_request = spec.ExecutionLayerWithdrawRequest(
        source_address=address,
        validator_pubkey=validator_pubkey,
        amount=amount,
    )

    yield from run_execution_layer_withdraw_request_processing(
        spec,
        state,
        execution_layer_withdraw_request,
    )

    # Check that the assigned exit epoch is correct
    assert state.earliest_exit_epoch == spec.compute_activation_exit_epoch(
        current_epoch
    )


@with_electra_and_later
@spec_state_test
@with_presets([MINIMAL])
def test_partial_withdrawal_request_with_low_amount(spec, state):
    state.slot += spec.config.SHARD_COMMITTEE_PERIOD * spec.SLOTS_PER_EPOCH
    current_epoch = spec.get_current_epoch(state)
    validator_index = spec.get_active_validator_indices(state, current_epoch)[0]
    validator_pubkey = state.validators[validator_index].pubkey
    address = b"\x22" * 20
    amount = 1
    # Give the validator some excess balance to withdraw
    state.balances[validator_index] += amount

    set_compounding_withdrawal_credential(spec, state, validator_index, address=address)
    execution_layer_withdraw_request = spec.ExecutionLayerWithdrawRequest(
        source_address=address,
        validator_pubkey=validator_pubkey,
        amount=amount,
    )

    yield from run_execution_layer_withdraw_request_processing(
        spec,
        state,
        execution_layer_withdraw_request,
    )

    # Check that the assigned exit epoch is correct
    assert state.earliest_exit_epoch == spec.compute_activation_exit_epoch(
        current_epoch
    )


# No-op partial withdrawal tests


@with_electra_and_later
@spec_state_test
@with_presets([MINIMAL], "need full partial withdrawal queue")
def test_partial_withdrawal_queue_full(spec, state):
    state.slot += spec.config.SHARD_COMMITTEE_PERIOD * spec.SLOTS_PER_EPOCH
    current_epoch = spec.get_current_epoch(state)
    validator_index = spec.get_active_validator_indices(state, current_epoch)[0]
    validator_pubkey = state.validators[validator_index].pubkey
    address = b"\x22" * 20
    amount = spec.EFFECTIVE_BALANCE_INCREMENT
    # Ensure that the validator has sufficient excess balance
    state.balances[validator_index] += 2 * amount
    set_compounding_withdrawal_credential(spec, state, validator_index, address=address)
    execution_layer_withdraw_request = spec.ExecutionLayerWithdrawRequest(
        source_address=address,
        validator_pubkey=validator_pubkey,
        amount=amount,
    )

    # Fill the partial withdrawal queue to the max
    partial_withdrawal = spec.PendingPartialWithdrawal(
        index=1, amount=1, withdrawable_epoch=current_epoch
    )
    state.pending_partial_withdrawals = [
        partial_withdrawal
    ] * spec.PENDING_PARTIAL_WITHDRAWALS_LIMIT
    yield from run_execution_layer_withdraw_request_processing(
        spec, state, execution_layer_withdraw_request, success=False
    )


@with_electra_and_later
@spec_state_test
def test_no_compounding_credentials(spec, state):
    state.slot += spec.config.SHARD_COMMITTEE_PERIOD * spec.SLOTS_PER_EPOCH
    current_epoch = spec.get_current_epoch(state)
    validator_index = spec.get_active_validator_indices(state, current_epoch)[0]
    validator_pubkey = state.validators[validator_index].pubkey
    address = b"\x22" * 20
    amount = spec.EFFECTIVE_BALANCE_INCREMENT
    # Ensure that the validator has sufficient excess balance
    state.balances[validator_index] += 2 * amount

    set_eth1_withdrawal_credential_with_balance(
        spec, state, validator_index, address=address
    )
    execution_layer_withdraw_request = spec.ExecutionLayerWithdrawRequest(
        source_address=address,
        validator_pubkey=validator_pubkey,
        amount=amount,
    )

    yield from run_execution_layer_withdraw_request_processing(
        spec,
        state,
        execution_layer_withdraw_request,
        success=False,
    )


@with_electra_and_later
@spec_state_test
def test_no_excess_balance(spec, state):
    state.slot += spec.config.SHARD_COMMITTEE_PERIOD * spec.SLOTS_PER_EPOCH
    current_epoch = spec.get_current_epoch(state)
    validator_index = spec.get_active_validator_indices(state, current_epoch)[0]
    validator_pubkey = state.validators[validator_index].pubkey
    address = b"\x22" * 20
    amount = spec.EFFECTIVE_BALANCE_INCREMENT

    set_compounding_withdrawal_credential(spec, state, validator_index, address=address)
    execution_layer_withdraw_request = spec.ExecutionLayerWithdrawRequest(
        source_address=address,
        validator_pubkey=validator_pubkey,
        amount=amount,
    )

    yield from run_execution_layer_withdraw_request_processing(
        spec, state, execution_layer_withdraw_request, success=False
    )


@with_electra_and_later
@spec_state_test
def test_pending_withdrawals_consume_all_excess_balance(spec, state):
    state.slot += spec.config.SHARD_COMMITTEE_PERIOD * spec.SLOTS_PER_EPOCH
    current_epoch = spec.get_current_epoch(state)
    validator_index = spec.get_active_validator_indices(state, current_epoch)[0]
    validator_pubkey = state.validators[validator_index].pubkey
    address = b"\x22" * 20
    amount = spec.EFFECTIVE_BALANCE_INCREMENT
    # Add excess balance
    state.balances[validator_index] += 10 * amount

    set_compounding_withdrawal_credential(spec, state, validator_index, address=address)
    execution_layer_withdraw_request = spec.ExecutionLayerWithdrawRequest(
        source_address=address,
        validator_pubkey=validator_pubkey,
        amount=amount,
    )

    # Add pending withdrawals totalling an amount equal to the excess balance
    partial_withdrawal = spec.PendingPartialWithdrawal(
        index=validator_index, amount=amount, withdrawable_epoch=current_epoch
    )
    state.pending_partial_withdrawals = [partial_withdrawal] * 10

    yield from run_execution_layer_withdraw_request_processing(
        spec, state, execution_layer_withdraw_request, success=False
    )


@with_electra_and_later
@spec_state_test
def test_insufficient_effective_balance(spec, state):
    state.slot += spec.config.SHARD_COMMITTEE_PERIOD * spec.SLOTS_PER_EPOCH
    current_epoch = spec.get_current_epoch(state)
    validator_index = spec.get_active_validator_indices(state, current_epoch)[0]
    validator_pubkey = state.validators[validator_index].pubkey
    address = b"\x22" * 20
    amount = spec.EFFECTIVE_BALANCE_INCREMENT
    # Make effective balance insufficient
    state.validators[
        validator_index
    ].effective_balance -= spec.EFFECTIVE_BALANCE_INCREMENT

    set_compounding_withdrawal_credential(spec, state, validator_index, address=address)
    execution_layer_withdraw_request = spec.ExecutionLayerWithdrawRequest(
        source_address=address,
        validator_pubkey=validator_pubkey,
        amount=amount,
    )

    yield from run_execution_layer_withdraw_request_processing(
        spec,
        state,
        execution_layer_withdraw_request,
        success=False,
    )


@with_electra_and_later
@spec_state_test
def test_partial_withdrawal_incorrect_source_address(spec, state):
    # move state forward SHARD_COMMITTEE_PERIOD epochs to allow for exit
    state.slot += spec.config.SHARD_COMMITTEE_PERIOD * spec.SLOTS_PER_EPOCH

    current_epoch = spec.get_current_epoch(state)
    validator_index = spec.get_active_validator_indices(state, current_epoch)[0]
    validator_pubkey = state.validators[validator_index].pubkey
    address = b"\x22" * 20
    incorrect_address = b"\x33" * 20
    amount = spec.EFFECTIVE_BALANCE_INCREMENT
    state.balances[validator_index] += 2 * amount

    set_compounding_withdrawal_credential(spec, state, validator_index, address=address)
    execution_layer_withdraw_request = spec.ExecutionLayerWithdrawRequest(
        source_address=incorrect_address,
        validator_pubkey=validator_pubkey,
        amount=amount,
    )

    yield from run_execution_layer_withdraw_request_processing(
        spec, state, execution_layer_withdraw_request, success=False
    )


@with_electra_and_later
@spec_state_test
def test_partial_withdrawal_incorrect_withdrawal_credential_prefix(spec, state):
    # move state forward SHARD_COMMITTEE_PERIOD epochs to allow for exit
    state.slot += spec.config.SHARD_COMMITTEE_PERIOD * spec.SLOTS_PER_EPOCH

    current_epoch = spec.get_current_epoch(state)
    validator_index = spec.get_active_validator_indices(state, current_epoch)[0]
    validator_pubkey = state.validators[validator_index].pubkey
    address = b"\x22" * 20
    amount = spec.EFFECTIVE_BALANCE_INCREMENT
    state.balances[validator_index] += 2 * amount
    set_compounding_withdrawal_credential(spec, state, validator_index, address=address)
    # Set incorrect prefix
    state.validators[validator_index].withdrawal_credentials = (
        spec.BLS_WITHDRAWAL_PREFIX
        + state.validators[validator_index].withdrawal_credentials[1:]
    )
    execution_layer_withdraw_request = spec.ExecutionLayerWithdrawRequest(
        source_address=address,
        validator_pubkey=validator_pubkey,
        amount=amount,
    )

    yield from run_execution_layer_withdraw_request_processing(
        spec, state, execution_layer_withdraw_request, success=False
    )


@with_electra_and_later
@spec_state_test
def test_partial_withdrawal_on_exit_initiated_validator(spec, state):
    # move state forward SHARD_COMMITTEE_PERIOD epochs to allow for exit
    state.slot += spec.config.SHARD_COMMITTEE_PERIOD * spec.SLOTS_PER_EPOCH

    current_epoch = spec.get_current_epoch(state)
    validator_index = spec.get_active_validator_indices(state, current_epoch)[0]
    validator_pubkey = state.validators[validator_index].pubkey
    address = b"\x22" * 20
    amount = spec.EFFECTIVE_BALANCE_INCREMENT
    state.balances[validator_index] += 2 * amount
    set_compounding_withdrawal_credential(spec, state, validator_index, address=address)
    # Initiate exit earlier
    spec.initiate_validator_exit(state, validator_index)
    execution_layer_withdraw_request = spec.ExecutionLayerWithdrawRequest(
        source_address=address,
        validator_pubkey=validator_pubkey,
        amount=amount,
    )

    yield from run_execution_layer_withdraw_request_processing(
        spec, state, execution_layer_withdraw_request, success=False
    )


@with_electra_and_later
@spec_state_test
def test_partial_withdrawal_activation_epoch_less_than_shard_committee_period(
    spec, state
):
    current_epoch = spec.get_current_epoch(state)
    validator_index = spec.get_active_validator_indices(state, current_epoch)[0]
    validator_pubkey = state.validators[validator_index].pubkey
    address = b"\x22" * 20
    amount = spec.EFFECTIVE_BALANCE_INCREMENT
    state.balances[validator_index] += 2 * amount
    set_compounding_withdrawal_credential(spec, state, validator_index, address=address)
    execution_layer_withdraw_request = spec.ExecutionLayerWithdrawRequest(
        source_address=address,
        validator_pubkey=validator_pubkey,
        amount=amount,
    )

    assert spec.get_current_epoch(state) < (
        state.validators[validator_index].activation_epoch
        + spec.config.SHARD_COMMITTEE_PERIOD
    )

    yield from run_execution_layer_withdraw_request_processing(
        spec, state, execution_layer_withdraw_request, success=False
    )


#
# Run processing
#


def run_execution_layer_withdraw_request_processing(
    spec, state, execution_layer_withdraw_request, valid=True, success=True
):
    """
    Run ``process_execution_layer_withdraw_request``, yielding:
      - pre-state ('pre')
      - execution_layer_withdraw_request ('execution_layer_withdraw_request')
      - post-state ('post').
    If ``valid == False``, run expecting ``AssertionError``
    If ``success == False``, it doesn't initiate exit successfully
    """
    validator_index = get_validator_index_by_pubkey(
        state, execution_layer_withdraw_request.validator_pubkey
    )

    yield "pre", state
    yield "execution_layer_withdraw_request", execution_layer_withdraw_request

    if not valid:
        expect_assertion_error(
            lambda: spec.process_execution_layer_withdraw_request(
                state, execution_layer_withdraw_request
            )
        )
        yield "post", None
        return

    pre_exit_epoch = state.validators[validator_index].exit_epoch
    pre_pending_partial_withdrawals = state.pending_partial_withdrawals.copy()
    pre_balance = state.balances[validator_index]
    pre_effective_balance = state.validators[validator_index].effective_balance
    pre_state = state
    expected_amount_to_withdraw = compute_amount_to_withdraw(
        spec, state, validator_index, execution_layer_withdraw_request.amount
    )

    spec.process_execution_layer_withdraw_request(
        state, execution_layer_withdraw_request
    )

    yield "post", state

    if not success:
        # No-op
        assert pre_state == state
    else:
        assert state.balances[validator_index] == pre_balance
        assert (
            state.validators[validator_index].effective_balance == pre_effective_balance
        )
        # Full exit request
        if execution_layer_withdraw_request.amount == spec.FULL_EXIT_REQUEST_AMOUNT:
            assert pre_exit_epoch == spec.FAR_FUTURE_EPOCH
            assert state.validators[validator_index].exit_epoch < spec.FAR_FUTURE_EPOCH
            assert spec.get_pending_balance_to_withdraw(state, validator_index) == 0
            assert state.pending_partial_withdrawals == pre_pending_partial_withdrawals
        # Partial withdrawal request
        else:
            assert state.validators[validator_index].exit_epoch == spec.FAR_FUTURE_EPOCH
            expected_withdrawable_epoch = (
                state.earliest_exit_epoch
                + spec.config.MIN_VALIDATOR_WITHDRAWABILITY_DELAY
            )
            expected_partial_withdrawal = spec.PendingPartialWithdrawal(
                index=validator_index,
                amount=expected_amount_to_withdraw,
                withdrawable_epoch=expected_withdrawable_epoch,
            )
            assert (
                state.pending_partial_withdrawals
                == pre_pending_partial_withdrawals + [expected_partial_withdrawal]
            )


def compute_amount_to_withdraw(spec, state, index, amount):
    pending_balance_to_withdraw = spec.get_pending_balance_to_withdraw(state, index)
    return min(
        state.balances[index]
        - spec.MIN_ACTIVATION_BALANCE
        - pending_balance_to_withdraw,
        amount,
    )
