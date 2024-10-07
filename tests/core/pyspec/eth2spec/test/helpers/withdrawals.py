from eth2spec.test.helpers.forks import is_post_electra


def get_expected_withdrawals(spec, state):
    if is_post_electra(spec):
        withdrawals, _ = spec.get_expected_withdrawals(state)
        return withdrawals
    else:
        return spec.get_expected_withdrawals(state)


def set_validator_fully_withdrawable(spec, state, index, withdrawable_epoch=None):
    if withdrawable_epoch is None:
        withdrawable_epoch = spec.get_current_epoch(state)

    validator = state.validators[index]
    validator.withdrawable_epoch = withdrawable_epoch
    # set exit epoch as well to avoid interactions with other epoch process, e.g. forced ejections
    if validator.exit_epoch > withdrawable_epoch:
        validator.exit_epoch = withdrawable_epoch

    if validator.withdrawal_credentials[0:1] == spec.BLS_WITHDRAWAL_PREFIX:
        validator.withdrawal_credentials = spec.ETH1_ADDRESS_WITHDRAWAL_PREFIX + validator.withdrawal_credentials[1:]

    if state.balances[index] == 0:
        state.balances[index] = 10000000000

    assert spec.is_fully_withdrawable_validator(validator, state.balances[index], withdrawable_epoch)


def set_eth1_withdrawal_credential_with_balance(spec, state, index, balance=None, address=None):
    if balance is None:
        balance = spec.MAX_EFFECTIVE_BALANCE
    if address is None:
        address = b'\x11' * 20

    validator = state.validators[index]
    validator.withdrawal_credentials = spec.ETH1_ADDRESS_WITHDRAWAL_PREFIX + b'\x00' * 11 + address
    validator.effective_balance = min(balance, spec.MAX_EFFECTIVE_BALANCE)
    state.balances[index] = balance


def set_validator_partially_withdrawable(spec, state, index, excess_balance=1000000000):
    validator = state.validators[index]
    if is_post_electra(spec) and spec.has_compounding_withdrawal_credential(validator):
        validator.effective_balance = spec.MAX_EFFECTIVE_BALANCE_ELECTRA
        state.balances[index] = validator.effective_balance + excess_balance
    else:
        set_eth1_withdrawal_credential_with_balance(spec, state, index, spec.MAX_EFFECTIVE_BALANCE + excess_balance)

    assert spec.is_partially_withdrawable_validator(state.validators[index], state.balances[index])


def sample_withdrawal_indices(spec, state, rng, num_full_withdrawals, num_partial_withdrawals):
    bound = min(len(state.validators), spec.MAX_VALIDATORS_PER_WITHDRAWALS_SWEEP)
    assert num_full_withdrawals + num_partial_withdrawals <= bound
    eligible_validator_indices = list(range(bound))
    sampled_indices = rng.sample(eligible_validator_indices, num_full_withdrawals + num_partial_withdrawals)
    fully_withdrawable_indices = rng.sample(sampled_indices, num_full_withdrawals)
    partial_withdrawals_indices = list(set(sampled_indices).difference(set(fully_withdrawable_indices)))

    return fully_withdrawable_indices, partial_withdrawals_indices


def prepare_expected_withdrawals(spec, state, rng,
                                 num_full_withdrawals=0, num_partial_withdrawals=0):
    fully_withdrawable_indices, partial_withdrawals_indices = sample_withdrawal_indices(
        spec, state, rng, num_full_withdrawals, num_partial_withdrawals
    )

    for index in fully_withdrawable_indices:
        set_validator_fully_withdrawable(spec, state, index)
    for index in partial_withdrawals_indices:
        set_validator_partially_withdrawable(spec, state, index)

    return fully_withdrawable_indices, partial_withdrawals_indices


def set_compounding_withdrawal_credential(spec, state, index, address=None):
    if address is None:
        address = b'\x11' * 20

    validator = state.validators[index]
    validator.withdrawal_credentials = spec.COMPOUNDING_WITHDRAWAL_PREFIX + b'\x00' * 11 + address


def set_compounding_withdrawal_credential_with_balance(spec, state, index,
                                                       effective_balance=None, balance=None, address=None):
    set_compounding_withdrawal_credential(spec, state, index, address)

    if effective_balance is None:
        effective_balance = spec.MAX_EFFECTIVE_BALANCE_ELECTRA
    if balance is None:
        balance = effective_balance

    state.validators[index].effective_balance = effective_balance
    state.balances[index] = balance


def prepare_expected_withdrawals_compounding(spec, state, rng,
                                             num_full_withdrawals=0,
                                             num_partial_withdrawals_sweep=0,
                                             excess_balance=1000000000):
    assert is_post_electra(spec)

    fully_withdrawable_indices, partial_withdrawals_sweep_indices = sample_withdrawal_indices(
        spec, state, rng, num_full_withdrawals, num_partial_withdrawals_sweep
    )

    for index in fully_withdrawable_indices + partial_withdrawals_sweep_indices:
        address = state.validators[index].withdrawal_credentials[12:]
        set_compounding_withdrawal_credential_with_balance(spec, state, index, address=address)

    for index in fully_withdrawable_indices:
        set_validator_fully_withdrawable(spec, state, index)
    for index in partial_withdrawals_sweep_indices:
        set_validator_partially_withdrawable(spec, state, index)

    return fully_withdrawable_indices, partial_withdrawals_sweep_indices


def prepare_pending_withdrawal(spec, state, validator_index,
                               effective_balance=32_000_000_000, amount=1_000_000_000):
    assert is_post_electra(spec)

    balance = effective_balance + amount
    set_compounding_withdrawal_credential_with_balance(
        spec, state, validator_index, effective_balance, balance
    )

    withdrawal = spec.PendingPartialWithdrawal(
        index=validator_index,
        amount=amount,
        withdrawable_epoch=spec.get_current_epoch(state),
    )
    state.pending_partial_withdrawals.append(withdrawal)

    return withdrawal

#
# Run processing
#


def verify_post_state(state, spec, expected_withdrawals,
                      fully_withdrawable_indices, partial_withdrawals_indices):
    # Consider verifying also the condition when no withdrawals are expected.
    if len(expected_withdrawals) == 0:
        return

    expected_withdrawals_validator_indices = [withdrawal.validator_index for withdrawal in expected_withdrawals]
    assert state.next_withdrawal_index == expected_withdrawals[-1].index + 1

    if len(expected_withdrawals) == spec.MAX_WITHDRAWALS_PER_PAYLOAD:
        # NOTE: ideally we would also check in the case with
        # fewer than maximum withdrawals but that requires the pre-state info
        next_withdrawal_validator_index = (expected_withdrawals_validator_indices[-1] + 1) % len(state.validators)
        assert state.next_withdrawal_validator_index == next_withdrawal_validator_index

    for index in fully_withdrawable_indices:
        if index in expected_withdrawals_validator_indices:
            assert state.balances[index] == 0
        else:
            assert state.balances[index] > 0
    for index in partial_withdrawals_indices:
        if is_post_electra(spec):
            max_effective_balance = spec.get_max_effective_balance(state.validators[index])
        else:
            max_effective_balance = spec.MAX_EFFECTIVE_BALANCE

        if index in expected_withdrawals_validator_indices:
            assert state.balances[index] == max_effective_balance
        else:
            assert state.balances[index] > max_effective_balance


def run_withdrawals_processing(spec, state, execution_payload, num_expected_withdrawals=None,
                               fully_withdrawable_indices=None, partial_withdrawals_indices=None, valid=True):
    """
    Run ``process_withdrawals``, yielding:
      - pre-state ('pre')
      - execution payload ('execution_payload')
      - post-state ('post').
    If ``valid == False``, run expecting ``AssertionError``
    """
    expected_withdrawals = get_expected_withdrawals(spec, state)
    assert len(expected_withdrawals) <= spec.MAX_WITHDRAWALS_PER_PAYLOAD
    if num_expected_withdrawals is not None:
        assert len(expected_withdrawals) == num_expected_withdrawals

    pre_state = state.copy()
    yield 'pre', state
    yield 'execution_payload', execution_payload

    if not valid:
        try:
            spec.process_withdrawals(state, execution_payload)
            raise AssertionError('expected an assertion error, but got none.')
        except AssertionError:
            pass

        yield 'post', None
        return

    spec.process_withdrawals(state, execution_payload)

    yield 'post', state

    if len(expected_withdrawals) == 0:
        next_withdrawal_validator_index = (
            pre_state.next_withdrawal_validator_index + spec.MAX_VALIDATORS_PER_WITHDRAWALS_SWEEP
        )
        assert state.next_withdrawal_validator_index == next_withdrawal_validator_index % len(state.validators)
    elif len(expected_withdrawals) <= spec.MAX_WITHDRAWALS_PER_PAYLOAD:
        bound = min(spec.MAX_VALIDATORS_PER_WITHDRAWALS_SWEEP, spec.MAX_WITHDRAWALS_PER_PAYLOAD)
        assert len(get_expected_withdrawals(spec, state)) <= bound
    elif len(expected_withdrawals) > spec.MAX_WITHDRAWALS_PER_PAYLOAD:
        raise ValueError('len(expected_withdrawals) should not be greater than MAX_WITHDRAWALS_PER_PAYLOAD')

    if fully_withdrawable_indices is not None or partial_withdrawals_indices is not None:
        verify_post_state(state, spec, expected_withdrawals, fully_withdrawable_indices, partial_withdrawals_indices)

    return expected_withdrawals
