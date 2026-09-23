"""Coverage target for the assertion slice of Gloas ``process_operations``.

The operation-processing loops are intentionally out of scope here: each
``for_ops`` call is covered by the corresponding operation handler target.
This target measures only the deposit prohibition and operation-count limits.
"""

# ruff: noqa: F841 - factor declarations are assignments the body never reads
from __future__ import annotations

from tests.generators.compliance_runners.state_transition.evaluation.coverage_dsl import (
    ACCEPTED,
    capture_observations,
    capture_outcome,
    CAttribute,
    CConstant,
    CFactor,
    Context,
    coverage_aspect,
    CPred,
    each,
    fix,
    nwise,
    nwise_of,
    rules,
    Target,
    union,
)

from .observation import observe_attributes


@coverage_aspect("limits")
def capture_limits(
    deposits: CAttribute[int],
    proposer_slashings: CAttribute[int],
    attester_slashings: CAttribute[int],
    attestations: CAttribute[int],
    voluntary_exits: CAttribute[int],
    bls_to_execution_changes: CAttribute[int],
    payload_attestations: CAttribute[int],
    *,
    proposer_slashings_limit: CConstant[int],
    attester_slashings_limit: CConstant[int],
    attestations_limit: CConstant[int],
    voluntary_exits_limit: CConstant[int],
    bls_to_execution_changes_limit: CConstant[int],
    payload_attestations_limit: CConstant[int],
):
    deposits_empty: CPred = deposits == 0
    proposer_slashings_within_limit: CFactor = proposer_slashings <= proposer_slashings_limit
    attester_slashings_within_limit: CFactor = attester_slashings <= attester_slashings_limit
    attestations_within_limit: CFactor = attestations <= attestations_limit
    voluntary_exits_within_limit: CFactor = voluntary_exits <= voluntary_exits_limit
    bls_to_execution_changes_within_limit: CFactor = (
        bls_to_execution_changes <= bls_to_execution_changes_limit
    )
    payload_attestations_within_limit: CFactor = payload_attestations <= payload_attestations_limit


LIMITS = capture_limits
ASPECTS = (LIMITS, capture_outcome)
ALL_LIMITS = list(LIMITS.factors)
GATES = ALL_LIMITS


def observe(ctx: Context) -> None:
    attributes = observe_attributes(ctx)
    capture_observations(**attributes)
    capture_limits(**attributes)


def _holds(assignment: dict, factor, granularity: str) -> bool | None:
    return (
        None
        if factor.name not in assignment
        else factor.holds(assignment[factor.name], granularity)
    )


def _accepted_iff_all_assertions_hold(assignment: dict, granularity: str) -> bool:
    accepted = _holds(assignment, ACCEPTED, granularity)
    if accepted is None:
        return True
    assertions = [_holds(assignment, factor, granularity) for factor in GATES]
    if accepted:
        return all(value is not False for value in assertions)
    return not all(value is True for value in assertions)


FEASIBLE = rules(_accepted_iff_all_assertions_hold)
NORMAL = fix(accepted=True)
EXCEPTIONAL = fix(accepted=False)

PROFILES = {
    "smoke": each([*ALL_LIMITS, ACCEPTED]).where(FEASIBLE),
    "normal": (NORMAL * LIMITS.exhaustive()).where(FEASIBLE),
    "exceptional": (EXCEPTIONAL * nwise(ALL_LIMITS, 2)).where(FEASIBLE),
    "standard": union(
        each([*ALL_LIMITS, ACCEPTED]),
        nwise_of([LIMITS.each(), capture_outcome.each()], 2),
    ).where(FEASIBLE),
}

TARGET = Target(
    "process_operations",
    ASPECTS,
    observe,
    PROFILES,
    FEASIBLE,
    constants={
        "proposer_slashings_limit": lambda spec: int(spec.MAX_PROPOSER_SLASHINGS),
        "attester_slashings_limit": lambda spec: int(spec.MAX_ATTESTER_SLASHINGS_ELECTRA),
        "attestations_limit": lambda spec: int(spec.MAX_ATTESTATIONS_ELECTRA),
        "voluntary_exits_limit": lambda spec: int(spec.MAX_VOLUNTARY_EXITS),
        "bls_to_execution_changes_limit": lambda spec: int(spec.MAX_BLS_TO_EXECUTION_CHANGES),
        "payload_attestations_limit": lambda spec: int(spec.MAX_PAYLOAD_ATTESTATIONS),
    },
)
