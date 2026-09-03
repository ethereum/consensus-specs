from tests.generators.compliance_runners.state_transition.aspects.base import (
    _to_bool,
    validator,
)
from tests.generators.compliance_runners.state_transition.aspects.builder_withdrawals.pending_withdrawal_validator import (
    pending_withdrawal_validator,
)
from tests.generators.compliance_runners.state_transition.aspects.withdrawal_processing.builder_pending_withdrawal_processing import (
    BuilderPendingWithdrawalProcessing,
)


@validator
def builder_pending_withdrawal_processing_validator(
    spec,
    beacon_state,
    solution: BuilderPendingWithdrawalProcessing,
    builder_pending_withdrawal_index: int,
) -> bool:
    """
    - `builder_pending_withdrawal_index` is the index in `beacon_state.builder_pending_withdrawals`
        of the materialized pending withdrawal.
    """
    if not pending_withdrawal_validator(
        spec, beacon_state, solution.pending_withdrawal, builder_pending_withdrawal_index
    ):
        return False

    return solution.state_latest_block_hash_match == _to_bool(
        beacon_state.latest_block_hash == beacon_state.latest_execution_payload_bid.block_hash
    )
