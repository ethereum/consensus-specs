"""Payload-attestation declarations preserving the original coverage policy."""

from tests.generators.compliance_runners.state_transition.evaluation.declarations import (
    aspect,
    assertion,
    assertion_set,
    attribute,
    bind,
    Boolean,
    choose,
    coverage_spec,
    dimension,
    each,
    exhaustive,
    Finite,
    nwise,
    union,
)

from .observation import observe_attributes

# Keep up to two assertion faults exhaustive, then cover exceptional
# interactions pairwise for the max profile.
MAX_EXHAUSTIVE_FAULTS = 2
MAX_EXCEPTIONAL_INTERACTION_STRENGTH = 2

OUTCOMES = (
    "REJECT_PARENT_ROOT",
    "REJECT_SLOT",
    "REJECT_EMPTY",
    "REJECT_SIGNATURE",
    "ACCEPT",
)
parent_root_equal = attribute("parent_root_equal", Boolean())
previous_slot = attribute("previous_slot", Boolean())
indices_shape = attribute("indices_shape", Finite(("EMPTY", "PARTIAL", "ALL")))
indices_nonempty = attribute("indices_nonempty", Boolean())
signature_ok = attribute("signature_ok", Boolean())
inferred_outcome = attribute("inferred_outcome", Finite(OUTCOMES))
post_present = attribute("post_present", Boolean())

BLOCK_CONTEXT = aspect(
    "block_context",
    assertion("parent_root_matches", parent_root_equal),
    assertion("slot_is_previous", previous_slot),
)
NONEMPTY = assertion("attesting_indices_nonempty", indices_nonempty)
SIGNATURE = assertion("signature_valid", signature_ok, when=NONEMPTY)
PARTICIPANTS = aspect(
    "participants",
    dimension("attesting_indices_profile", indices_shape),
    NONEMPTY,
    SIGNATURE,
)
OUTCOME = dimension("outcome", inferred_outcome)
ACCEPTED = dimension("accepted", post_present)
RESULT = aspect("outcome", OUTCOME, ACCEPTED)
ASPECTS = (BLOCK_CONTEXT, PARTICIPANTS, RESULT)
ASSERTIONS = assertion_set(BLOCK_CONTEXT, PARTICIPANTS, observed=ACCEPTED, complete=True)

EXPECTED_OUTCOME = choose(
    (~BLOCK_CONTEXT.ref("parent_root_matches"), "REJECT_PARENT_ROOT"),
    (~BLOCK_CONTEXT.ref("slot_is_previous"), "REJECT_SLOT"),
    (~NONEMPTY, "REJECT_EMPTY"),
    (~SIGNATURE, "REJECT_SIGNATURE"),
    "ACCEPT",
)
FACTORS = (*BLOCK_CONTEXT.declarations, *PARTICIPANTS.declarations, OUTCOME)
NORMAL = ASSERTIONS.normal(BLOCK_CONTEXT.exhaustive() * PARTICIPANTS.exhaustive())
EXCEPTIONAL = ASSERTIONS.exceptional(each((OUTCOME,)), faults=1)
PROFILES = {
    "smoke": each((OUTCOME,)),
    "normal": NORMAL,
    "exceptional": EXCEPTIONAL,
    "standard": NORMAL | EXCEPTIONAL,
    "max": union(
        ASSERTIONS.normal(exhaustive(FACTORS)),
        ASSERTIONS.exceptional(exhaustive(FACTORS), faults=(1, MAX_EXHAUSTIVE_FAULTS)),
        ASSERTIONS.exceptional(nwise(FACTORS, MAX_EXCEPTIONAL_INTERACTION_STRENGTH)),
    ),
}
COVERAGE = coverage_spec(
    "payload_attestation",
    focus="parent-root, previous-slot, nonempty-indices, and signature assertions",
    record="one payload-attestation vector",
    aspects=ASPECTS,
    profiles=PROFILES,
    constraints=(
        (PARTICIPANTS.ref("attesting_indices_profile") != "EMPTY") == NONEMPTY,
        OUTCOME == EXPECTED_OUTCOME,
    ),
    assertions=ASSERTIONS,
)
TARGET = bind(COVERAGE, observe_attributes=observe_attributes)
