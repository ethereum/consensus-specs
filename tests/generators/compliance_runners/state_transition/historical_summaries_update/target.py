"""Coverage target for ``process_historical_summaries_update``.

The handler appends a summary at the end of each historical-root period.  The
target records the period boundary and whether the summary list already has
entries before the update.
"""

# ruff: noqa: F841 - factor declarations are assignments the body never reads
from __future__ import annotations

from tests.generators.compliance_runners.state_transition.evaluation.coverage_dsl import (
    CAttribute,
    coverage_aspect,
    CPred,
    each,
    Target,
)


@coverage_aspect("update")
def capture_update(
    next_epoch: CAttribute[int],
    epochs_per_historical_root: CAttribute[int],
    summary_count: CAttribute[int],
):
    at_update_boundary: CPred = next_epoch % epochs_per_historical_root == 0
    summaries_nonempty: CPred = summary_count > 0


UPDATE = capture_update
ASPECTS = (UPDATE,)


def _observe(ctx) -> None:
    spec, state = ctx.spec, ctx.pre
    capture_update(
        next_epoch=int(spec.get_current_epoch(state)) + 1,
        epochs_per_historical_root=(
            int(spec.SLOTS_PER_HISTORICAL_ROOT) // int(spec.SLOTS_PER_EPOCH)
        ),
        summary_count=len(state.historical_summaries),
    )


PROFILES = {
    "smoke": each(UPDATE.factors),
    "normal": UPDATE.exhaustive(),
    "standard": UPDATE.exhaustive(),
}


TARGET = Target("historical_summaries_update", ASPECTS, _observe, PROFILES)
