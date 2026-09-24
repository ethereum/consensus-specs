"""Coverage of the ordered activation-queue, ejection, and activation branches."""

from tests.generators.compliance_runners.state_transition.evaluation.declarations import (
    aspect,
    attribute,
    bind,
    coverage_spec,
    factor,
    Integer,
)

from .observation import observe_attributes

validator_count = attribute("validator_count", Integer(min=0))
queued_count = attribute("queued_count", Integer(min=0))
ejected_count = attribute("ejected_count", Integer(min=0))
activated_count = attribute("activated_count", Integer(min=0))
unchanged_count = attribute("unchanged_count", Integer(min=0))

SHAPE = aspect("shape", factor("has_validators", validator_count > 0))
BRANCHES = aspect(
    "branches",
    factor("queues_validator", queued_count > 0),
    factor("ejects_validator", ejected_count > 0),
    factor("activates_validator", activated_count > 0),
    factor("leaves_validator_unchanged", unchanged_count > 0),
)
ASPECTS = (SHAPE, BRANCHES)
PROFILES = {
    "smoke": SHAPE.each() | BRANCHES.each(),
    "normal": SHAPE.each() | BRANCHES.nwise(2),
    "standard": SHAPE.each() | BRANCHES.nwise(2),
}

COVERAGE = coverage_spec(
    "registry_updates",
    focus="process_registry_updates: ordered per-validator queue, ejection, activation, and no-op branches",
    record="one vector; branch factors mean at least one validator takes that branch",
    attributes=(validator_count, queued_count, ejected_count, activated_count, unchanged_count),
    aspects=ASPECTS,
    profiles=PROFILES,
    feasible=lambda a, _g: (
        a.get("has_validators") is None
        or a.get("has_validators")
        is any(
            a.get(name) is True
            for name in (
                "queues_validator",
                "ejects_validator",
                "activates_validator",
                "leaves_validator_unchanged",
            )
        )
    ),
)
TARGET = bind(COVERAGE, observe_attributes=observe_attributes)
