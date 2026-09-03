from tests.generators.compliance_runners.state_transition.aspects.base import (
    _to_bool,
    validator,
)
from tests.generators.compliance_runners.state_transition.aspects.builder.builder import (
    Builder as BuilderSolution,
    is_self_builder,
)
from tests.generators.compliance_runners.state_transition.aspects.builder.builder_validator import (
    get_builder_solution,
)
from tests.generators.compliance_runners.state_transition.aspects.builder_withdrawals.builder_sweep_validator import (
    builder_sweep_validator,
)
from tests.generators.compliance_runners.state_transition.aspects.builder_withdrawals.pending_withdrawal import (
    BuilderPendingWithdrawal as BuilderPendingWithdrawalSolution,
)
from tests.generators.compliance_runners.state_transition.aspects.builder_withdrawals.pending_withdrawal_validator import (
    get_pending_withdrawal_solution,
)
from tests.generators.compliance_runners.state_transition.aspects.validator_withdrawals.pending_partial_withdrawal import (
    ValidatorPendingPartialWithdrawal as ValidatorPendingPartialWithdrawalSolution,
)
from tests.generators.compliance_runners.state_transition.aspects.validator_withdrawals.pending_partial_withdrawal_validator import (
    get_pending_partial_withdrawal_solution,
)
from tests.generators.compliance_runners.state_transition.aspects.withdrawal_processing.withdrawal_processing import (
    WithdrawalProcessing,
)


@validator
def withdrawal_processing_validator(
    spec,
    beacon_state,
    solution: WithdrawalProcessing,
    all_builder_solutions: list[BuilderSolution],
    all_builder_pending_withdrawal_solutions: list[BuilderPendingWithdrawalSolution],
    all_validator_pending_withdrawal_solutions: list[ValidatorPendingPartialWithdrawalSolution],
) -> bool:
    """
    Validates the withdrawal processing aspect against `beacon_state` for
    `process_withdrawals` (specs/gloas/beacon-chain.md).

    - `all_builder_solutions` is all possible builder solutions obtained
      from the Builder model,
    - `all_builder_pending_withdrawal_solutions` is all possible pending withdrawal
      solutions obtained from the BuilderPendingWithdrawal model,
    - `all_validator_pending_withdrawal_solutions` is all possible pending partial
      withdrawal solutions obtained from the ValidatorPendingPartialWithdrawal
      model.
    """
    # Each builder must not be a self builder and must satisfy one of the
    # possible builder solutions.
    for idx in range(len(beacon_state.builders)):
        builder_solution = get_builder_solution(spec, beacon_state, idx)
        if is_self_builder(builder_solution):
            return False
        if builder_solution not in all_builder_solutions:
            return False

    # Each builder pending withdrawal in the queue must satisfy one of the possible
    # pending withdrawal solutions.
    for i in range(len(beacon_state.builder_pending_withdrawals)):
        pending_withdrawal_solution = get_pending_withdrawal_solution(spec, beacon_state, i)
        if pending_withdrawal_solution not in all_builder_pending_withdrawal_solutions:
            return False

    # Each validator pending withdrawal in the queue must satisfy one of the
    # possible pending partial withdrawal solutions.
    for i in range(len(beacon_state.pending_partial_withdrawals)):
        pending_partial_withdrawal_solution = get_pending_partial_withdrawal_solution(
            spec, beacon_state, i
        )
        if pending_partial_withdrawal_solution not in all_validator_pending_withdrawal_solutions:
            return False

    state_latest_block_hash_match = _to_bool(
        beacon_state.latest_block_hash == beacon_state.latest_execution_payload_bid.block_hash
    )
    builder_pending_withdrawals_exist = _to_bool(len(beacon_state.builder_pending_withdrawals) > 0)
    validator_pending_withdrawals_exist = _to_bool(
        len(beacon_state.pending_partial_withdrawals) > 0
    )
    current_epoch = spec.get_current_epoch(beacon_state)
    eligible_validator_pending_withdrawals_exist = _to_bool(
        any(w.withdrawable_epoch <= current_epoch for w in beacon_state.pending_partial_withdrawals)
    )
    validators_eligible_for_sweep_exist = _to_bool(
        any(
            spec.is_fully_withdrawable_validator(validator, beacon_state.balances[i], current_epoch)
            or spec.is_partially_withdrawable_validator(validator, beacon_state.balances[i])
            for i, validator in enumerate(beacon_state.validators)
        )
    )

    withdrawals_limit = int(spec.MAX_WITHDRAWALS_PER_PAYLOAD) - 1
    expected_withdrawals = spec.get_expected_withdrawals(beacon_state)
    builder_pending_withdrawals_hit_limit = _to_bool(
        expected_withdrawals.processed_builder_withdrawals_count == withdrawals_limit
    )
    validator_pending_withdrawals_hit_limit = _to_bool(
        expected_withdrawals.processed_builder_withdrawals_count < withdrawals_limit
        and (
            (
                expected_withdrawals.processed_builder_withdrawals_count
                + expected_withdrawals.processed_partial_withdrawals_count
            )
            == withdrawals_limit
            or expected_withdrawals.processed_partial_withdrawals_count
            == int(spec.MAX_PENDING_PARTIALS_PER_WITHDRAWALS_SWEEP)
        )
    )
    swept_validators_hit_limit = _to_bool(
        len(expected_withdrawals.withdrawals) == int(spec.MAX_WITHDRAWALS_PER_PAYLOAD)
    )

    withdrawals_prior_builder_sweep_count = (
        expected_withdrawals.processed_builder_withdrawals_count
        + expected_withdrawals.processed_partial_withdrawals_count
    )
    if not builder_sweep_validator(
        spec, beacon_state, solution.builder_sweep, withdrawals_prior_builder_sweep_count
    ):
        return False

    materialized = WithdrawalProcessing(
        state_latest_block_hash_match=state_latest_block_hash_match,
        builder_pending_withdrawals_exist=builder_pending_withdrawals_exist,
        validator_pending_withdrawals_exist=validator_pending_withdrawals_exist,
        eligible_validator_pending_withdrawals_exist=eligible_validator_pending_withdrawals_exist,
        validators_eligible_for_sweep_exist=validators_eligible_for_sweep_exist,
        builder_pending_withdrawals_hit_limit=builder_pending_withdrawals_hit_limit,
        validator_pending_withdrawals_hit_limit=validator_pending_withdrawals_hit_limit,
        swept_validators_hit_limit=swept_validators_hit_limit,
        builder_sweep=solution.builder_sweep,
    )

    return materialized == solution
