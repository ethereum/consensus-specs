"""Aligned exit balances and partial-withdrawal residuals realize churn boundaries."""

from random import Random
from types import SimpleNamespace

import pytest

from eth_consensus_specs.test.helpers.specs import spec_targets
from tests.generators.compliance_runners.state_transition.evaluation.coverage_dsl import Context, NA
from tests.generators.compliance_runners.state_transition.provider import load_provider
from tests.generators.compliance_runners.state_transition.validation_helpers import bls_enabled

from .materializer import VoluntaryExitMaterializer
from .target import CHURN, TARGET
from .test_utils import CHURN_CASES, make_record
from .witness import churn_witnesses

validation = load_provider("voluntary_exit")


@pytest.mark.parametrize("preset", ["minimal", "mainnet"])
@pytest.mark.parametrize("active", [False, True])
@pytest.mark.parametrize(("kind", "bucket", "additional_kind"), CHURN_CASES)
def test_churn_claims_and_state_updates(preset, active, kind, bucket, additional_kind, monkeypatch):
    spec = spec_targets[preset]["gloas"]
    validation = load_provider("voluntary_exit", spec=spec)
    witness = next(
        w
        for w in churn_witnesses(spec, active=active)
        if (w["earliest_lt_new"], w["balance_gt_consumable"], w["additional_epochs"])
        == (kind == "NEW_EPOCH", bucket, "NA" if additional_kind == "ZERO" else additional_kind)
    )
    record = make_record(
        spec,
        activation_le_current=active,
        current_ge_seasoned="GT_1" if active else "LT_FAR",
        foreign_pending_entries="SOME" if kind != "NEW_EPOCH" else "ZERO",
        **{
            n: witness[n] for n in ("earliest_lt_new", "balance_gt_consumable", "additional_epochs")
        },
    )
    materializer = VoluntaryExitMaterializer(spec)
    materializer.rng = Random(124)
    with bls_enabled():
        meta, parts = materializer.materialize_solution(SimpleNamespace(**record))
    encoded = {name: data for name, _, data in parts}
    pre = spec.BeaconState.decode_bytes(encoded["pre"])
    signed_exit = spec.SignedVoluntaryExit.decode_bytes(encoded["voluntary_exit"])
    post = spec.BeaconState.decode_bytes(encoded["post"]) if "post" in encoded else None
    actual = validation.recover(pre, signed_exit, post)
    assert {n: meta["claimed"][n] for n in actual} == actual
    increment = int(spec.EFFECTIVE_BALANCE_INCREMENT)
    index = int(signed_exit.message.validator_index)
    assert int(pre.validators[index].effective_balance) % increment == 0
    churn = int(spec.get_exit_churn_limit(pre))
    budget = churn if kind == "NEW_EPOCH" else int(pre.exit_balance_to_consume)
    if kind == "NEW_EPOCH" and bucket == "LT_FAR":
        assert budget - int(pre.validators[index].effective_balance) == increment
    if bucket in ("LT_1", "GT_1"):
        assert budget % increment != 0
        assert abs(int(pre.validators[index].effective_balance) - budget) == 1
        # The unaligned residual comes from a real foreign partial withdrawal.
        assert sum(int(w.amount) for w in pre.pending_partial_withdrawals) == churn - budget
        assert all(int(w.validator_index) != index for w in pre.pending_partial_withdrawals)
    target = TARGET.for_spec(spec)
    observed = target.record(target.observation(Context(spec, pre, signed_exit, post, {})))
    assert observed["balance_gt_consumable"] == bucket
    assert observed["additional_epochs"] == (NA if additional_kind == "ZERO" else additional_kind)
    assert target.feasible(observed)
    assert (post is not None) == active
    if post is not None:
        balance = int(pre.validators[index].effective_balance)
        extra = max(0, (balance - budget + churn - 1) // churn)
        earliest = max(
            int(pre.earliest_exit_epoch),
            int(spec.compute_activation_exit_epoch(spec.get_current_epoch(pre))),
        )
        assert int(post.validators[index].exit_epoch) == earliest + extra
        assert int(post.earliest_exit_epoch) == earliest + extra
        assert int(post.exit_balance_to_consume) == budget + extra * churn - balance


@pytest.mark.parametrize("preset", ["minimal", "mainnet"])
def test_fresh_budget_pruning(preset):
    spec = spec_targets[preset]["gloas"]
    target = TARGET.for_spec(spec)
    assert CHURN["balance_gt_consumable"].granularity == "cmp5"
    for bucket in ("LT_1", "GT_1"):
        assert not target.feasible({"earliest_lt_new": True, "balance_gt_consumable": bucket})
        assert target.feasible({"earliest_lt_new": False, "balance_gt_consumable": bucket})
    assert not target.feasible({"balance_gt_consumable": "GT_1", "additional_epochs": "MANY"})


def test_one_gwei_increment_keeps_fresh_neighbour_buckets():
    target = TARGET.for_spec(
        SimpleNamespace(
            FAR_FUTURE_EPOCH=2**64 - 1,
            EFFECTIVE_BALANCE_INCREMENT=1,
            config=SimpleNamespace(SHARD_COMMITTEE_PERIOD=64),
        )
    )
    for bucket in ("LT_1", "GT_1"):
        assert target.feasible({"earliest_lt_new": True, "balance_gt_consumable": bucket})
    assert not target.feasible({"balance_gt_consumable": "GT_1", "additional_epochs": "MANY"})
