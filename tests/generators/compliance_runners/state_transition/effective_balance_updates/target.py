"""Coverage model for the effective-balance hysteresis and cap boundaries."""

from tests.generators.compliance_runners.state_transition.evaluation.declarations import (
    aspect,
    attribute,
    bind,
    Boolean,
    choose,
    cmp5,
    constant,
    coverage_spec,
    dimension,
    Integer,
    modulo_boundary,
    nwise,
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
    dimension(
        "credential_type",
        choose(is_compounding, "COMPOUNDING", "STANDARD"),
    ),
)
GUARDS = aspect(
    "guards",
    dimension("downward_trigger", cmp5(balance + downward_threshold, effective_balance, op="<")),
    dimension("upward_trigger", cmp5(effective_balance + upward_threshold, balance, op="<")),
)
RESULT = aspect(
    "result",
    dimension("rounded_vs_cap", cmp5(rounded_balance, max_effective_balance, op=">=")),
    dimension("balance_remainder", modulo_boundary(balance, increment)),
    dimension(
        "outcome",
        choose(
            (post_effective_balance == effective_balance, "UNCHANGED"),
            (post_effective_balance == max_effective_balance, "EFFECTIVE_BALANCE_CAPPED"),
            "EFFECTIVE_BALANCE_UPDATED",
        ),
    ),
)
ASPECTS = (CREDENTIAL, GUARDS, RESULT)
FACTORS = tuple(f for a in ASPECTS for f in a.declarations)
COMPARISONS = (*GUARDS.factors, RESULT["rounded_vs_cap"])


PROFILES = {
    "smoke": nwise(FACTORS, 1),
    "normal": nwise(FACTORS, 2),
    "standard": nwise(FACTORS, 2),
    "max": nwise(FACTORS, len(FACTORS)),
}


def constant_feasibility(bound):
    values = (
        bound["increment"],
        bound["downward_threshold"],
        bound["upward_threshold"],
        bound["standard_max"],
        bound["compounding_max"],
    )

    def feasible(assignment):
        return tuple(sorted(assignment.items())) in representatives(values, COMPARISONS)

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
