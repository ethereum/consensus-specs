from ..base import (
    _to_op_bool,
    _to_op_cmp,
    validator,
)
from .builder import Builder as BuilderSolution, is_self_builder


@validator
def builder_validator(spec, beacon_state, solution: BuilderSolution, builder_index: int) -> bool:
    """
    - `builder_index` is an index in `beacon_state.builders` list corresponding
    to the instance of the builder materialized from the `solution`.
    """
    if is_self_builder(solution):
        return True

    state_epoch = spec.get_current_epoch(beacon_state)
    builder = beacon_state.builders[builder_index]

    payload_builder_version = _to_op_bool(builder.version == spec.PAYLOAD_BUILDER_VERSION)
    cmp_state_epoch_deposit_epoch = _to_op_cmp(state_epoch, builder.deposit_epoch)
    cmp_state_epoch_withdrawal_epoch = _to_op_cmp(state_epoch, builder.withdrawable_epoch)
    cmp_finalized_epoch_deposit_epoch = _to_op_cmp(beacon_state.finalized_checkpoint.epoch, builder.deposit_epoch)
    withdrawable_epoch_set = _to_op_bool(builder.withdrawable_epoch != spec.FAR_FUTURE_EPOCH)
    cmp_balance_zero = _to_op_cmp(builder.balance, 0)
    cmp_balance_min_deposit = _to_op_cmp(builder.balance, spec.MIN_DEPOSIT_AMOUNT)
    has_pending_payments = _to_op_bool(any(
        p for p in beacon_state.builder_pending_payments
        if p.withdrawal.builder_index == builder_index and int(p.withdrawal.amount) > 0
    ))
    has_pending_withdrawals = _to_op_bool(any(
        w for w in beacon_state.builder_pending_withdrawals
        if w.builder_index == builder_index and int(w.amount) > 0
    ))

    materialized_solution = BuilderSolution(
        payload_builder_version=payload_builder_version,
        cmp_state_epoch_deposit_epoch=cmp_state_epoch_deposit_epoch,
        cmp_state_epoch_withdrawal_epoch=cmp_state_epoch_withdrawal_epoch,
        cmp_finalized_epoch_deposit_epoch=cmp_finalized_epoch_deposit_epoch,
        withdrawable_epoch_set=withdrawable_epoch_set,
        cmp_balance_zero=cmp_balance_zero,
        cmp_balance_min_deposit=cmp_balance_min_deposit,
        has_pending_payments=has_pending_payments,
        has_pending_withdrawals=has_pending_withdrawals,
    )

    return materialized_solution == solution
