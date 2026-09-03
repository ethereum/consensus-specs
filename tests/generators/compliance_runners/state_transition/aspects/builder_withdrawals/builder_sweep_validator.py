from tests.generators.compliance_runners.state_transition.aspects.base import (
    _to_bool,
    _to_cmp,
    validator,
)
from tests.generators.compliance_runners.state_transition.aspects.builder_withdrawals.builder_sweep import (
    BuilderSweep,
)


def get_swept_count(spec, beacon_state, prior_withdrawals_count: int = 0) -> int:
    """
    Number of builders swept (withdrawn from) by `get_builders_sweep_withdrawals`
    (specs/gloas/beacon-chain.md) — each swept builder produces exactly one
    withdrawal, so this equals the number of withdrawals produced by the sweep.

    - `prior_withdrawals_count` is the number of withdrawals already produced
      by `get_builder_withdrawals` and `get_pending_partial_withdrawals`
      before the builder sweep starts.
    """
    current_epoch = spec.get_current_epoch(beacon_state)
    builders_count = len(beacon_state.builders)
    if builders_count == 0:
        return 0

    max_per_sweep = int(spec.MAX_BUILDERS_PER_WITHDRAWALS_SWEEP)
    withdrawals_limit = int(spec.MAX_WITHDRAWALS_PER_PAYLOAD) - 1
    builders_limit = min(builders_count, max_per_sweep)

    swept = 0
    builder_index = int(beacon_state.next_withdrawal_builder_index) % builders_count
    for _ in range(builders_limit):
        if prior_withdrawals_count + swept >= withdrawals_limit:
            break
        builder = beacon_state.builders[builder_index]
        if builder.withdrawable_epoch <= current_epoch and int(builder.balance) > 0:
            swept += 1
        builder_index = (builder_index + 1) % builders_count
    return swept


def get_builder_sweep_solution(spec, beacon_state, prior_withdrawals_count: int) -> BuilderSweep:
    builders_count = len(beacon_state.builders)
    next_index = int(beacon_state.next_withdrawal_builder_index)
    max_per_sweep = int(spec.MAX_BUILDERS_PER_WITHDRAWALS_SWEEP)
    withdrawals_limit = int(spec.MAX_WITHDRAWALS_PER_PAYLOAD) - 1

    cmp_builder_count_withdrawals_limit = _to_cmp(builders_count, withdrawals_limit)
    cmp_builder_count_max_per_sweep = _to_cmp(builders_count, max_per_sweep)

    current_epoch = spec.get_current_epoch(beacon_state)
    eligible_count = sum(
        1
        for builder in beacon_state.builders
        if builder.withdrawable_epoch <= current_epoch and int(builder.balance) > 0
    )
    cmp_eligible_builder_count_zero = _to_cmp(eligible_count, 0)

    swept_count = get_swept_count(spec, beacon_state, prior_withdrawals_count)
    cmp_swept_count_zero = _to_cmp(swept_count, 0)
    cmp_swept_count_max_per_sweep = _to_cmp(swept_count, max_per_sweep)
    cmp_next_index_zero = _to_cmp(next_index, 0)
    last_builder_index = builders_count - 1
    cmp_next_index_last_builder_index = _to_cmp(next_index, last_builder_index)
    swept_builders_hit_withdrawals_limit = _to_bool(
        prior_withdrawals_count < withdrawals_limit
        and swept_count + prior_withdrawals_count == withdrawals_limit
    )

    return BuilderSweep(
        cmp_builder_count_withdrawals_limit=cmp_builder_count_withdrawals_limit,
        cmp_builder_count_max_per_sweep=cmp_builder_count_max_per_sweep,
        cmp_eligible_builder_count_zero=cmp_eligible_builder_count_zero,
        cmp_swept_count_zero=cmp_swept_count_zero,
        cmp_swept_count_max_per_sweep=cmp_swept_count_max_per_sweep,
        cmp_next_index_zero=cmp_next_index_zero,
        cmp_next_index_last_builder_index=cmp_next_index_last_builder_index,
        swept_builders_hit_withdrawals_limit=swept_builders_hit_withdrawals_limit,
    )


@validator
def builder_sweep_validator(
    spec,
    beacon_state,
    solution: BuilderSweep,
    prior_withdrawals_count: int = 0,
) -> bool:
    """
    Validates the builder sweep aspect against `beacon_state` for the sweep
    portion of `get_builders_sweep_withdrawals`
    (specs/gloas/beacon-chain.md).

    - `prior_withdrawals_count` is the number of withdrawals already produced
      by `get_builder_withdrawals` and `get_pending_partial_withdrawals`
      before the builder sweep starts.
    """
    materialized = get_builder_sweep_solution(spec, beacon_state, prior_withdrawals_count)
    return materialized == solution
