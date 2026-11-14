"""Coverage declaration for Gloas ``process_sync_aggregate``."""

from tests.generators.compliance_runners.state_transition.evaluation.declarations import (
    aspect,
    attribute,
    bind,
    Boolean,
    choose,
    coverage_spec,
    dimension,
    exhaustive,
    Finite,
    fix,
    implies,
    union,
)

from .observation import observe_attributes

participation_level_input = attribute(
    "observed_participation_level", Finite(("FULL", "MAJORITY", "EMPTY"))
)
signature_valid_input = attribute("observed_signature_valid", Boolean())

PARTICIPANTS = aspect("participants", dimension("participation_level", participation_level_input))
SIGNATURE = aspect("signature", dimension("signature_valid", signature_valid_input))
OUTCOME = aspect(
    "outcome",
    dimension("outcome", choose(signature_valid_input, "ACCEPT", "REJECT_SIGNATURE")),
)
FACTORS = tuple(
    factor for aspect_ in (PARTICIPANTS, SIGNATURE, OUTCOME) for factor in aspect_.declarations
)

COVERAGE = coverage_spec(
    "sync_aggregate",
    focus="process_sync_aggregate: participant count and aggregate signature validity",
    record="one operation",
    aspects=(PARTICIPANTS, SIGNATURE, OUTCOME),
    profiles={
        "smoke": OUTCOME.exhaustive(),
        "normal": fix(signature_valid=True) * PARTICIPANTS.exhaustive(),
        "exceptional": fix(signature_valid=False) * PARTICIPANTS.exhaustive(),
        "standard": union(
            fix(signature_valid=True) * PARTICIPANTS.exhaustive(),
            fix(signature_valid=False) * PARTICIPANTS.exhaustive(),
        ),
        "max": exhaustive(FACTORS),
    },
    constraints=(
        implies(
            SIGNATURE.ref("signature_valid"),
            OUTCOME.ref("outcome") == "ACCEPT",
        ),
        implies(
            ~SIGNATURE.ref("signature_valid"),
            OUTCOME.ref("outcome") == "REJECT_SIGNATURE",
        ),
    ),
)

TARGET = bind(COVERAGE, observe_attributes=observe_attributes, backend="python")
