"""Coverage declaration for Gloas ``process_attester_slashing``."""

from tests.generators.compliance_runners.state_transition.evaluation.declarations import (
    all_of,
    any_of,
    aspect,
    attribute,
    bind,
    Boolean,
    choose,
    coverage_spec,
    dimension,
    exhaustive,
    Finite,
    fix,
    union,
)

from .observation import observe_attributes

data_slashable_input = attribute("observed_attestation_data_slashable", Boolean())
indices_well_formed_input = attribute("observed_attestation_1_indices_well_formed", Boolean())
attestation_1_valid_input = attribute("observed_attestation_1_valid", Boolean())
attestation_2_valid_input = attribute("observed_attestation_2_valid", Boolean())
intersection_size_input = attribute(
    "observed_intersection_size", Finite(("NONE", "ONE", "TWO", "THREE_OR_MORE"))
)
slashable_intersection_input = attribute("observed_slashable_intersection", Boolean())

SLASHABILITY = aspect(
    "slashability",
    dimension("attestation_data_slashable", data_slashable_input),
)
ATTESTATION_1 = aspect(
    "attestation_1",
    dimension("attestation_1_indices_well_formed", indices_well_formed_input),
    dimension("attestation_1_valid", attestation_1_valid_input),
)
ATTESTATION_2 = aspect("attestation_2", dimension("attestation_2_valid", attestation_2_valid_input))
INTERSECTION = aspect(
    "intersection",
    dimension("intersection_size", intersection_size_input),
    dimension("slashable_intersection", slashable_intersection_input),
)
OUTCOME = aspect(
    "outcome",
    dimension(
        "outcome",
        choose(
            (~data_slashable_input, "REJECT_NOT_SLASHABLE"),
            (~indices_well_formed_input, "REJECT_MALFORMED_FIRST_INDICES"),
            (~attestation_1_valid_input, "REJECT_FIRST_ATTESTATION"),
            (~attestation_2_valid_input, "REJECT_SECOND_ATTESTATION"),
            (~slashable_intersection_input, "REJECT_NO_SLASHABLE_INTERSECTION"),
            "ACCEPT",
        ),
    ),
)
ASPECTS = (SLASHABILITY, ATTESTATION_1, ATTESTATION_2, INTERSECTION, OUTCOME)
FACTORS = tuple(f for aspect_ in ASPECTS for f in aspect_.declarations)

VALID_SCENARIOS = (
    (True, True, True, True, "ONE", True, "ACCEPT"),
    (True, True, True, True, "TWO", True, "ACCEPT"),
    (True, True, True, True, "THREE_OR_MORE", True, "ACCEPT"),
    (False, True, True, True, "ONE", True, "REJECT_NOT_SLASHABLE"),
    (True, False, False, True, "NONE", False, "REJECT_MALFORMED_FIRST_INDICES"),
    (True, True, False, True, "ONE", True, "REJECT_FIRST_ATTESTATION"),
    (True, True, True, False, "ONE", True, "REJECT_SECOND_ATTESTATION"),
    (True, True, True, True, "ONE", False, "REJECT_NO_SLASHABLE_INTERSECTION"),
)
SCENARIO_CONSTRAINTS = (
    any_of(
        *(
            all_of(*(factor == value for factor, value in zip(FACTORS, values, strict=True)))
            for values in VALID_SCENARIOS
        )
    ),
)

NORMAL = fix(outcome="ACCEPT") * exhaustive(FACTORS)
EXCEPTIONAL_OUTCOMES = (
    "REJECT_NOT_SLASHABLE",
    "REJECT_FIRST_ATTESTATION",
    "REJECT_MALFORMED_FIRST_INDICES",
    "REJECT_SECOND_ATTESTATION",
    "REJECT_NO_SLASHABLE_INTERSECTION",
)
EXCEPTIONAL = union(*(fix(outcome=outcome) for outcome in EXCEPTIONAL_OUTCOMES))
COVERAGE = coverage_spec(
    "attester_slashing",
    focus="process_attester_slashing: attestation validity and slashable intersection",
    record="one operation",
    aspects=ASPECTS,
    profiles={
        "smoke": OUTCOME.exhaustive(),
        "normal": NORMAL,
        "exceptional": EXCEPTIONAL,
        "standard": union(NORMAL, EXCEPTIONAL),
        "max": exhaustive(FACTORS),
    },
    constraints=SCENARIO_CONSTRAINTS,
)

TARGET = bind(COVERAGE, observe_attributes=observe_attributes, backend="python")
