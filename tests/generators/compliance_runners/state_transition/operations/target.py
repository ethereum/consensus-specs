"""Coverage target for the assertion slice of Gloas ``process_operations``.

This target measures only the deposit prohibition and operation-count limits.
The sibling ``operations_dispatch`` provider supplies block-level integration
vectors for the operation-processing loops.
"""

from tests.generators.compliance_runners.state_transition.evaluation.coverage_dsl import rules
from tests.generators.compliance_runners.state_transition.evaluation.declarations import (
    aspect,
    attribute,
    bind,
    Boolean,
    comparison,
    constant,
    coverage_spec,
    each,
    factor,
    fix,
    Integer,
    union,
)

from .observation import observe_attributes

deposits = attribute("deposits", Integer(min=0))
proposer_slashings = attribute("proposer_slashings", Integer(min=0))
attester_slashings = attribute("attester_slashings", Integer(min=0))
attestations = attribute("attestations", Integer(min=0))
voluntary_exits = attribute("voluntary_exits", Integer(min=0))
bls_to_execution_changes = attribute("bls_to_execution_changes", Integer(min=0))
payload_attestations = attribute("payload_attestations", Integer(min=0))
post_present = attribute("post_present", Boolean())

proposer_slashings_limit = constant("proposer_slashings_limit", Integer(min=0))
attester_slashings_limit = constant("attester_slashings_limit", Integer(min=0))
attestations_limit = constant("attestations_limit", Integer(min=0))
voluntary_exits_limit = constant("voluntary_exits_limit", Integer(min=0))
bls_to_execution_changes_limit = constant("bls_to_execution_changes_limit", Integer(min=0))
payload_attestations_limit = constant("payload_attestations_limit", Integer(min=0))

LIMITS = aspect(
    "limits",
    factor("deposits_empty", deposits == 0),
    comparison(
        "proposer_slashings_within_limit", proposer_slashings, proposer_slashings_limit, op="<="
    ),
    comparison(
        "attester_slashings_within_limit", attester_slashings, attester_slashings_limit, op="<="
    ),
    comparison("attestations_within_limit", attestations, attestations_limit, op="<="),
    comparison("voluntary_exits_within_limit", voluntary_exits, voluntary_exits_limit, op="<="),
    comparison(
        "bls_to_execution_changes_within_limit",
        bls_to_execution_changes,
        bls_to_execution_changes_limit,
        op="<=",
    ),
    comparison(
        "payload_attestations_within_limit",
        payload_attestations,
        payload_attestations_limit,
        op="<=",
    ),
)

OUTCOME = aspect("outcome", factor("accepted", post_present))
ACCEPTED = OUTCOME["accepted"]
ASPECTS = (LIMITS, OUTCOME)
GATES = list(LIMITS.factors)


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
    "smoke": each([*LIMITS.declarations, *OUTCOME.declarations]),
    "normal": NORMAL * LIMITS.exhaustive(),
    "exceptional": EXCEPTIONAL * LIMITS.nwise(2),
    "standard": union(
        each([*LIMITS.declarations, *OUTCOME.declarations]),
        LIMITS.each() * OUTCOME.each(),
    ),
}

COVERAGE = coverage_spec(
    "process_operations",
    focus="deposit prohibition and operation-count assertions in process_operations; operation-processing loops excluded",
    record="one vector",
    attributes=(
        deposits,
        proposer_slashings,
        attester_slashings,
        attestations,
        voluntary_exits,
        bls_to_execution_changes,
        payload_attestations,
        post_present,
    ),
    constants=(
        proposer_slashings_limit,
        attester_slashings_limit,
        attestations_limit,
        voluntary_exits_limit,
        bls_to_execution_changes_limit,
        payload_attestations_limit,
    ),
    aspects=ASPECTS,
    profiles=PROFILES,
    feasible=FEASIBLE,
)

TARGET = bind(
    COVERAGE,
    observe_attributes=observe_attributes,
    constants={
        "proposer_slashings_limit": lambda spec: int(spec.MAX_PROPOSER_SLASHINGS),
        "attester_slashings_limit": lambda spec: int(spec.MAX_ATTESTER_SLASHINGS_ELECTRA),
        "attestations_limit": lambda spec: int(spec.MAX_ATTESTATIONS_ELECTRA),
        "voluntary_exits_limit": lambda spec: int(spec.MAX_VOLUNTARY_EXITS),
        "bls_to_execution_changes_limit": lambda spec: int(spec.MAX_BLS_TO_EXECUTION_CHANGES),
        "payload_attestations_limit": lambda spec: int(spec.MAX_PAYLOAD_ATTESTATIONS),
    },
)
