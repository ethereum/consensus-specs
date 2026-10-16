"""Coverage declaration for Gloas ``process_builder_pending_payments``."""

from itertools import combinations

from tests.generators.compliance_runners.state_transition.evaluation.declarations import (
    aspect,
    attribute,
    bind,
    Boolean,
    choose,
    cmp3,
    count,
    coverage_spec,
    dimension,
    exhaustive,
    Finite,
    implies,
    Integer,
    union,
)

from .observation import observe_attributes

OCCUPANCY = Finite(("EMPTY", "SINGLE", "MULTIPLE", "FULL"))
previous_input = attribute("observed_previous_epoch_occupancy", OCCUPANCY)
weight_input = attribute("observed_target_weight", Integer(min=0))
quorum_input = attribute("observed_payment_quorum", Integer(min=1))
amount_input = attribute("observed_target_amount_nonzero", Boolean())
count_input = attribute("observed_qualifying_payment_count", Integer(min=0))
mixed_input = attribute("observed_mixed_quorum_relations", Boolean())
next_input = attribute("observed_next_epoch_payments_occupancy", OCCUPANCY)
withdrawals_input = attribute("observed_preexisting_withdrawals_count", Integer(min=0))

previous = dimension("previous_epoch_occupancy", previous_input)
weight = dimension(
    "target_weight_to_quorum", cmp3(weight_input, quorum_input, op=">="), when=previous != "EMPTY"
)
amount = dimension("target_amount_nonzero", amount_input, when=previous != "EMPTY")
qualifying_count = dimension("qualifying_payment_count", count(count_input))
mixed = dimension("mixed_quorum_relations", mixed_input)
next_occupancy = dimension("next_epoch_payments_occupancy", next_input)
withdrawals = dimension("preexisting_withdrawals_occupancy", count(withdrawals_input))
outcome = dimension(
    "outcome",
    choose(
        ((previous_input == "EMPTY") & (next_input == "EMPTY"), "NO_STATE_CHANGE"),
        (count_input == 0, "ROTATED_ONLY"),
        (count_input == 1, "APPENDED_ONE_AND_ROTATED"),
        "APPENDED_MULTIPLE_AND_ROTATED",
    ),
)
effect = dimension("state_effected", outcome.value != "NO_STATE_CHANGE")

PREVIOUS = aspect("previous_section", previous, mixed)
QUORUM = aspect("quorum", weight, qualifying_count)
WITHDRAWAL = aspect("withdrawal", amount)
RETAINED = aspect("retained_section", next_occupancy)
EXISTING = aspect("existing_output", withdrawals)
EFFECTS = aspect("effects", outcome, effect)
ASPECTS = (PREVIOUS, QUORUM, WITHDRAWAL, RETAINED, EXISTING, EFFECTS)
FACTORS = tuple(f for a in ASPECTS for f in a.declarations)
# Retain the former effects/count grouping and carry previous-section
# occupancy in conditional projections, including the empty-section branch.
PROJECTIONS = (
    PREVIOUS.exhaustive(),
    exhaustive((previous, weight, qualifying_count)),
    exhaustive((previous, amount)),
    RETAINED.exhaustive(),
    EXISTING.exhaustive(),
    exhaustive((qualifying_count, outcome, effect)),
)
NORMAL = union(*(left * right for left, right in combinations(PROJECTIONS, 2)))
LARGE_PREVIOUS = (previous == "MULTIPLE") | (previous == "FULL")
COVERAGE = coverage_spec(
    "builder_pending_payments",
    focus="process_builder_pending_payments: quorum boundaries, queue rotation, and withdrawal append",
    record="one epoch-processing step",
    aspects=ASPECTS,
    constraints=(
        outcome
        == choose(
            ((previous == "EMPTY") & (next_occupancy == "EMPTY"), "NO_STATE_CHANGE"),
            (qualifying_count == "ZERO", "ROTATED_ONLY"),
            (qualifying_count == "ONE", "APPENDED_ONE_AND_ROTATED"),
            "APPENDED_MULTIPLE_AND_ROTATED",
        ),
        effect == (outcome != "NO_STATE_CHANGE"),
        implies(previous == "EMPTY", (qualifying_count == "ZERO") & ~mixed),
        implies(previous == "SINGLE", (qualifying_count != "MANY") & ~mixed),
        implies((previous == "SINGLE") & ~weight, qualifying_count == "ZERO"),
        implies((previous == "SINGLE") & weight, qualifying_count == "ONE"),
        implies(mixed, LARGE_PREVIOUS & (qualifying_count == "MANY") & ~weight),
        implies(LARGE_PREVIOUS & weight, qualifying_count != "ZERO"),
    ),
    profiles={
        "smoke": exhaustive((outcome,)),
        "normal": NORMAL,
        "standard": NORMAL,
        "max": exhaustive(FACTORS),
    },
)

TARGET = bind(COVERAGE, observe_attributes=observe_attributes, backend="python")
