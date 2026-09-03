from tests.generators.compliance_runners.state_transition.aspects.base import (
    _to_bool,
    _to_cmp,
    validator,
)
from tests.generators.compliance_runners.state_transition.aspects.validator.validator_validator import (
    get_validator_solution,
    validator_validator,
)
from tests.generators.compliance_runners.state_transition.aspects.validator_withdrawals.pending_partial_withdrawal import (
    ValidatorPendingPartialWithdrawal,
)


def get_pending_partial_withdrawal_solution(
    spec, beacon_state, pending_partial_withdrawal_index: int
) -> ValidatorPendingPartialWithdrawal:
    """
    Materialize the `ValidatorPendingPartialWithdrawal` solution corresponding to
    the pending partial withdrawal at `pending_partial_withdrawal_index` in
    `beacon_state.pending_partial_withdrawals`.
    """
    pending_withdrawal = beacon_state.pending_partial_withdrawals[pending_partial_withdrawal_index]
    validator = get_validator_solution(spec, beacon_state, pending_withdrawal.validator_index)
    withdrawable = _to_bool(
        pending_withdrawal.withdrawable_epoch <= spec.get_current_epoch(beacon_state)
    )
    cmp_pending_amount_zero = _to_cmp(int(pending_withdrawal.amount), 0)
    balance = int(beacon_state.balances[pending_withdrawal.validator_index])
    cmp_balance_amount = _to_cmp(balance, int(pending_withdrawal.amount))
    return ValidatorPendingPartialWithdrawal(
        validator=validator,
        withdrawable=withdrawable,
        cmp_pending_amount_zero=cmp_pending_amount_zero,
        cmp_balance_amount=cmp_balance_amount,
    )


@validator
def pending_partial_withdrawal_validator(
    spec,
    beacon_state,
    solution: ValidatorPendingPartialWithdrawal,
    pending_partial_withdrawal_index: int,
) -> bool:
    """
    - `pending_partial_withdrawal_index` is the index in
      `beacon_state.pending_partial_withdrawals` of the materialized pending
      partial withdrawal.
    """
    pending_withdrawal = beacon_state.pending_partial_withdrawals[pending_partial_withdrawal_index]
    if not validator_validator(
        spec, beacon_state, solution.validator, pending_withdrawal.validator_index
    ):
        return False

    withdrawable = _to_bool(
        pending_withdrawal.withdrawable_epoch <= spec.get_current_epoch(beacon_state)
    )
    cmp_pending_amount_zero = _to_cmp(int(pending_withdrawal.amount), 0)
    balance = int(beacon_state.balances[pending_withdrawal.validator_index])
    cmp_balance_amount = _to_cmp(balance, int(pending_withdrawal.amount))

    materialized = ValidatorPendingPartialWithdrawal(
        validator=solution.validator,
        withdrawable=withdrawable,
        cmp_pending_amount_zero=cmp_pending_amount_zero,
        cmp_balance_amount=cmp_balance_amount,
    )

    return materialized == solution
