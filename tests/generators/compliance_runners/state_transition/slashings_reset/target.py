"""Coverage target for ``process_slashings_reset``.

The handler selects the next epoch's circular slashings slot and resets it to
zero.  The target records the wraparound case and whether the selected slot
actually contains a value to clear.
"""

from tests.generators.compliance_runners.state_transition.evaluation.declarations import (
    aspect,
    attribute,
    bind,
    comparison,
    constant,
    coverage_spec,
    Integer,
    modulo,
)

from .observation import observe_attributes

next_epoch = attribute("next_epoch", Integer(min=1))
vector_length = constant("vector_length", Integer(min=1))
destination_value = attribute("destination_value", Integer(min=0))

RESET = aspect(
    "reset",
    modulo("destination_position", next_epoch, vector_length),
    comparison("destination_nonzero", destination_value, 0, granularity="cmp5"),
)
ASPECTS = (RESET,)
PROFILES = {
    "smoke": RESET.each(),
    "normal": RESET.exhaustive(),
    "max": RESET.exhaustive(),
    "standard": RESET.exhaustive(),
}

COVERAGE = coverage_spec(
    "slashings_reset",
    focus="process_slashings_reset: destination wraparound and value to clear",
    record="one vector",
    attributes=(
        next_epoch,
        destination_value,
    ),
    constants=(vector_length,),
    aspects=ASPECTS,
    profiles=PROFILES,
)

TARGET = bind(
    COVERAGE,
    observe_attributes=observe_attributes,
    constants={"vector_length": lambda spec: int(spec.EPOCHS_PER_SLASHINGS_VECTOR)},
)
