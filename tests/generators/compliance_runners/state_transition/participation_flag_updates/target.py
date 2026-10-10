"""Coverage target for ``process_participation_flag_updates``.

The handler rotates the previous/current participation arrays and replaces the
current array with zero flags.  The target records validator-set size and the
contents of both arrays before rotation.
"""

from tests.generators.compliance_runners.state_transition.evaluation.declarations import (
    aspect,
    attribute,
    bind,
    constant,
    coverage_spec,
    dimension,
    Integer,
)

from .observation import observe_attributes

validator_count = attribute("validator_count", Integer(min=0))
previous_nonzero_count = attribute("previous_nonzero_count", Integer(min=0))
current_nonzero_count = attribute("current_nonzero_count", Integer(min=0))
minimum_validator_count = constant("minimum_validator_count", Integer(min=0))

PARTICIPATION = aspect(
    "participation",
    dimension("validator_set_is_larger", validator_count > minimum_validator_count),
    dimension("previous_has_flags", previous_nonzero_count > 0),
    dimension("current_has_flags", current_nonzero_count > 0),
)
ASPECTS = (PARTICIPATION,)
PROFILES = {
    "smoke": PARTICIPATION.each(),
    "normal": PARTICIPATION.exhaustive(),
    "max": PARTICIPATION.exhaustive(),
    "standard": PARTICIPATION.exhaustive(),
}

COVERAGE = coverage_spec(
    "participation_flag_updates",
    focus="process_participation_flag_updates: validator-set size and participation-array contents",
    record="one vector",
    attributes=(
        validator_count,
        previous_nonzero_count,
        current_nonzero_count,
    ),
    constants=(minimum_validator_count,),
    aspects=ASPECTS,
    profiles=PROFILES,
)

TARGET = bind(
    COVERAGE,
    observe_attributes=observe_attributes,
    constants={
        "minimum_validator_count": lambda spec: int(spec.config.MIN_GENESIS_ACTIVE_VALIDATOR_COUNT)
    },
)
