"""Coverage of the early return, justification thresholds, and finalization paths."""

from tests.generators.compliance_runners.state_transition.evaluation.declarations import (
    all_of,
    any_of,
    aspect,
    attribute,
    bind,
    Boolean,
    constant,
    coverage_spec,
    dimension,
    factor,
    implies,
    Integer,
)

from .observation import observe_attributes

current_epoch = attribute("current_epoch", Integer(min=0))
previous_support = attribute("previous_support", Boolean())
current_support = attribute("current_support", Boolean())
finalization_rule = attribute("finalization_rule", Integer(min=0, max=4))
genesis_epoch = constant("genesis_epoch", Integer(min=0))

REACHED = factor("past_initial_epochs", current_epoch > genesis_epoch + 1)
GUARD = aspect("guard", REACHED)
JUSTIFICATION = aspect(
    "justification",
    factor("previous_epoch_supermajority", previous_support, when=REACHED),
    factor("current_epoch_supermajority", current_support, when=REACHED),
)
FINALIZATION = aspect(
    "finalization",
    dimension(
        "finalization_path",
        finalization_rule,
        when=REACHED,
        description=(
            "Last successful finalization rule: none, previous checkpoint at age 3 or 2, "
            "or current checkpoint at age 2 or 1."
        ),
    ),
)
ASPECTS = (GUARD, JUSTIFICATION, FINALIZATION)
PROFILES = {
    "smoke": GUARD.each() | JUSTIFICATION.each() | FINALIZATION.each(),
    "max": GUARD.exhaustive()
    | JUSTIFICATION.exhaustive()
    | FINALIZATION.exhaustive()
    | (JUSTIFICATION.each() * FINALIZATION.each()),
    "normal": JUSTIFICATION.exhaustive() | (JUSTIFICATION.each() * FINALIZATION.each()),
    "standard": GUARD.each()
    | JUSTIFICATION.exhaustive()
    | (JUSTIFICATION.each() * FINALIZATION.each()),
}

COVERAGE = coverage_spec(
    "justification_and_finalization",
    focus="process_justification_and_finalization: epoch guard, two 2/3 thresholds, four finalization rules",
    record="one vector",
    attributes=(current_epoch, previous_support, current_support, finalization_rule),
    constants=(genesis_epoch,),
    aspects=ASPECTS,
    profiles=PROFILES,
    constraints=(
        implies(
            any_of(
                FINALIZATION.ref("finalization_path") == 1,
                FINALIZATION.ref("finalization_path") == 2,
            ),
            JUSTIFICATION.ref("previous_epoch_supermajority"),
        ),
        implies(
            any_of(
                FINALIZATION.ref("finalization_path") == 3,
                FINALIZATION.ref("finalization_path") == 4,
            ),
            all_of(*JUSTIFICATION.declarations),
        ),
    ),
)
TARGET = bind(
    COVERAGE,
    observe_attributes=observe_attributes,
    constants={"genesis_epoch": lambda spec: int(spec.GENESIS_EPOCH)},
)
