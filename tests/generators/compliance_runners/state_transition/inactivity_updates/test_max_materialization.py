"""Regression checks for the larger inactivity-update profile."""

from types import SimpleNamespace

from eth_consensus_specs.gloas import minimal as spec
from tests.generators.compliance_runners.state_transition.evaluation.coverage_dsl import Context
from tests.generators.compliance_runners.state_transition.inactivity_updates_loop.materializer import (
    InactivityUpdatesLoopMaterializer,
)
from tests.generators.compliance_runners.state_transition.inactivity_updates_loop.target import (
    TARGET as LOOP_TARGET,
)

from .materializer import InactivityUpdatesMaterializer
from .target import TARGET


def _observed(materializer, target, **solution):
    _, parts = materializer.materialize_solution(SimpleNamespace(**solution))
    pre = spec.BeaconState.decode_bytes(parts[0][2])
    post = spec.BeaconState.decode_bytes(parts[1][2])
    return target.record(target.observation(Context(spec, pre, None, post, {})), "predicate")


def test_partial_obligations_keep_requested_eligibility_and_score_effect():
    materializer = InactivityUpdatesMaterializer(spec)
    empty = _observed(
        materializer,
        TARGET,
        current_after_genesis=True,
        has_active_eligible=False,
        has_slashed_validators=False,
    )
    assert empty["has_active_eligible"] is False
    assert empty["has_slashed_validators"] is False

    changed = _observed(
        materializer,
        TARGET,
        current_after_genesis=True,
        eligible_validators="ONE",
        has_zero_score_eligible=True,
        scores_changed=True,
    )
    assert changed["scores_changed"] is True
    assert changed["has_zero_score_eligible"] is True


def test_stable_participant_keeps_target_flag():
    observed = _observed(
        InactivityUpdatesLoopMaterializer(spec),
        LOOP_TARGET,
        score_delta="UNCHANGED",
        has_target_flag=True,
        is_slashed=False,
    )
    assert observed["score_delta"] == "UNCHANGED"
    assert observed["has_target_flag"] is True


def test_max_omits_unrealizable_score_and_branch_combinations():
    obligations = [dict(item) for item in TARGET.for_spec(spec).profiles["max"].run("predicate")]
    assert all(
        not (
            item.get("scores_changed") is False
            and (item.get("has_zero_score_eligible") is False or item.get("leaking") is True)
        )
        for item in obligations
    )
    assert all(
        not (
            item.get("has_ineligible_validators") is False
            and item.get("has_slashed_validators") is True
            and item.get("branch_mix") == "ALL_DECREMENT"
        )
        for item in obligations
    )
