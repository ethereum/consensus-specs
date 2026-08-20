from dataclasses import dataclass
from ..base import (
    _to_op_bool,
    _to_op_cmp,
    constraint,
    OpBool,
    OpCmp,
    predicate,
    Record,
    validator,
)


@dataclass
class Builder(Record):
    payload_builder_version: OpBool
    cmp_state_epoch_deposit_epoch: OpCmp
    cmp_state_epoch_withdrawal_epoch: OpCmp
    cmp_finalized_epoch_deposit_epoch: OpCmp
    withdrawable_epoch_set: OpBool
    cmp_balance_zero: OpCmp
    cmp_balance_min_deposit: OpCmp
    has_pending_payments: OpBool
    has_pending_withdrawals: OpBool


@predicate
def is_self_builder(b: Builder) -> bool:
    return (
        b.payload_builder_version == OpBool.NA
        and b.cmp_state_epoch_deposit_epoch == OpCmp.NA
        and b.cmp_state_epoch_withdrawal_epoch == OpCmp.NA
        and b.cmp_finalized_epoch_deposit_epoch == OpCmp.NA
        and b.cmp_balance_zero == OpCmp.NA
        and b.cmp_balance_min_deposit == OpCmp.NA
        and b.has_pending_payments == OpBool.NA
        and b.has_pending_withdrawals == OpBool.NA
        and b.withdrawable_epoch_set == OpBool.NA
    )


@predicate
def is_external_builder(b: Builder) -> bool:
    return (
        b.payload_builder_version != OpBool.NA
        and b.cmp_state_epoch_deposit_epoch != OpCmp.NA
        and b.cmp_state_epoch_withdrawal_epoch != OpCmp.NA
        and b.cmp_finalized_epoch_deposit_epoch != OpCmp.NA
        and b.cmp_balance_zero != OpCmp.NA
        and b.cmp_balance_min_deposit != OpCmp.NA
        and b.has_pending_payments != OpBool.NA
        and b.has_pending_withdrawals != OpBool.NA
        and b.withdrawable_epoch_set != OpBool.NA
    )


@predicate
def is_active_builder(b: Builder) -> bool:
    return b.cmp_finalized_epoch_deposit_epoch == OpCmp.GT and b.withdrawable_epoch_set == OpBool.F


@predicate
def has_pending_withdrawals(b: Builder) -> bool:
    return b.has_pending_payments == OpBool.T or b.has_pending_withdrawals == OpBool.T


@constraint
def builder_constraints(b: Builder) -> None:
    assert not is_self_builder(b) == is_external_builder(b)

    if is_self_builder(b):
        return

    assert b.cmp_state_epoch_deposit_epoch in {OpCmp.GT, OpCmp.EQ}
    assert b.cmp_balance_zero in {OpCmp.GT, OpCmp.EQ}
    assert (b.cmp_balance_zero == OpCmp.EQ) == (b.cmp_balance_min_deposit == OpCmp.LT)

    if is_active_builder(b):
        assert b.cmp_balance_min_deposit in {OpCmp.GT, OpCmp.EQ}

    if has_pending_withdrawals(b):
        assert is_active_builder(b)
        assert b.cmp_balance_min_deposit == OpCmp.GT

    if not b.withdrawable_epoch_set:
        assert b.cmp_state_epoch_withdrawal_epoch == OpCmp.LT
