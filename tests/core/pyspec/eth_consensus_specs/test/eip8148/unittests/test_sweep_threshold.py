from eth_consensus_specs.test.context import (
    single_phase,
    spec_state_test,
    spec_test,
    with_eip8148_and_later,
    with_phases,
    with_state,
)
from eth_consensus_specs.test.helpers.constants import EIP8148, HEZE
from eth_consensus_specs.test.helpers.withdrawals import (
    set_compounding_withdrawal_credential_with_balance,
    set_eth1_withdrawal_credential_with_balance,
)

ADDRESS = b"\x11" * 20


def _credentials(spec, prefix, increments):
    return spec.Bytes32(prefix + increments.to_bytes(2, "little") + b"\x00" * 9 + ADDRESS)


def _compounding_validator(spec, increments=0):
    return spec.Validator(
        withdrawal_credentials=_credentials(spec, spec.COMPOUNDING_WITHDRAWAL_PREFIX, increments)
    )


def _eth(spec, amount):
    return spec.Gwei(amount * spec.EFFECTIVE_BALANCE_INCREMENT)


def _threshold_bytes(validator):
    return bytes(validator.withdrawal_credentials[1:3])


def _request(spec, state, index, threshold, source_address=ADDRESS):
    return spec.SetSweepThresholdRequest(
        source_address=spec.ExecutionAddress(source_address),
        validator_pubkey=state.validators[index].pubkey,
        threshold=threshold,
    )


def _prepare_compounding(spec, state, index=0, balance_eth=32):
    set_compounding_withdrawal_credential_with_balance(
        spec, state, index, balance=_eth(spec, balance_eth), address=ADDRESS
    )
    return state.validators[index]


@with_eip8148_and_later
@spec_test
@single_phase
def test_get_sweep_threshold__default(spec):
    assert spec.get_sweep_threshold(_compounding_validator(spec)) == (
        spec.MAX_EFFECTIVE_BALANCE_ELECTRA
    )


@with_eip8148_and_later
@spec_test
@single_phase
def test_get_sweep_threshold__custom(spec):
    for amount in (32, 128, 1000, 2047, 2048):
        assert spec.get_sweep_threshold(_compounding_validator(spec, amount)) == _eth(spec, amount)


@with_eip8148_and_later
@spec_test
@single_phase
def test_get_sweep_threshold__out_of_range_is_default(spec):
    for increments in (1, 31, 2049, 0xFFFF):
        validator = _compounding_validator(spec, increments)
        assert spec.get_sweep_threshold(validator) == spec.MAX_EFFECTIVE_BALANCE_ELECTRA


@with_eip8148_and_later
@spec_test
@single_phase
def test_get_sweep_threshold__non_compounding_ignores_bytes(spec):
    validator = spec.Validator(
        withdrawal_credentials=_credentials(spec, spec.ETH1_ADDRESS_WITHDRAWAL_PREFIX, 128)
    )
    assert spec.get_sweep_threshold(validator) == spec.MIN_ACTIVATION_BALANCE


@with_eip8148_and_later
@spec_test
@single_phase
def test_set_sweep_threshold__little_endian(spec):
    validator = _compounding_validator(spec)
    original = bytes(validator.withdrawal_credentials)

    spec.set_sweep_threshold(validator, _eth(spec, 1000))

    assert _threshold_bytes(validator) == b"\xe8\x03"
    assert bytes(validator.withdrawal_credentials)[:1] == original[:1]
    assert bytes(validator.withdrawal_credentials)[3:] == original[3:]
    assert spec.get_sweep_threshold(validator) == _eth(spec, 1000)


@with_eip8148_and_later
@spec_test
@single_phase
def test_set_sweep_threshold__max_restores_credentials(spec):
    validator = _compounding_validator(spec)
    original = validator.withdrawal_credentials

    spec.set_sweep_threshold(validator, _eth(spec, 128))
    assert validator.withdrawal_credentials != original

    spec.set_sweep_threshold(validator, spec.MAX_EFFECTIVE_BALANCE_ELECTRA)
    assert validator.withdrawal_credentials == original


@with_eip8148_and_later
@spec_test
@single_phase
def test_get_validator_from_deposit__caps_effective_balance(spec):
    credentials = _credentials(spec, spec.COMPOUNDING_WITHDRAWAL_PREFIX, 32)
    validator = spec.get_validator_from_deposit(
        spec.BLSPubkey(b"\x22" * 48), credentials, spec.MAX_EFFECTIVE_BALANCE_ELECTRA
    )

    assert validator.withdrawal_credentials == credentials
    assert validator.effective_balance == spec.MIN_ACTIVATION_BALANCE


@with_eip8148_and_later
@spec_test
@single_phase
def test_get_validator_from_deposit__normalizes_threshold(spec):
    for increments in (5, 2048, 3000):
        credentials = _credentials(spec, spec.COMPOUNDING_WITHDRAWAL_PREFIX, increments)
        validator = spec.get_validator_from_deposit(
            spec.BLSPubkey(b"\x22" * 48), credentials, spec.MAX_EFFECTIVE_BALANCE_ELECTRA
        )

        assert _threshold_bytes(validator) == b"\x00\x00"
        assert validator.effective_balance == spec.MAX_EFFECTIVE_BALANCE_ELECTRA


@with_eip8148_and_later
@spec_state_test
def test_process_set_sweep_threshold_request__success(spec, state):
    validator = _prepare_compounding(spec, state)

    spec.process_set_sweep_threshold_request(state, _request(spec, state, 0, _eth(spec, 64)))

    assert _threshold_bytes(validator) == (64).to_bytes(2, "little")
    assert spec.get_sweep_threshold(validator) == _eth(spec, 64)
    assert bytes(validator.withdrawal_credentials[12:]) == ADDRESS


@with_eip8148_and_later
@spec_state_test
def test_process_set_sweep_threshold_request__max_restores_credentials(spec, state):
    validator = _prepare_compounding(spec, state)
    original = validator.withdrawal_credentials

    spec.process_set_sweep_threshold_request(state, _request(spec, state, 0, _eth(spec, 64)))
    spec.process_set_sweep_threshold_request(
        state, _request(spec, state, 0, spec.MAX_EFFECTIVE_BALANCE_ELECTRA)
    )

    assert validator.withdrawal_credentials == original


def _assert_request_ignored(spec, state, request, index=0):
    credentials = state.validators[index].withdrawal_credentials
    spec.process_set_sweep_threshold_request(state, request)
    assert state.validators[index].withdrawal_credentials == credentials


@with_eip8148_and_later
@spec_state_test
def test_process_set_sweep_threshold_request__unknown_pubkey(spec, state):
    _prepare_compounding(spec, state)
    request = _request(spec, state, 0, _eth(spec, 64))
    request.validator_pubkey = spec.BLSPubkey(b"\x33" * 48)
    _assert_request_ignored(spec, state, request)


@with_eip8148_and_later
@spec_state_test
def test_process_set_sweep_threshold_request__not_compounding(spec, state):
    set_eth1_withdrawal_credential_with_balance(spec, state, 0, address=ADDRESS)
    _assert_request_ignored(spec, state, _request(spec, state, 0, _eth(spec, 64)))


@with_eip8148_and_later
@spec_state_test
def test_process_set_sweep_threshold_request__wrong_source_address(spec, state):
    _prepare_compounding(spec, state)
    request = _request(spec, state, 0, _eth(spec, 64), source_address=b"\x44" * 20)
    _assert_request_ignored(spec, state, request)


@with_eip8148_and_later
@spec_state_test
def test_process_set_sweep_threshold_request__exiting(spec, state):
    validator = _prepare_compounding(spec, state)
    validator.exit_epoch = spec.get_current_epoch(state) + 1
    _assert_request_ignored(spec, state, _request(spec, state, 0, _eth(spec, 64)))


@with_eip8148_and_later
@spec_state_test
def test_process_set_sweep_threshold_request__below_balance(spec, state):
    _prepare_compounding(spec, state, balance_eth=100)
    _assert_request_ignored(spec, state, _request(spec, state, 0, _eth(spec, 64)))


@with_eip8148_and_later
@spec_state_test
def test_process_set_sweep_threshold_request__not_increment_multiple(spec, state):
    _prepare_compounding(spec, state)
    threshold = _eth(spec, 64) + spec.Gwei(1)
    _assert_request_ignored(spec, state, _request(spec, state, 0, threshold))


@with_eip8148_and_later
@spec_state_test
def test_process_set_sweep_threshold_request__below_min_activation_balance(spec, state):
    _prepare_compounding(spec, state, balance_eth=16)
    _assert_request_ignored(spec, state, _request(spec, state, 0, _eth(spec, 31)))


@with_eip8148_and_later
@spec_state_test
def test_process_set_sweep_threshold_request__above_max_effective_balance(spec, state):
    _prepare_compounding(spec, state)
    _assert_request_ignored(spec, state, _request(spec, state, 0, _eth(spec, 2049)))


@with_eip8148_and_later
@spec_state_test
def test_process_effective_balance_updates__capped_at_threshold(spec, state):
    validator = _prepare_compounding(spec, state, balance_eth=32)
    spec.set_sweep_threshold(validator, _eth(spec, 64))
    state.balances[0] = _eth(spec, 100)

    spec.process_effective_balance_updates(state)

    assert validator.effective_balance == _eth(spec, 64)


@with_eip8148_and_later
@spec_state_test
def test_get_validators_sweep_withdrawals__sweeps_above_threshold(spec, state):
    validator = _prepare_compounding(spec, state, balance_eth=64)
    spec.set_sweep_threshold(validator, _eth(spec, 64))
    state.balances[0] = _eth(spec, 65)
    state.next_withdrawal_validator_index = 0

    assert spec.is_partially_withdrawable_validator(validator, state.balances[0])
    withdrawals, _, _ = spec.get_validators_sweep_withdrawals(state, spec.WithdrawalIndex(0), [])

    assert withdrawals[0].validator_index == 0
    assert withdrawals[0].amount == _eth(spec, 1)


@with_eip8148_and_later
@spec_state_test
def test_switch_to_compounding_validator__clears_threshold(spec, state):
    set_eth1_withdrawal_credential_with_balance(spec, state, 0, address=ADDRESS)
    validator = state.validators[0]
    validator.withdrawal_credentials = _credentials(spec, spec.ETH1_ADDRESS_WITHDRAWAL_PREFIX, 128)

    spec.switch_to_compounding_validator(state, 0)

    assert spec.has_compounding_withdrawal_credential(validator)
    assert _threshold_bytes(validator) == b"\x00\x00"
    assert spec.get_sweep_threshold(validator) == spec.MAX_EFFECTIVE_BALANCE_ELECTRA


@with_phases(phases=[HEZE], other_phases=[EIP8148])
@spec_test
@with_state
def test_upgrade_to_eip8148__clears_threshold(spec, phases, state):
    post_spec = phases[EIP8148]
    compounding = state.validators[0]
    compounding.withdrawal_credentials = _credentials(spec, spec.COMPOUNDING_WITHDRAWAL_PREFIX, 128)
    execution = state.validators[1]
    execution.withdrawal_credentials = _credentials(spec, spec.ETH1_ADDRESS_WITHDRAWAL_PREFIX, 128)

    post = post_spec.upgrade_to_eip8148(state)

    assert _threshold_bytes(post.validators[0]) == b"\x00\x00"
    assert post_spec.get_sweep_threshold(post.validators[0]) == (
        post_spec.MAX_EFFECTIVE_BALANCE_ELECTRA
    )
    assert _threshold_bytes(post.validators[1]) == (128).to_bytes(2, "little")
