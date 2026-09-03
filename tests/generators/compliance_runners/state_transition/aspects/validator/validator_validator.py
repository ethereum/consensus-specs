from tests.generators.compliance_runners.state_transition.aspects.base import (
    _to_bool,
    _to_cmp,
    validator,
    ValidatorCredentialKind,
)
from tests.generators.compliance_runners.state_transition.aspects.validator.validator import (
    Validator as ValidatorSolution,
)


def get_validator_solution(spec, beacon_state, validator_index: int) -> ValidatorSolution:
    state_epoch = spec.get_current_epoch(beacon_state)
    validator = beacon_state.validators[validator_index]
    balance = beacon_state.balances[validator_index]

    if spec.has_compounding_withdrawal_credential(validator):
        withdrawal_credential = ValidatorCredentialKind.COMPOUNDING
    elif spec.has_eth1_withdrawal_credential(validator):
        withdrawal_credential = ValidatorCredentialKind.ETH1
    else:
        withdrawal_credential = ValidatorCredentialKind.BLS

    cmp_state_epoch_activation_epoch = _to_cmp(state_epoch, validator.activation_epoch)
    cmp_state_epoch_exit_epoch = _to_cmp(state_epoch, validator.exit_epoch)
    cmp_state_epoch_withdrawal_epoch = _to_cmp(state_epoch, validator.withdrawable_epoch)
    cmp_finalized_epoch_activation_eligibility_epoch = _to_cmp(
        beacon_state.finalized_checkpoint.epoch, validator.activation_eligibility_epoch
    )
    withdrawable_epoch_set = _to_bool(validator.withdrawable_epoch != spec.FAR_FUTURE_EPOCH)
    exit_epoch_set = _to_bool(validator.exit_epoch != spec.FAR_FUTURE_EPOCH)
    cmp_balance_zero = _to_cmp(balance, 0)
    cmp_effective_balance_min_activation_balance = _to_cmp(
        validator.effective_balance, spec.MIN_ACTIVATION_BALANCE
    )
    has_pending_withdrawal = _to_bool(
        any(
            w
            for w in beacon_state.pending_partial_withdrawals
            if w.validator_index == validator_index
        )
    )

    return ValidatorSolution(
        withdrawal_credential=withdrawal_credential,
        cmp_state_epoch_activation_epoch=cmp_state_epoch_activation_epoch,
        cmp_state_epoch_exit_epoch=cmp_state_epoch_exit_epoch,
        cmp_state_epoch_withdrawal_epoch=cmp_state_epoch_withdrawal_epoch,
        cmp_finalized_epoch_activation_eligibility_epoch=cmp_finalized_epoch_activation_eligibility_epoch,
        withdrawable_epoch_set=withdrawable_epoch_set,
        exit_epoch_set=exit_epoch_set,
        cmp_balance_zero=cmp_balance_zero,
        cmp_effective_balance_min_activation_balance=cmp_effective_balance_min_activation_balance,
        has_pending_withdrawal=has_pending_withdrawal,
    )


@validator
def validator_validator(
    spec, beacon_state, solution: ValidatorSolution, validator_index: int
) -> bool:
    """
    - `validator_index` is an index in `beacon_state.validators` list corresponding
    to the instance of the validator materialized from the `solution`.
    """
    materialized_solution = get_validator_solution(spec, beacon_state, validator_index)
    return materialized_solution == solution
