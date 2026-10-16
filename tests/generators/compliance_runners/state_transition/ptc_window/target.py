"""Coverage declaration for Gloas ``process_ptc_window``."""

from tests.generators.compliance_runners.state_transition.evaluation.declarations import (
    aspect,
    attribute,
    bind,
    coverage_spec,
    dimension,
    Finite,
    union,
)

from .observation import observe_attributes

epoch_position_input = attribute(
    "observed_epoch_position", Finite(("GENESIS_END", "LATER_EPOCH_END"))
)
validator_count_input = attribute("observed_validator_count", Finite(("MINIMUM", "MANY")))
validator_balance_input = attribute(
    "observed_validator_balance", Finite(("MINIMUM_BALANCE", "MAXIMUM_BALANCE", "MIXED_BALANCE"))
)
validator_activity_input = attribute(
    "observed_validator_activity", Finite(("ALL_ACTIVE", "SOME_INACTIVE"))
)

EPOCH_CONTEXT = aspect("epoch_context", dimension("epoch_position", epoch_position_input))
STATE = aspect(
    "state",
    dimension("validator_count", validator_count_input),
    dimension("validator_balance", validator_balance_input),
    dimension("validator_activity", validator_activity_input),
)

COVERAGE = coverage_spec(
    "ptc_window",
    focus="process_ptc_window: epoch position, validator count, balance, and activity",
    record="one vector",
    aspects=(EPOCH_CONTEXT, STATE),
    profiles={
        "smoke": union(EPOCH_CONTEXT.each(), STATE.exhaustive()),
        "normal": EPOCH_CONTEXT.exhaustive() * STATE.exhaustive(),
        "max": EPOCH_CONTEXT.exhaustive() * STATE.exhaustive(),
        "standard": EPOCH_CONTEXT.exhaustive() * STATE.exhaustive(),
    },
)

TARGET = bind(COVERAGE, observe_attributes=observe_attributes, backend="python")
