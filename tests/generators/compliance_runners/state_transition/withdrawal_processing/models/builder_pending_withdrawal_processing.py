from dataclasses import dataclass

from tests.generators.compliance_runners.state_transition.aspects.base import (
    Bool,
    constraint,
    Record,
)
from tests.generators.compliance_runners.state_transition.aspects.builder_withdrawals.pending_withdrawal import (
    BuilderPendingWithdrawal,
    pending_withdrawal_constraints,
)


@dataclass
class BuilderPendingWithdrawalProcessing(Record):
    state_latest_block_hash_match: Bool
    pending_withdrawal: BuilderPendingWithdrawal


@constraint
def builder_pending_withdrawal_processing_constraints(
    p: BuilderPendingWithdrawalProcessing,
) -> None:
    # Apply sub-constraints transitively
    pending_withdrawal_constraints(p.pending_withdrawal)
    # Always true in this test
    assert p.state_latest_block_hash_match == Bool.T
