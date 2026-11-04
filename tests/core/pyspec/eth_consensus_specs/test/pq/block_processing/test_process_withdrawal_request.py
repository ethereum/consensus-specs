from eth_consensus_specs.test.context import spec_state_test, with_phases
from eth_consensus_specs.test.electra.block_processing.test_process_withdrawal_request import (
    run_withdrawal_request_processing,
)
from eth_consensus_specs.test.helpers.constants import PQ
from eth_consensus_specs.test.helpers.withdrawals import (
    set_compounding_withdrawal_credential_with_balance,
    set_eth1_withdrawal_credential_with_balance,
)


@with_phases([PQ])
@spec_state_test
def test_full_exit_request_ignored(spec, state):
    state.slot += spec.Uint64(spec.config.SHARD_COMMITTEE_PERIOD) * spec.SLOTS_PER_EPOCH
    validator_index = 0
    address = b"\x22" * 20
    set_eth1_withdrawal_credential_with_balance(spec, state, validator_index, address=address)
    withdrawal_request = spec.WithdrawalRequest(
        source_address=address,
        validator_pubkey=state.validators[validator_index].pubkey,
        amount=spec.FULL_EXIT_REQUEST_AMOUNT,
    )

    yield from run_withdrawal_request_processing(spec, state, withdrawal_request, success=False)

    assert state.pq_validators[validator_index].exit_epoch == spec.FAR_FUTURE_EPOCH


@with_phases([PQ])
@spec_state_test
def test_partial_withdrawal_request_ignored(spec, state):
    state.slot += spec.Uint64(spec.config.SHARD_COMMITTEE_PERIOD) * spec.SLOTS_PER_EPOCH
    validator_index = 0
    address = b"\x22" * 20
    amount = spec.EFFECTIVE_BALANCE_INCREMENT
    set_compounding_withdrawal_credential_with_balance(
        spec,
        state,
        validator_index,
        balance=spec.MIN_ACTIVATION_BALANCE + amount,
        address=address,
    )
    withdrawal_request = spec.WithdrawalRequest(
        source_address=address,
        validator_pubkey=state.validators[validator_index].pubkey,
        amount=amount,
    )

    yield from run_withdrawal_request_processing(spec, state, withdrawal_request, success=False)

    assert len(state.pending_partial_withdrawals) == 0
