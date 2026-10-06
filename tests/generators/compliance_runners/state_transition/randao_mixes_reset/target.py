"""Coverage target for ``process_randao_mixes_reset``.

The handler copies the current epoch's RANDAO mix into the next epoch's
circular slot.  The target records the destination wraparound and the source
and destination mix relationship.
"""

from tests.generators.compliance_runners.state_transition.evaluation.declarations import (
    aspect,
    attribute,
    bind,
    Bytes,
    constant,
    coverage_spec,
    factor,
    Integer,
    modulo,
)

from .observation import observe_attributes

next_epoch = attribute("next_epoch", Integer(min=1))
vector_length = constant("vector_length", Integer(min=1))
source_mix = attribute("source_mix", Bytes(length=32))
destination_mix = attribute("destination_mix", Bytes(length=32))
zero_mix = constant("zero_mix", Bytes(length=32))

RESET = aspect(
    "reset",
    modulo("destination_position", next_epoch, vector_length),
    factor("source_nonzero", source_mix != zero_mix),
    factor("source_matches_destination", source_mix == destination_mix),
)
ASPECTS = (RESET,)
PROFILES = {
    "smoke": RESET.each(),
    "normal": RESET.exhaustive(),
    "max": RESET.exhaustive(),
    "standard": RESET.exhaustive(),
}

COVERAGE = coverage_spec(
    "randao_mixes_reset",
    focus="process_randao_mixes_reset: destination wraparound and source/destination mix relationship",
    record="one vector",
    attributes=(
        next_epoch,
        source_mix,
        destination_mix,
    ),
    constants=(zero_mix, vector_length),
    aspects=ASPECTS,
    profiles=PROFILES,
)

TARGET = bind(
    COVERAGE,
    observe_attributes=observe_attributes,
    constants={
        "zero_mix": lambda spec: bytes(spec.Root()) if hasattr(spec, "Root") else bytes(32),
        "vector_length": lambda spec: int(spec.EPOCHS_PER_HISTORICAL_VECTOR),
    },
)
