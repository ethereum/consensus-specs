from eth_consensus_specs.test.context import spec_state_test, with_heze_and_later
from eth_consensus_specs.test.helpers.deposits import make_withdrawal_credentials, mock_deposit
from eth_consensus_specs.test.helpers.epoch_processing import run_epoch_processing_with
from eth_consensus_specs.test.helpers.keys import pubkeys
from eth_consensus_specs.test.helpers.state import next_epoch


def run_process_registry_updates(spec, state):
    yield from run_epoch_processing_with(spec, state, "process_registry_updates")


def prepare_queued_validator(spec, state, index, withdrawal_credentials):
    next_epoch(spec, state)
    next_epoch(spec, state)
    mock_deposit(spec, state, index)
    state.validators[index].withdrawal_credentials = withdrawal_credentials
    state.finalized_checkpoint.epoch = spec.get_current_epoch(state) - 1
    state.validators[index].activation_eligibility_epoch = state.finalized_checkpoint.epoch


@with_heze_and_later
@spec_state_test
def test_bls_withdrawal_credentials_not_activated(spec, state):
    index = 0
    withdrawal_credentials = spec.BLS_WITHDRAWAL_PREFIX + spec.sha256(pubkeys[index])[1:]
    prepare_queued_validator(spec, state, index, withdrawal_credentials)

    yield from run_process_registry_updates(spec, state)

    assert state.validators[index].activation_epoch == spec.FAR_FUTURE_EPOCH
    assert state.validators[index].effective_balance == spec.MAX_EFFECTIVE_BALANCE


@with_heze_and_later
@spec_state_test
def test_execution_withdrawal_credentials_activated(spec, state):
    index = 0
    withdrawal_credentials = make_withdrawal_credentials(
        spec, spec.ETH1_ADDRESS_WITHDRAWAL_PREFIX, b"\x42"
    )
    prepare_queued_validator(spec, state, index, withdrawal_credentials)

    yield from run_process_registry_updates(spec, state)

    assert state.validators[index].activation_epoch == spec.compute_activation_exit_epoch(
        spec.get_current_epoch(state)
    )


@with_heze_and_later
@spec_state_test
def test_active_bls_withdrawal_credentials_unaffected(spec, state):
    index = 0
    withdrawal_credentials = spec.BLS_WITHDRAWAL_PREFIX + spec.sha256(pubkeys[index])[1:]
    state.validators[index].withdrawal_credentials = withdrawal_credentials
    assert spec.is_active_validator(state.validators[index], spec.get_current_epoch(state))

    yield from run_process_registry_updates(spec, state)

    assert spec.is_active_validator(state.validators[index], spec.get_current_epoch(state))
    assert state.validators[index].exit_epoch == spec.FAR_FUTURE_EPOCH
