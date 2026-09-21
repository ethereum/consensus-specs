"""Coverage target for ``process_sync_committee_updates``.

The handler rotates the sync committees at the end of each sync-committee
period and computes the next committee from the state.
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


@coverage_aspect("committee")
def capture_committee(
    next_epoch: CAttribute[int],
    epochs_per_sync_committee_period: CAttribute[int],
    current_matches_next: CAttribute[bool],
    computed_next_matches_existing: CAttribute[bool],
):
    at_period_boundary: CPred = next_epoch % epochs_per_sync_committee_period == 0
    committees_already_match: CPred = current_matches_next
    computed_next_is_unchanged: CPred = computed_next_matches_existing


COMMITTEE = capture_committee
ASPECTS = (COMMITTEE,)


def _observe(ctx) -> None:
    spec, state = ctx.spec, ctx.pre
    current_epoch = int(spec.get_current_epoch(state))
    next_committee = spec.get_next_sync_committee(state)
    capture_committee(
        next_epoch=current_epoch + 1,
        epochs_per_sync_committee_period=int(spec.EPOCHS_PER_SYNC_COMMITTEE_PERIOD),
        current_matches_next=state.current_sync_committee == state.next_sync_committee,
        computed_next_matches_existing=next_committee == state.next_sync_committee,
    )


PROFILES = {
    "smoke": each(COMMITTEE.factors),
    "normal": COMMITTEE.exhaustive(),
    "standard": COMMITTEE.exhaustive(),
}


TARGET = Target("sync_committee_updates", ASPECTS, _observe, PROFILES)
