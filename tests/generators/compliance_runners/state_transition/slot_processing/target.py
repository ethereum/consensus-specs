"""Coverage of the Gloas ``process_slot`` inputs in one-slot sanity vectors.

``sanity/slots`` may advance several slots and run ``process_epoch``. This
target covers the first ``process_slot`` invocation when ``slots.yaml`` is 1;
multi-slot sequencing belongs to a separate ``process_slots`` target.
"""

from tests.generators.compliance_runners.state_transition.evaluation.declarations import (
    aspect,
    attribute,
    bind,
    Boolean,
    categorical,
    choose,
    constant,
    coverage_spec,
    factor,
    Integer,
)

from .observation import observe_attributes

slot = attribute("slot", Integer(min=0))
slots_to_process = attribute("slots_to_process", Integer(min=1))
header_root_zero = attribute("header_root_zero", Boolean())
state_root_slot_nonzero = attribute("state_root_slot_nonzero", Boolean())
block_root_slot_nonzero = attribute("block_root_slot_nonzero", Boolean())
next_payload_available = attribute("next_payload_available", Boolean())
slots_per_historical_root = constant("slots_per_historical_root", Integer(min=2))

POSITION = aspect(
    "position",
    categorical(
        "ring_position",
        choose(
            slot % slots_per_historical_root == 0,
            "FIRST",
            choose(
                slot % slots_per_historical_root == slots_per_historical_root - 1,
                "LAST",
                "MIDDLE",
            ),
        ),
        ("FIRST", "MIDDLE", "LAST"),
        description="The write index and the next-slot availability index share a circular buffer.",
    ),
)
CACHES = aspect(
    "caches",
    factor(
        "header_state_root_empty",
        header_root_zero,
        description="Only an empty latest block-header state root is filled in.",
    ),
    factor("state_root_destination_populated", state_root_slot_nonzero),
    factor("block_root_destination_populated", block_root_slot_nonzero),
    factor(
        "next_payload_available_before_clear",
        next_payload_available,
        description="Clearing a true availability bit changes the state.",
    ),
)
ASPECTS = (POSITION, CACHES)
ALL_FACTORS = (*POSITION.declarations, *CACHES.declarations)
PROFILES = {
    "smoke": POSITION.each() | CACHES.each(),
    "normal": POSITION.each() | CACHES.nwise(2) | (POSITION.each() * CACHES.each()),
    "standard": (POSITION.each() * CACHES.exhaustive()),
}

COVERAGE = coverage_spec(
    "process_slot",
    focus="Gloas process_slot: circular write positions, header-root guard, cache occupancy, and payload availability clear",
    record="one sanity/slots vector with slots.yaml equal to 1",
    attributes=(
        slot,
        slots_to_process,
        header_root_zero,
        state_root_slot_nonzero,
        block_root_slot_nonzero,
        next_payload_available,
    ),
    constants=(slots_per_historical_root,),
    aspects=ASPECTS,
    profiles=PROFILES,
    applicable_when=slots_to_process == 1,
)
TARGET = bind(
    COVERAGE,
    observe_attributes=observe_attributes,
    constants={"slots_per_historical_root": lambda spec: int(spec.SLOTS_PER_HISTORICAL_ROOT)},
)
