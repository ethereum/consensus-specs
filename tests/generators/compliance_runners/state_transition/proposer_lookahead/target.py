"""Coverage of lookahead inputs and the active, unslashed candidate pool."""

from tests.generators.compliance_runners.state_transition.evaluation.declarations import (
    aspect,
    attribute,
    bind,
    Boolean,
    constant,
    coverage_spec,
    factor,
    Integer,
)

from .observation import observe_attributes

candidate_count = attribute("candidate_count", Integer(min=1))
slashed_active_count = attribute("slashed_active_count", Integer(min=0))
old_lookahead_has_slashed = attribute("old_lookahead_has_slashed", Boolean())
new_proposers_have_duplicate = attribute("new_proposers_have_duplicate", Boolean())
old_tail_equals_new = attribute("old_tail_equals_new", Boolean())
slots_per_epoch = constant("slots_per_epoch", Integer(min=1))

CANDIDATES = aspect(
    "candidates",
    factor("has_slashed_active_validator", slashed_active_count > 0),
    factor("fewer_candidates_than_slots", candidate_count < slots_per_epoch),
    factor("old_lookahead_contains_slashed", old_lookahead_has_slashed),
)
ROTATION = aspect(
    "rotation",
    factor("new_proposers_repeat", new_proposers_have_duplicate),
    factor("new_epoch_repeats_old_tail", old_tail_equals_new),
)
ASPECTS = (CANDIDATES, ROTATION)
PROFILES = {
    "smoke": CANDIDATES.each() | ROTATION.each(),
    "max": CANDIDATES.exhaustive() | ROTATION.exhaustive() | (CANDIDATES.each() * ROTATION.each()),
    "normal": CANDIDATES.nwise(2) | ROTATION.each(),
    "standard": CANDIDATES.nwise(2) | (CANDIDATES.each() * ROTATION.each()),
}
COVERAGE = coverage_spec(
    "proposer_lookahead",
    focus="process_proposer_lookahead: slashed exclusion, proposer repetition, and old/new epoch relationship",
    record="one vector",
    attributes=(
        candidate_count,
        slashed_active_count,
        old_lookahead_has_slashed,
        new_proposers_have_duplicate,
        old_tail_equals_new,
    ),
    constants=(slots_per_epoch,),
    aspects=ASPECTS,
    profiles=PROFILES,
    feasible=lambda a, _g: (
        a.get("fewer_candidates_than_slots") is not True or a.get("new_proposers_repeat") is True
    ),
)
TARGET = bind(
    COVERAGE,
    observe_attributes=observe_attributes,
    constants={"slots_per_epoch": lambda spec: int(spec.SLOTS_PER_EPOCH)},
)
