"""Coverage target for the assertion slice of Gloas ``process_block_header``.

The operation vectors provide a ``BeaconBlock`` in
``block_header.ssz_snappy``. Signature verification and the rest of
``process_block`` are intentionally out of scope.
"""

from tests.generators.compliance_runners.state_transition.evaluation.declarations import (
    aspect,
    assertion,
    assertion_set,
    attribute,
    bind,
    Boolean,
    cmp5,
    coverage_spec,
    dimension,
    each,
    Integer,
    predicate,
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
    assertion("slot_matches_state", cmp5(block_slot, state_slot, op="==")),
    assertion("slot_is_newer", cmp5(block_slot, latest_header_slot, op=">")),
    assertion(
        "proposer_index_matches", predicate(proposer_index, expected_proposer_index, op="==")
    ),
    assertion("parent_matches", parent_root_match),
    # Availability of the validator lookup, rather than a coverage dimension.
    assertion("proposer_not_slashed", ~proposer_slashed, available_when=proposer_found),
)

OUTCOME = aspect("outcome", dimension("accepted", post_present))
ASPECTS = (HEADER, OUTCOME)


ASSERTIONS = assertion_set(HEADER, observed=OUTCOME.ref("accepted"), complete=True)


def _slot_order_is_reachable(assignment):
    """latest_header_slot <= state_slot implies block-header delta >= block-state delta."""
    buckets = ("LT_FAR", "LT_1", "EQ", "GT_1", "GT_FAR")
    match = assignment.get("slot_matches_state")
    newer = assignment.get("slot_is_newer")
    return match is None or newer is None or buckets.index(newer) >= buckets.index(match)


PROFILES = {
    "smoke": each([*HEADER.declarations, *OUTCOME.declarations]),
    "normal": ASSERTIONS.normal(HEADER.exhaustive()),
    "exceptional": ASSERTIONS.exceptional(HEADER.nwise(2), faults=1),
    "max": union(ASSERTIONS.normal(HEADER.exhaustive()), ASSERTIONS.exceptional(HEADER.nwise(2))),
    "standard": union(
        each([*HEADER.declarations, *OUTCOME.declarations]),
        HEADER.each() * OUTCOME.each(),
    ),
}

COVERAGE = coverage_spec(
    "block_header",
    focus="assertions in process_block_header; signature verification and the rest of process_block excluded",
    record="one vector",
    aspects=ASPECTS,
    profiles=PROFILES,
    assertions=ASSERTIONS,
    feasible=_slot_order_is_reachable,
)

TARGET = bind(COVERAGE, observe_attributes=observe_attributes, constants={})
