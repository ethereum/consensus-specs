import random


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
    set_eth1_withdrawal_credential_with_balance(spec, state, index, spec.MAX_EFFECTIVE_BALANCE + excess_balance)
    validator = state.validators[index]

    assert spec.is_partially_withdrawable_validator(validator, state.balances[index])


def prepare_expected_withdrawals(spec, state,
                                 num_full_withdrawals=0, num_partial_withdrawals=0, rng=random.Random(5566)):
    bound = min(len(state.validators), spec.MAX_VALIDATORS_PER_WITHDRAWALS_SWEEP)
    assert num_full_withdrawals + num_partial_withdrawals <= bound
    eligible_validator_indices = list(range(bound))
    sampled_indices = rng.sample(eligible_validator_indices, num_full_withdrawals + num_partial_withdrawals)
    fully_withdrawable_indices = rng.sample(sampled_indices, num_full_withdrawals)
    partial_withdrawals_indices = list(set(sampled_indices).difference(set(fully_withdrawable_indices)))

    for index in fully_withdrawable_indices:
        set_validator_fully_withdrawable(spec, state, index)
    for index in partial_withdrawals_indices:
        set_validator_partially_withdrawable(spec, state, index)

    return fully_withdrawable_indices, partial_withdrawals_indices
