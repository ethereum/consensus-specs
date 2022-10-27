def set_validator_fully_withdrawable(spec, state, index, withdrawable_epoch=None):
    if withdrawable_epoch is None:
        withdrawable_epoch = spec.get_current_epoch(state)

    validator = state.validators[index]
    validator.withdrawable_epoch = withdrawable_epoch
    # set exit epoch as well to avoid interactions with other epoch process, e.g. forced ejecions
    if validator.exit_epoch > withdrawable_epoch:
        validator.exit_epoch = withdrawable_epoch

    if validator.withdrawal_credentials[0:1] == spec.BLS_WITHDRAWAL_PREFIX:
        validator.withdrawal_credentials = spec.ETH1_ADDRESS_WITHDRAWAL_PREFIX + validator.withdrawal_credentials[1:]

    if state.balances[index] == 0:
        state.balances[index] = 10000000000

    assert spec.is_fully_withdrawable_validator(validator, state.balances[index], withdrawable_epoch)


def set_eth1_withdrawal_credential_with_balance(spec, state, index, balance):
    validator = state.validators[index]
    validator.withdrawal_credentials = spec.ETH1_ADDRESS_WITHDRAWAL_PREFIX + validator.withdrawal_credentials[1:]
    validator.effective_balance = min(balance, spec.MAX_EFFECTIVE_BALANCE)
    state.balances[index] = balance


def set_validator_partially_withdrawable(spec, state, index, excess_balance=1000000000):
    set_eth1_withdrawal_credential_with_balance(spec, state, index, spec.MAX_EFFECTIVE_BALANCE + excess_balance)
    validator = state.validators[index]

    assert spec.is_partially_withdrawable_validator(validator, state.balances[index])
