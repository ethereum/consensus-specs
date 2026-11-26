from eth_consensus_specs.test.context import spec_state_test, with_phases
from eth_consensus_specs.test.eip8483.block_processing.test_process_validator_pq_registration_request import (
    prepare_validator_pq_registration_request,
)
from eth_consensus_specs.test.electra.block_processing.test_process_withdrawal_request import (
    run_withdrawal_request_processing,
)
from eth_consensus_specs.test.helpers.constants import EIP8483
from eth_consensus_specs.test.helpers.withdrawals import set_compounding_withdrawal_credential


@with_phases([EIP8483])
@spec_state_test
def test_process_withdrawal_request__full_exit_removes_pq_registration(spec, state):
    # Move state forward SHARD_COMMITTEE_PERIOD epochs to allow for exit
    state.slot += spec.Uint64(spec.config.SHARD_COMMITTEE_PERIOD) * spec.SLOTS_PER_EPOCH
    address = b"\x22" * 20
    set_compounding_withdrawal_credential(spec, state, 0, address=address)
    set_compounding_withdrawal_credential(spec, state, 1, address=address)
    spec.process_validator_pq_registration_request(
        state, prepare_validator_pq_registration_request(spec, state, 0, b"\x33" * 64)
    )
    spec.process_validator_pq_registration_request(
        state, prepare_validator_pq_registration_request(spec, state, 1, b"\x44" * 64)
    )
    withdrawal_request = spec.WithdrawalRequest(
        source_address=address,
        validator_pubkey=state.validators[0].pubkey,
        amount=spec.FULL_EXIT_REQUEST_AMOUNT,
    )

    yield from run_withdrawal_request_processing(spec, state, withdrawal_request)

    assert [registration.validator_index for registration in state.validator_pq_registrations] == [
        1
    ]
