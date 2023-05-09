from eth2spec.test.context import spec_state_test, with_eip7002_and_later
from eth2spec.test.helpers.execution_layer_exits import run_execution_layer_exit_processing
from eth2spec.test.helpers.withdrawals import set_eth1_withdrawal_credential_with_balance


@with_eip7002_and_later
@spec_state_test
def test_basic_exit(spec, state):
    # move state forward SHARD_COMMITTEE_PERIOD epochs to allow for exit
    state.slot += spec.config.SHARD_COMMITTEE_PERIOD * spec.SLOTS_PER_EPOCH

    current_epoch = spec.get_current_epoch(state)
    validator_index = spec.get_active_validator_indices(state, current_epoch)[0]
    address = b'\x22' * 20
    set_eth1_withdrawal_credential_with_balance(spec, state, validator_index, address=address)
    execution_layer_exit = spec.ExecutionLayerExit(
        source_address=address,
        validator_index=validator_index,
    )

    yield from run_execution_layer_exit_processing(spec, state, execution_layer_exit)


@with_eip7002_and_later
@spec_state_test
def test_incorrect_source_address(spec, state):
    # move state forward SHARD_COMMITTEE_PERIOD epochs to allow for exit
    state.slot += spec.config.SHARD_COMMITTEE_PERIOD * spec.SLOTS_PER_EPOCH

    current_epoch = spec.get_current_epoch(state)
    validator_index = spec.get_active_validator_indices(state, current_epoch)[0]
    address = b'\x22' * 20
    incorrect_address = b'\x33' * 20
    set_eth1_withdrawal_credential_with_balance(spec, state, validator_index, address=address)
    execution_layer_exit = spec.ExecutionLayerExit(
        source_address=incorrect_address,
        validator_index=validator_index,
    )

    yield from run_execution_layer_exit_processing(spec, state, execution_layer_exit, success=False)
