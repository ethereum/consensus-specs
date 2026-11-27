from types import SimpleNamespace

import pytest

from eth_consensus_specs.gloas import minimal as spec
from tests.generators.compliance_runners.runner.discovery import gather_tests
from tests.generators.compliance_runners.runner.state_transition import get_test_case
from tests.generators.compliance_runners.state_transition.evaluation.coverage_dsl import (
    Context,
    score,
)
from tests.generators.compliance_runners.state_transition.evaluation.invariant_scan import (
    entry_condition_violations,
    state_invariant_violations,
)
from tests.generators.compliance_runners.state_transition.provider import materialize_handler

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
    assert TARGET.observation(ctx)["reset_remainder"] == "ZERO"
    ctx.spec.EPOCHS_PER_ETH1_VOTING_PERIOD = 8
    observation = TARGET.observation(ctx)
    assert observation["reset_remainder"] == "INTERIOR"
    assert "epochs_per_eth1_voting_period" not in observation


def test_bound_constants_are_validated_and_profiles_require_binding():
    with pytest.raises(ValueError, match="for_spec"):
        TARGET.profiles["normal"].run()
    with pytest.raises(ValueError, match="outside"):
        TARGET.for_spec(SimpleNamespace(EPOCHS_PER_ETH1_VOTING_PERIOD=0))
    target = TARGET.for_spec(context(3, 1).spec)
    assert target.bound_constants == {"epochs_per_eth1_voting_period": 4}


@pytest.mark.parametrize(
    ("epoch", "remainder"), [(1, "INTERIOR"), (2, "LAST"), (3, "ZERO"), (4, "ONE")]
)
@pytest.mark.parametrize("vote_count", [0, 1, 2])
def test_target_binds_attributes_and_preserves_factor_semantics(epoch, remainder, vote_count):
    ctx = context(epoch, vote_count)
    observation = TARGET.observation(ctx)
    assert all(observation[name] == value for name, value in observe_attributes(ctx).items())
    assert TARGET.record(observation) == {
        "reset_remainder": remainder,
        "votes_nonempty": ("EQ", "GT_1", "GT_FAR")[vote_count],
    }


def test_rejected_vector_still_has_input_coverage():
    observation = TARGET.observation(context(3, 1, post_present=False))
    assert TARGET.record(observation) == {
        "reset_remainder": "ZERO",
        "votes_nonempty": "GT_1",
    }


@pytest.mark.parametrize("profile", ["smoke", "normal", "standard"])
def test_profiles_cover_all_boundary_and_occupancy_combinations(profile):
    records = [
        TARGET.record(TARGET.observation(context(epoch, count)))
        for epoch in (1, 2, 3, 4)
        for count in (0, 1, 2)
    ]
    target = TARGET.for_spec(context(3, 1).spec)
    report = score(target, records, target.profiles[profile])
    assert report.total == report.covered == (7 if profile == "smoke" else 12)
    assert report.uncovered == report.unexpected == []


def test_max_vectors_reach_epoch_entry_with_included_votes(tmp_path):
    assert materialize_handler("eth1_data_reset", "max", tmp_path, spec=spec, seed=124) == 12
    for case in gather_tests([tmp_path], kind="state_transition"):
        vector = get_test_case(spec, case.test_dir, case.handler)
        pre, post = vector["pre"], vector["post"]
        assert not list(entry_condition_violations(spec, pre, case.runner))
        assert not list(state_invariant_violations(spec, pre))
        current_epoch = spec.get_current_epoch(pre)
        if current_epoch == spec.GENESIS_EPOCH:
            assert all(
                spec.has_compounding_withdrawal_credential(validator)
                and validator.effective_balance == spec.MAX_EFFECTIVE_BALANCE_ELECTRA
                for validator in pre.validators
            )

        votes = pre.eth1_data_votes
        if votes:
            assert pre.latest_block_header.slot == pre.slot
            voted_slots = range(int(pre.slot) - len(votes) + 1, int(pre.slot) + 1)
            roots = {pre.block_roots[slot % spec.SLOTS_PER_HISTORICAL_ROOT] for slot in voted_slots}
            assert len(roots) == len(votes)
            assert len({vote.block_hash for vote in votes}) == min(len(votes), 2)
            assert all(vote.deposit_count == pre.eth1_data.deposit_count for vote in votes)

        expected = pre.copy()
        next_epoch = current_epoch + 1
        if next_epoch % spec.EPOCHS_PER_ETH1_VOTING_PERIOD == 0:
            expected.eth1_data_votes = spec.Eth1DataVotes()
        assert post == expected
