from eth_consensus_specs.test.context import spec_state_test, with_phases
from eth_consensus_specs.test.helpers.constants import PQ
from eth_consensus_specs.test.helpers.withdrawals import (
    set_compounding_withdrawal_credential_with_balance,
    set_eth1_withdrawal_credential_with_balance,
)


def prepare_withdrawal_request(spec, state, validator_index, address, amount, prefix=None):
    """
    A withdrawal request naming the XMSS public key of the validator at
    ``validator_index``, after ``prefix``.
    """
    if prefix is None:
        prefix = spec.XMSS_DEPOSIT_PREFIX
    return spec.WithdrawalRequest(
        source_address=address,
        validator_pubkey=spec.Bytes48(prefix + state.validators[validator_index].pubkey),
        amount=amount,
    )


def run_withdrawal_request_processing(spec, state, withdrawal_request):
    yield "pre", state
    yield "withdrawal_request", withdrawal_request

    spec.process_withdrawal_request(state, withdrawal_request)

    yield "post", state


@with_phases([PQ])
@spec_state_test
def test_full_exit_request(spec, state):
    state.slot += spec.Uint64(spec.config.SHARD_COMMITTEE_PERIOD) * spec.SLOTS_PER_EPOCH
    validator_index = 0
    address = b"\x22" * 20
    set_eth1_withdrawal_credential_with_balance(spec, state, validator_index, address=address)
    withdrawal_request = prepare_withdrawal_request(
        spec, state, validator_index, address, spec.FULL_EXIT_REQUEST_AMOUNT
    )

    yield from run_withdrawal_request_processing(spec, state, withdrawal_request)

    assert state.validators[validator_index].exit_epoch < spec.FAR_FUTURE_EPOCH


@with_phases([PQ])
@spec_state_test
def test_full_exit_request_legacy_pubkey_ignored(spec, state):
    state.slot += spec.Uint64(spec.config.SHARD_COMMITTEE_PERIOD) * spec.SLOTS_PER_EPOCH
    validator_index = 0
    address = b"\x22" * 20
    set_eth1_withdrawal_credential_with_balance(spec, state, validator_index, address=address)
    withdrawal_request = prepare_withdrawal_request(
        spec,
        state,
        validator_index,
        address,
        spec.FULL_EXIT_REQUEST_AMOUNT,
        prefix=b"\xff" * 16,
    )
    pre_state = state.copy()

    yield from run_withdrawal_request_processing(spec, state, withdrawal_request)

    assert state == pre_state


@with_phases([PQ])
@spec_state_test
def test_full_exit_request_unknown_pubkey(spec, state):
    state.slot += spec.Uint64(spec.config.SHARD_COMMITTEE_PERIOD) * spec.SLOTS_PER_EPOCH
    address = b"\x22" * 20
    set_eth1_withdrawal_credential_with_balance(spec, state, 0, address=address)
    withdrawal_request = spec.WithdrawalRequest(
        source_address=address,
        validator_pubkey=spec.Bytes48(spec.XMSS_DEPOSIT_PREFIX + b"\x11" * 32),
        amount=spec.FULL_EXIT_REQUEST_AMOUNT,
    )
    pre_state = state.copy()

    yield from run_withdrawal_request_processing(spec, state, withdrawal_request)

    assert state == pre_state


@with_phases([PQ])
@spec_state_test
def test_partial_withdrawal_request(spec, state):
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
    withdrawal_request = prepare_withdrawal_request(spec, state, validator_index, address, amount)

    yield from run_withdrawal_request_processing(spec, state, withdrawal_request)

    assert len(state.pending_partial_withdrawals) == 1
    assert state.pending_partial_withdrawals[0].validator_index == validator_index
    assert state.pending_partial_withdrawals[0].amount == amount
