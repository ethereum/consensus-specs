from types import SimpleNamespace

import pytest

from tests.generators.compliance_runners.state_transition.evaluation.coverage_dsl import (
    Context,
    GRANULARITIES,
    score,
)

from .observation import observe_attributes
from .target import COVERAGE, TARGET


def context(current_epoch, vote_count, *, post_present=True):
    spec = SimpleNamespace(
        EPOCHS_PER_ETH1_VOTING_PERIOD=4,
        get_current_epoch=lambda state: state.slot // 8,
    )
    pre = SimpleNamespace(slot=current_epoch * 8, eth1_data_votes=[object()] * vote_count)
    return Context(spec, pre, None, object() if post_present else None, {})


def test_adapter_extracts_attributes_without_recording():
    assert observe_attributes(context(3, 2)) == {
        "next_epoch": 4,
        "vote_count": 2,
    }


def test_constants_are_distinct_and_follow_the_selected_spec():
    assert tuple(c.name for c in COVERAGE.constants) == ("epochs_per_eth1_voting_period",)
    assert tuple(a.name for a in COVERAGE.attributes) == ("next_epoch", "vote_count")
    ctx = context(3, 1)
    assert TARGET.observation(ctx)["at_reset_boundary"] is True
    ctx.spec.EPOCHS_PER_ETH1_VOTING_PERIOD = 8
    observation = TARGET.observation(ctx)
    assert observation["at_reset_boundary"] is False
    assert "epochs_per_eth1_voting_period" not in observation


def test_bound_constants_are_validated_and_profiles_require_binding():
    with pytest.raises(ValueError, match="for_spec"):
        TARGET.profiles["normal"].run("predicate")
    with pytest.raises(ValueError, match="outside"):
        TARGET.for_spec(SimpleNamespace(EPOCHS_PER_ETH1_VOTING_PERIOD=0))
    target = TARGET.for_spec(context(3, 1).spec)
    assert target.bound_constants == {"epochs_per_eth1_voting_period": 4}


@pytest.mark.parametrize("granularity", GRANULARITIES)
@pytest.mark.parametrize(("epoch", "boundary"), [(2, False), (3, True), (4, False)])
@pytest.mark.parametrize("vote_count", [0, 1, 2])
def test_target_binds_attributes_and_preserves_factor_semantics(
    granularity, epoch, boundary, vote_count
):
    ctx = context(epoch, vote_count)
    observation = TARGET.observation(ctx)
    assert all(observation[name] == value for name, value in observe_attributes(ctx).items())
    assert TARGET.record(observation, granularity) == {
        "at_reset_boundary": boundary,
        "votes_nonempty": vote_count > 0,
    }


def test_rejected_vector_still_has_input_coverage():
    observation = TARGET.observation(context(3, 1, post_present=False))
    assert TARGET.record(observation, "predicate") == {
        "at_reset_boundary": True,
        "votes_nonempty": True,
    }


@pytest.mark.parametrize("profile", ["smoke", "normal", "standard"])
def test_profiles_cover_all_boundary_and_occupancy_combinations(profile):
    records = [
        TARGET.record(TARGET.observation(context(epoch, count)), "predicate")
        for epoch in (2, 3)
        for count in (0, 1)
    ]
    target = TARGET.for_spec(context(3, 1).spec)
    report = score(target, records, target.profiles[profile], "predicate")
    assert report.total == report.covered == 4
    assert report.uncovered == report.unexpected == []
