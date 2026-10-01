"""Coverage target for the assertion slice of Gloas ``process_block_header``.

The operation vectors provide a ``BeaconBlock`` in
``block_header.ssz_snappy``. Signature verification and the rest of
``process_block`` are intentionally out of scope.
"""

from tests.generators.compliance_runners.state_transition.evaluation.coverage_dsl import rules
from tests.generators.compliance_runners.state_transition.evaluation.declarations import (
    aspect,
    attribute,
    bind,
    Boolean,
    comparison,
    coverage_spec,
    each,
    factor,
    fix,
    Integer,
    union,
)

from .observation import observe_attributes

proposer_found = attribute("proposer_found", Boolean())
block_slot = attribute("block_slot", Integer(min=0))
state_slot = attribute("state_slot", Integer(min=0))
latest_header_slot = attribute("latest_header_slot", Integer(min=0))
proposer_index = attribute("proposer_index", Integer(min=0))
expected_proposer_index = attribute("expected_proposer_index", Integer(min=0))
parent_root_match = attribute("parent_root_match", Boolean())
proposer_slashed = attribute("proposer_slashed", Boolean())
post_present = attribute("post_present", Boolean())

HEADER = aspect(
    "header",
    comparison("slot_matches_state", block_slot, state_slot, op="=="),
    comparison("slot_is_newer", block_slot, latest_header_slot, op=">"),
    comparison("proposer_index_matches", proposer_index, expected_proposer_index, op="=="),
    factor("parent_matches", parent_root_match),
    # Availability of the validator lookup, rather than a coverage dimension.
    factor("proposer_not_slashed", ~proposer_slashed, available_when=proposer_found),
)

OUTCOME = aspect("outcome", factor("accepted", post_present))
ACCEPTED = OUTCOME["accepted"]
ASPECTS = (HEADER, OUTCOME)
GATES = list(HEADER.factors)


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
    "smoke": each([*HEADER.declarations, *OUTCOME.declarations]),
    "normal": NORMAL * HEADER.exhaustive(),
    "exceptional": EXCEPTIONAL * HEADER.nwise(2),
    "max": union(NORMAL * HEADER.exhaustive(), EXCEPTIONAL * HEADER.nwise(2)),
    "standard": union(
        each([*HEADER.declarations, *OUTCOME.declarations]),
        HEADER.each() * OUTCOME.each(),
    ),
}

COVERAGE = coverage_spec(
    "block_header",
    focus="assertions in process_block_header; signature verification and the rest of process_block excluded",
    record="one vector",
    attributes=(
        proposer_found,
        block_slot,
        state_slot,
        latest_header_slot,
        proposer_index,
        expected_proposer_index,
        parent_root_match,
        proposer_slashed,
        post_present,
    ),
    constants=(),
    aspects=ASPECTS,
    profiles=PROFILES,
    feasible=FEASIBLE,
)

TARGET = bind(COVERAGE, observe_attributes=observe_attributes, constants={})
