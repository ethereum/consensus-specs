from dataclasses import dataclass

from tests.generators.compliance_runners.state_transition.aspects.base import (
    Cmp,
    constraint,
    OpBool,
    Record,
)
from tests.generators.compliance_runners.state_transition.aspects.builder.builder import (
    Builder,
    builder_constraints,
    is_external_builder,
)


@dataclass
class BuilderPendingWithdrawal(Record):
    builder: Builder
    # Pending withdrawal amount vs 0 (all pending withdrawals have amount > 0 by construction)
    cmp_pending_amount_zero: Cmp
    # Builder balance vs pending withdrawal amount (saturation in apply_withdrawals)
    cmp_builder_balance_amount: Cmp


@constraint
def pending_withdrawal_constraints(w: BuilderPendingWithdrawal) -> None:
    # Apply builder_constraints transitively
    builder_constraints(w.builder)
    # The builder is always an external builder
    assert is_external_builder(w.builder)
    # Builder must have pending withdrawals
    assert w.builder.has_pending_withdrawals == OpBool.T
    # Pending withdrawals only come from bids, which require payload_builder_version
    assert w.builder.payload_builder_version == OpBool.T
    # All pending withdrawals have amount > 0 (creation guards in spec)
    assert w.cmp_pending_amount_zero == Cmp.GT
    # Balance vs amount: saturation in apply_withdrawals allows any ordering
    assert w.cmp_builder_balance_amount in {Cmp.LT, Cmp.EQ, Cmp.GT}
