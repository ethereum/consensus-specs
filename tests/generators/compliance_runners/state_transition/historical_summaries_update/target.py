"""Coverage target for ``process_historical_summaries_update``.

The handler appends a summary at the end of each historical-root period.  The
target records the period boundary and whether the summary list already has
entries before the update.
"""

from tests.generators.compliance_runners.state_transition.evaluation.declarations import (
    aspect,
    attribute,
    bind,
    constant,
    coverage_spec,
    factor,
    Integer,
)

from .observation import observe_attributes

next_epoch = attribute("next_epoch", Integer(min=1))
summary_count = attribute("summary_count", Integer(min=0))
epochs_per_historical_root = constant("epochs_per_historical_root", Integer(min=1))

UPDATE = aspect(
    "update",
    factor("at_update_boundary", next_epoch % epochs_per_historical_root == 0),
    factor("summaries_nonempty", summary_count > 0),
)
ASPECTS = (UPDATE,)
PROFILES = {
    "smoke": UPDATE.each(),
    "normal": UPDATE.exhaustive(),
    "max": UPDATE.exhaustive(),
    "standard": UPDATE.exhaustive(),
}

COVERAGE = coverage_spec(
    "historical_summaries_update",
    focus="process_historical_summaries_update: historical-root period boundary and summary-list occupancy",
    record="one vector",
    attributes=(
        next_epoch,
        summary_count,
    ),
    constants=(epochs_per_historical_root,),
    aspects=ASPECTS,
    profiles=PROFILES,
)

TARGET = bind(
    COVERAGE,
    observe_attributes=observe_attributes,
    constants={
        "epochs_per_historical_root": lambda spec: (
            int(spec.SLOTS_PER_HISTORICAL_ROOT) // int(spec.SLOTS_PER_EPOCH)
        )
    },
)
