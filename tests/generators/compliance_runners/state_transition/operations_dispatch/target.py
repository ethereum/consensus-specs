"""Declare the five operation-dispatch integration scenarios."""

from tests.generators.compliance_runners.state_transition.evaluation.declarations import (
    all_of,
    aspect,
    attribute,
    bind,
    Boolean,
    choose,
    coverage_spec,
    dimension,
    exhaustive,
    fix,
    Integer,
    union,
)

from .observation import FIELDS, observe_attributes

counts = {field: attribute(f"observed_{field}_count", Integer(min=0)) for field in FIELDS}
post_input = attribute("observed_post_present", Boolean())
shared_input = attribute("observed_shared_slash_exit", Boolean())
root_input = attribute("observed_payload_root_matches", Boolean())
parent_differs_input = attribute("observed_parent_slot_differs", Boolean())
parent_available_input = attribute("observed_parent_slot_payload_available", Boolean())
attestation_available_input = attribute("observed_attestation_slot_payload_available", Boolean())
index_input = attribute("observed_attestation_index", Integer(min=0))
head_input = attribute("observed_head_flag_set", Boolean())


def shape(**nonempty):
    """Exact list sizes are part of these integration fixtures' contract."""
    return all_of(*(value == nonempty.get(field, 0) for field, value in counts.items()))


ALL_LISTS = all_of(
    shape(**{field: 2 if field == "proposer_slashings" else 1 for field in FIELDS}),
    ~shared_input,
    root_input,
)
SLASH_EXIT = shape(proposer_slashings=1, voluntary_exits=1) & shared_input
BAD_PAYLOAD = shape(payload_attestations=1) & ~root_input
PARENT_SLOT = all_of(
    shape(attestations=1),
    parent_differs_input,
    parent_available_input,
    ~attestation_available_input,
)
scenario = dimension(
    "scenario",
    choose(
        (ALL_LISTS, "all_lists"),
        (SLASH_EXIT, "slash_before_exit"),
        (BAD_PAYLOAD, "invalid_payload_attestation"),
        (PARENT_SLOT & (index_input == 1) & head_input, "parent_slot_matches"),
        (PARENT_SLOT & (index_input == 0) & ~head_input, "parent_slot_mismatches"),
        "UNRECOGNIZED",
    ),
)
accepted = dimension("accepted", post_input)
outcome = dimension("outcome", choose(post_input, "ACCEPT", no="REJECT"))
SCENARIO = aspect("dispatch", scenario)
OUTCOME = aspect("outcome", accepted, outcome)
FACTORS = (*SCENARIO.declarations, *OUTCOME.declarations)
NORMAL = union(
    *(fix(scenario=name) for name in ("all_lists", "parent_slot_matches", "parent_slot_mismatches"))
)
EXCEPTIONAL = union(fix(scenario="slash_before_exit"), fix(scenario="invalid_payload_attestation"))
COVERAGE = coverage_spec(
    "process_operations_dispatch",
    focus="process_operations: nonempty dispatch, slash-before-exit order, payload roots, and parent-slot head flags",
    record="one block",
    aspects=(SCENARIO, OUTCOME),
    constraints=(
        scenario != "UNRECOGNIZED",
        accepted
        == (
            (scenario == "all_lists")
            | (scenario == "parent_slot_matches")
            | (scenario == "parent_slot_mismatches")
        ),
        outcome == choose(accepted, "ACCEPT", no="REJECT"),
    ),
    profiles={
        "smoke": union(fix(scenario="all_lists"), fix(scenario="slash_before_exit")),
        "normal": NORMAL,
        "exceptional": EXCEPTIONAL,
        "standard": exhaustive(FACTORS),
        "max": exhaustive(FACTORS),
    },
)

TARGET = bind(COVERAGE, observe_attributes=observe_attributes, backend="python")
