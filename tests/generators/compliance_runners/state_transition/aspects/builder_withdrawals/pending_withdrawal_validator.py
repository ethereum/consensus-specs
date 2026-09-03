from tests.generators.compliance_runners.state_transition.aspects.base import (
    _to_op_cmp,
    validator,
)
from tests.generators.compliance_runners.state_transition.aspects.builder.builder_validator import (
    builder_validator,
    get_builder_solution,
)
from tests.generators.compliance_runners.state_transition.aspects.builder_withdrawals.pending_withdrawal import (
    BuilderPendingWithdrawal,
)


def get_pending_withdrawal_solution(
    spec, beacon_state, builder_pending_withdrawal_index: int
) -> BuilderPendingWithdrawal:
    """
    Materialize the `BuilderPendingWithdrawal` solution corresponding to the
    pending withdrawal at `builder_pending_withdrawal_index` in
    `beacon_state.builder_pending_withdrawals`.
    """
    pending_withdrawal = beacon_state.builder_pending_withdrawals[builder_pending_withdrawal_index]
    builder = get_builder_solution(spec, beacon_state, pending_withdrawal.builder_index)
    cmp_pending_amount_zero = _to_op_cmp(int(pending_withdrawal.amount), 0)
    builder_balance = int(beacon_state.builders[pending_withdrawal.builder_index].balance)
    cmp_builder_balance_amount = _to_op_cmp(builder_balance, int(pending_withdrawal.amount))
    return BuilderPendingWithdrawal(
        builder=builder,
        cmp_pending_amount_zero=cmp_pending_amount_zero,
        cmp_builder_balance_amount=cmp_builder_balance_amount,
    )


@validator
def pending_withdrawal_validator(
    spec,
    beacon_state,
    solution: BuilderPendingWithdrawal,
    builder_pending_withdrawal_index: int,
) -> bool:
    """
    - `builder_pending_withdrawal_index` is the index in `beacon_state.builder_pending_withdrawals`
        of the materialized pending withdrawal.
    """
    pending_withdrawal = beacon_state.builder_pending_withdrawals[builder_pending_withdrawal_index]
    if not builder_validator(
        spec, beacon_state, solution.builder, pending_withdrawal.builder_index
    ):
        return False

    cmp_pending_amount_zero = _to_op_cmp(int(pending_withdrawal.amount), 0)
    builder_balance = int(beacon_state.builders[pending_withdrawal.builder_index].balance)
    cmp_builder_balance_amount = _to_op_cmp(builder_balance, int(pending_withdrawal.amount))

    materialized = BuilderPendingWithdrawal(
        builder=solution.builder,
        cmp_pending_amount_zero=cmp_pending_amount_zero,
        cmp_builder_balance_amount=cmp_builder_balance_amount,
    )

    return materialized == solution
