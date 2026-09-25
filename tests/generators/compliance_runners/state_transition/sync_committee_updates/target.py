"""Coverage target for ``process_sync_committee_updates``.

The handler rotates the sync committees at the end of each sync-committee
period and computes the next committee from the state.
"""

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

next_epoch = attribute("next_epoch", Integer(min=1))
current_matches_next = attribute("current_matches_next", Boolean())
computed_next_matches_existing = attribute("computed_next_matches_existing", Boolean())
epochs_per_sync_committee_period = constant("epochs_per_sync_committee_period", Integer(min=1))

COMMITTEE = aspect(
    "committee",
    factor("at_period_boundary", next_epoch % epochs_per_sync_committee_period == 0),
    factor("committees_already_match", current_matches_next),
    factor("computed_next_is_unchanged", computed_next_matches_existing),
)
ASPECTS = (COMMITTEE,)
PROFILES = {
    "smoke": COMMITTEE.each(),
    "normal": COMMITTEE.exhaustive(),
    "max": COMMITTEE.exhaustive(),
    "standard": COMMITTEE.exhaustive(),
}

COVERAGE = coverage_spec(
    "sync_committee_updates",
    focus="process_sync_committee_updates: period boundary and committee relationships",
    record="one vector",
    attributes=(
        next_epoch,
        current_matches_next,
        computed_next_matches_existing,
    ),
    constants=(epochs_per_sync_committee_period,),
    aspects=ASPECTS,
    profiles=PROFILES,
)

TARGET = bind(
    COVERAGE,
    observe_attributes=observe_attributes,
    constants={
        "epochs_per_sync_committee_period": lambda spec: int(spec.EPOCHS_PER_SYNC_COMMITTEE_PERIOD)
    },
)
