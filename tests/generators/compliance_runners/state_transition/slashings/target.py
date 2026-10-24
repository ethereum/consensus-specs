"""Coverage declaration for Gloas ``process_slashings``."""

from itertools import combinations

from tests.generators.compliance_runners.state_transition.evaluation.declarations import (
    all_of,
    any_of,
    aspect,
    attribute,
    bind,
    coverage_spec,
    dimension,
    exhaustive,
    Finite,
    union,
)

from .observation import observe_attributes

validator_status_input = attribute(
    "observed_validator_status",
    Finite(("UNSLASHED_VALIDATOR", "SLASHED_WAITING", "SLASHED_DUE")),
)
total_slashings_input = attribute(
    "observed_total_slashings", Finite(("ZERO_TOTAL", "PARTIAL_TOTAL", "SATURATED_TOTAL"))
)
penalty_outcome_input = attribute(
    "observed_penalty_outcome",
    Finite(("NO_PENALTY", "PARTIAL_PENALTY", "FULL_PENALTY", "UNDERFLOW_TO_ZERO")),
)
outcome_input = attribute(
    "observed_outcome", Finite(("NO_STATE_CHANGE", "BALANCE_DECREASED", "BALANCE_ZEROED"))
)

VALIDATOR = aspect("validator", dimension("validator_status", validator_status_input))
TOTAL = aspect("total_slashings", dimension("total_slashings", total_slashings_input))
PENALTY = aspect("penalty", dimension("penalty_outcome", penalty_outcome_input))
OUTCOME = aspect("outcome", dimension("outcome", outcome_input))
ASPECTS = (VALIDATOR, TOTAL, PENALTY, OUTCOME)
FACTORS = tuple(f for aspect_ in ASPECTS for f in aspect_.declarations)
NORMAL = union(
    *(left.exhaustive() * right.exhaustive() for left, right in combinations(ASPECTS, 2))
)

valid_scenarios = (
    ("UNSLASHED_VALIDATOR", "SATURATED_TOTAL", "NO_PENALTY", "NO_STATE_CHANGE"),
    ("SLASHED_WAITING", "SATURATED_TOTAL", "NO_PENALTY", "NO_STATE_CHANGE"),
    ("SLASHED_DUE", "ZERO_TOTAL", "NO_PENALTY", "NO_STATE_CHANGE"),
    ("SLASHED_DUE", "PARTIAL_TOTAL", "PARTIAL_PENALTY", "BALANCE_DECREASED"),
    ("SLASHED_DUE", "SATURATED_TOTAL", "FULL_PENALTY", "BALANCE_ZEROED"),
    ("SLASHED_DUE", "SATURATED_TOTAL", "UNDERFLOW_TO_ZERO", "BALANCE_ZEROED"),
)
scenario_constraints = (
    any_of(
        *(
            all_of(*(factor == value for factor, value in zip(FACTORS, scenario, strict=True)))
            for scenario in valid_scenarios
        )
    ),
)

COVERAGE = coverage_spec(
    "slashings",
    focus="process_slashings: validator timing, slashing total, penalty, and balance result",
    record="one vector",
    aspects=ASPECTS,
    profiles={
        "smoke": OUTCOME.exhaustive(),
        "normal": NORMAL,
        "max": exhaustive(FACTORS),
        "standard": NORMAL,
    },
    constraints=scenario_constraints,
)

TARGET = bind(COVERAGE, observe_attributes=observe_attributes, backend="python")
