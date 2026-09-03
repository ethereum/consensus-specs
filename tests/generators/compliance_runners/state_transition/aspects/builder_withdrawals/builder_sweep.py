from dataclasses import dataclass

from tests.generators.compliance_runners.state_transition.aspects.base import (
    Bool,
    Cmp,
    constraint,
    Record,
)


@dataclass
class BuilderSweep(Record):
    cmp_builder_count_withdrawals_limit: Cmp
    cmp_builder_count_max_per_sweep: Cmp
    cmp_eligible_builder_count_zero: Cmp
    cmp_swept_count_zero: Cmp
    cmp_swept_count_max_per_sweep: Cmp
    cmp_next_index_zero: Cmp
    cmp_next_index_last_builder_index: Cmp
    swept_builders_hit_withdrawals_limit: Bool


@constraint
def builder_sweep_constraints(s: BuilderSweep) -> None:
    # Total builder count is always greater than the withdrawals limit
    assert s.cmp_builder_count_withdrawals_limit == Cmp.GT
    # Sweep eligible builder count >= 0
    assert s.cmp_eligible_builder_count_zero in {Cmp.EQ, Cmp.GT}

    # If no sweep eligible builders in the builder set
    if s.cmp_eligible_builder_count_zero == Cmp.EQ:
        # the swept count is zero
        assert s.cmp_swept_count_zero == Cmp.EQ
        assert s.swept_builders_hit_withdrawals_limit == Bool.F

    # Number of swept builders >= 0
    assert s.cmp_swept_count_zero in {Cmp.EQ, Cmp.GT}
    # Number of swept builders < MAX_BUILDERS_PER_WITHDRAWALS_SWEEP
    assert s.cmp_swept_count_max_per_sweep == Cmp.LT
    # If a number of swept builders == 0
    if s.cmp_swept_count_zero == Cmp.EQ:
        # there is no way to hit the limit
        assert s.swept_builders_hit_withdrawals_limit == Bool.F

    if s.cmp_builder_count_max_per_sweep in {Cmp.LT, Cmp.EQ}:
        assert (s.cmp_swept_count_zero == Cmp.GT) == (s.cmp_eligible_builder_count_zero == Cmp.GT)

    assert s.cmp_next_index_zero in {Cmp.EQ, Cmp.GT}
    assert s.cmp_next_index_last_builder_index in {Cmp.LT, Cmp.EQ}
    if s.cmp_next_index_last_builder_index == Cmp.EQ:
        assert s.cmp_next_index_zero == Cmp.GT
