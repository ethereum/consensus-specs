"""Coverage model for the effective-balance hysteresis and cap boundaries."""

from dataclasses import dataclass

from tests.generators.compliance_runners.state_transition.evaluation.declarations import (
    aspect,
    attribute,
    bind,
    Boolean,
    categorical,
    choose,
    comparison,
    constant,
    coverage_spec,
    factor,
    Integer,
    nwise,
    Plan,
)

from .cases import representatives
from .observation import observe_attributes

balance = attribute("balance", Integer(min=0))
effective_balance = attribute("effective_balance", Integer(min=0))
rounded_balance = attribute("rounded_balance", Integer(min=0))
max_effective_balance = attribute("max_effective_balance", Integer(min=0))
is_compounding = attribute("is_compounding", Boolean())
post_effective_balance = attribute("post_effective_balance", Integer(min=0))

increment = constant("increment", Integer(min=1))
downward_threshold = constant("downward_threshold", Integer(min=0))
upward_threshold = constant("upward_threshold", Integer(min=0))
standard_max = constant("standard_max", Integer(min=1))
compounding_max = constant("compounding_max", Integer(min=1))

CREDENTIAL = aspect(
    "credential",
    categorical(
        "credential_type",
        choose(is_compounding, "COMPOUNDING", "STANDARD"),
        ("STANDARD", "COMPOUNDING"),
    ),
)
GUARDS = aspect(
    "guards",
    comparison("downward_trigger", balance + downward_threshold, effective_balance, op="<"),
    comparison("upward_trigger", effective_balance + upward_threshold, balance, op="<"),
)
RESULT = aspect(
    "result",
    comparison("rounded_vs_cap", rounded_balance, max_effective_balance, op=">="),
    factor("balance_aligned", balance == rounded_balance),
    categorical(
        "outcome",
        choose(
            post_effective_balance == effective_balance,
            "UNCHANGED",
            choose(
                post_effective_balance == max_effective_balance,
                "EFFECTIVE_BALANCE_CAPPED",
                "EFFECTIVE_BALANCE_UPDATED",
            ),
        ),
        ("UNCHANGED", "EFFECTIVE_BALANCE_UPDATED", "EFFECTIVE_BALANCE_CAPPED"),
    ),
)
ASPECTS = (CREDENTIAL, GUARDS, RESULT)
FACTORS = tuple(f for a in ASPECTS for f in a.declarations)


@dataclass(frozen=True)
class ProfileDefinition:
    granularity: str | None
    plan: Plan | None


PROFILE_DEFINITIONS = {
    "smoke": ProfileDefinition("predicate", nwise(FACTORS, 1)),
    "normal": ProfileDefinition("cmp3", nwise(FACTORS, 2)),
    "standard": ProfileDefinition("cmp3", nwise(FACTORS, 2)),
    "max": ProfileDefinition("cmp5", nwise(FACTORS, len(FACTORS))),
    "exceptional": ProfileDefinition(None, None),
}
# The DSL consumes plans; the provider also needs each plan's granularity.
PROFILES = {
    name: definition.plan
    for name, definition in PROFILE_DEFINITIONS.items()
    if definition.plan is not None
}


def constant_feasibility(bound):
    values = (
        bound["increment"],
        bound["downward_threshold"],
        bound["upward_threshold"],
        bound["standard_max"],
        bound["compounding_max"],
    )

    def feasible(assignment, granularity):
        return tuple(sorted(assignment.items())) in representatives(values, granularity)

    return feasible


COVERAGE = coverage_spec(
    "effective_balance_updates",
    focus="process_effective_balance_updates: hysteresis guards, rounding, and cap",
    record="one validator loop iteration per vector",
    attributes=(
        balance,
        effective_balance,
        rounded_balance,
        max_effective_balance,
        is_compounding,
        post_effective_balance,
    ),
    constants=(
        increment,
        downward_threshold,
        upward_threshold,
        standard_max,
        compounding_max,
    ),
    aspects=ASPECTS,
    profiles=PROFILES,
    constant_feasibility=constant_feasibility,
)
TARGET = bind(
    COVERAGE,
    observe_attributes=observe_attributes,
    constants={
        "increment": lambda spec: int(spec.EFFECTIVE_BALANCE_INCREMENT),
        "downward_threshold": lambda spec: (
            int(spec.EFFECTIVE_BALANCE_INCREMENT)
            // int(spec.HYSTERESIS_QUOTIENT)
            * int(spec.HYSTERESIS_DOWNWARD_MULTIPLIER)
        ),
        "upward_threshold": lambda spec: (
            int(spec.EFFECTIVE_BALANCE_INCREMENT)
            // int(spec.HYSTERESIS_QUOTIENT)
            * int(spec.HYSTERESIS_UPWARD_MULTIPLIER)
        ),
        "standard_max": lambda spec: int(spec.MAX_EFFECTIVE_BALANCE),
        "compounding_max": lambda spec: int(spec.MAX_EFFECTIVE_BALANCE_ELECTRA),
    },
)
