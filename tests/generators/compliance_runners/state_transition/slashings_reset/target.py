"""Coverage target for ``process_slashings_reset``.

The handler selects the next epoch's circular slashings slot and resets it to
zero.  The target records the wraparound case and whether the selected slot
actually contains a value to clear.
"""

from tests.generators.compliance_runners.state_transition.evaluation.declarations import (
    aspect,
    attribute,
    bind,
    coverage_spec,
    factor,
    Integer,
)

from .observation import observe_attributes

destination_index = attribute("destination_index", Integer(min=0))
destination_value = attribute("destination_value", Integer(min=0))

RESET = aspect(
    "reset",
    factor("destination_is_first_slot", destination_index == 0),
    factor("destination_nonzero", destination_value > 0),
)
ASPECTS = (RESET,)
PROFILES = {"smoke": RESET.each(), "normal": RESET.exhaustive(), "standard": RESET.exhaustive()}

COVERAGE = coverage_spec(
    "slashings_reset",
    focus="process_slashings_reset: destination wraparound and value to clear",
    record="one vector",
    attributes=(
        destination_index,
        destination_value,
    ),
    constants=(),
    aspects=ASPECTS,
    profiles=PROFILES,
)

TARGET = bind(COVERAGE, observe_attributes=observe_attributes, constants={})
