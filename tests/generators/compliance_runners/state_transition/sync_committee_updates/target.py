"""Coverage target for ``process_sync_committee_updates``.

The handler rotates the sync committees at the end of each sync-committee
period and computes the next committee from the state.
"""

# ruff: noqa: F841 - factor declarations are assignments the body never reads
from __future__ import annotations

from tests.generators.compliance_runners.state_transition.evaluation.coverage_dsl import (
    CAttribute,
    CConstant,
    Context,
    coverage_aspect,
    CPred,
    each,
    Target,
)

from .observation import observe_attributes


@coverage_aspect("committee")
def capture_committee(
    next_epoch: CAttribute[int],
    current_matches_next: CAttribute[bool],
    computed_next_matches_existing: CAttribute[bool],
    *,
    epochs_per_sync_committee_period: CConstant[int],
):
    at_period_boundary: CPred = next_epoch % epochs_per_sync_committee_period == 0
    committees_already_match: CPred = current_matches_next
    computed_next_is_unchanged: CPred = computed_next_matches_existing


COMMITTEE = capture_committee
ASPECTS = (COMMITTEE,)


def _observe(ctx: Context) -> None:
    capture_committee(**observe_attributes(ctx))


PROFILES = {
    "smoke": each(COMMITTEE.factors),
    "normal": COMMITTEE.exhaustive(),
    "standard": COMMITTEE.exhaustive(),
}


TARGET = Target(
    "sync_committee_updates",
    ASPECTS,
    _observe,
    PROFILES,
    constants={
        "epochs_per_sync_committee_period": lambda spec: int(spec.EPOCHS_PER_SYNC_COMMITTEE_PERIOD)
    },
)
