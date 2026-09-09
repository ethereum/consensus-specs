from dataclasses import dataclass

from tests.generators.compliance_runners.state_transition.aspects.base import (
    Bool,
    Cmp,
    constraint,
    Record,
)
from tests.generators.compliance_runners.state_transition.aspects.builder_withdrawals.builder_sweep import (
    builder_sweep_constraints,
    BuilderSweep,
)


@dataclass
class WithdrawalProcessing(Record):
    state_latest_block_hash_match: Bool
    # 1. Pending builder withdrawals
    builder_pending_withdrawals_exist: Bool
    builder_pending_withdrawals_hit_limit: Bool
    # 2. Pending validator withdrawals
    validator_pending_withdrawals_exist: Bool
    eligible_validator_pending_withdrawals_exist: Bool
    validator_pending_withdrawals_hit_limit: Bool
    # 3. Builder sweep
    builder_sweep: BuilderSweep
    # 4. Validator sweep
    validators_eligible_for_sweep_exist: Bool
    swept_validators_hit_limit: Bool


@constraint
def withdrawal_processing_constraints(p: WithdrawalProcessing) -> None:
    # Apply sub-constraints transitively
    builder_sweep_constraints(p.builder_sweep)

    # Pending builder withdrawal queue constraints
    if p.builder_pending_withdrawals_hit_limit == Bool.T:
        assert p.builder_pending_withdrawals_exist == Bool.T

    # Pending validator withdrawal queue constraints
    if p.eligible_validator_pending_withdrawals_exist == Bool.T:
        assert p.validator_pending_withdrawals_exist == Bool.T
    if p.validator_pending_withdrawals_hit_limit == Bool.T:
        assert p.eligible_validator_pending_withdrawals_exist == Bool.T

    # Additional builder sweep constraints
    # If prior withdrawals exists then
    # having a swept builder implies hitting the limit by the builder sweep in minimal configuration
    # 1 builder pending + 1 validator pending + 1 swept builder == withdrawal_limit (3)
    if (
        p.builder_pending_withdrawals_exist == Bool.T
        and p.eligible_validator_pending_withdrawals_exist == Bool.T
        and p.builder_sweep.cmp_swept_count_zero == Cmp.GT
    ):
        assert p.builder_sweep.swept_builders_hit_withdrawals_limit == Bool.T
    # 0 builder pending + 2 validator pending + 1 swept builder == withdrawal_limit (3)
    if (
        p.builder_pending_withdrawals_exist == Bool.F
        and p.validator_pending_withdrawals_hit_limit == Bool.T
        and p.builder_sweep.cmp_swept_count_zero == Cmp.GT
    ):
        assert p.builder_sweep.swept_builders_hit_withdrawals_limit == Bool.T

    # Validator sweep constraints
    if p.swept_validators_hit_limit == Bool.T:
        assert p.validators_eligible_for_sweep_exist == Bool.T

    # Swept count must be zero if the limit is already hit
    if p.builder_pending_withdrawals_hit_limit == Bool.T or (
        p.validator_pending_withdrawals_hit_limit == Bool.T
        # This is needed because the limit for validator partial withdrawals
        # also respects MAX_PENDING_PARTIALS_PER_WITHDRAWALS_SWEEP=2 with minimal preset
        and p.builder_pending_withdrawals_exist == Bool.T
    ):
        assert p.builder_sweep.cmp_swept_count_zero == Cmp.EQ

    # Exclusivity of hitting the withdrawals limit: the sources drain in order
    # (builder pending -> validator partial -> builder sweep), so an earlier
    # source hitting the limit precludes the later sources from doing so.
    if p.builder_pending_withdrawals_hit_limit == Bool.T:
        assert p.validator_pending_withdrawals_hit_limit == Bool.F

    # Reduce the space of block_hash matching failures
    if p.state_latest_block_hash_match == Bool.F:
        assert p.builder_pending_withdrawals_exist == Bool.T
        assert p.eligible_validator_pending_withdrawals_exist == Bool.T
        assert p.builder_sweep.cmp_swept_count_zero == Cmp.GT
        assert p.swept_validators_hit_limit == Bool.T
