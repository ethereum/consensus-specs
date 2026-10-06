"""Boundary claims agree with signed exits and the spec's assertion outcomes."""

from random import Random
from types import SimpleNamespace

import pytest

from eth_consensus_specs.test.helpers.specs import spec_targets
from tests.generators.compliance_runners.state_transition.evaluation.coverage_dsl import Context
from tests.generators.compliance_runners.state_transition.validation_helpers import bls_enabled

from . import validation
from .cases import BUCKET_DELTAS, scenario_record
from .coverage import build_profile
from .materializer import VoluntaryExitMaterializer
from .target import EPOCHS, TARGET


@pytest.mark.parametrize("preset", ["minimal", "mainnet"])
@pytest.mark.parametrize("message_bucket", list(BUCKET_DELTAS))
@pytest.mark.parametrize("seasoned_bucket", list(BUCKET_DELTAS))
def test_signed_exit_epoch_boundaries(preset, message_bucket, seasoned_bucket, monkeypatch):
    spec = spec_targets[preset]["gloas"]
    monkeypatch.setattr(validation, "spec", spec)
    period = int(spec.config.SHARD_COMMITTEE_PERIOD)
    scenario = (
        "TOO_YOUNG"
        if BUCKET_DELTAS[seasoned_bucket] < 0
        else "FUTURE_EXIT_EPOCH"
        if BUCKET_DELTAS[message_bucket] < 0
        else "VALID"
    )
    record = scenario_record(period, scenario, message_bucket, seasoned_bucket)
    materializer = VoluntaryExitMaterializer(spec)
    materializer.rng = Random(124)
    with bls_enabled():
        meta, parts = materializer.materialize_solution(SimpleNamespace(**record))
    encoded = {name: data for name, _, data in parts}
    pre = spec.BeaconState.decode_bytes(encoded["pre"])
    signed_exit = spec.SignedVoluntaryExit.decode_bytes(encoded["voluntary_exit"])
    post = spec.BeaconState.decode_bytes(encoded["post"]) if "post" in encoded else None
    actual = validation.recover_dimensions(pre, signed_exit)
    assert meta["claimed"] == actual
    assert (post is not None) == (actual["outcome"] == "ACCEPT")
    epoch = int(spec.get_current_epoch(pre))
    validator = pre.validators[signed_exit.message.validator_index]
    assert epoch - int(signed_exit.message.epoch) == BUCKET_DELTAS[message_bucket]
    assert epoch - int(validator.activation_epoch) - period == BUCKET_DELTAS[seasoned_bucket]
    target = TARGET.for_spec(spec)
    observed = target.record(target.observation(Context(spec, pre, signed_exit, post, {})))
    assert observed["current_ge_message_epoch"] == message_bucket
    assert observed["current_ge_seasoned"] == seasoned_bucket
    assert observed["accepted"] == (post is not None)
    assert target.feasible(observed)


@pytest.mark.parametrize("preset", ["minimal", "mainnet"])
def test_profiles_preserve_outcomes_and_cover_epoch_buckets(preset):
    spec = spec_targets[preset]["gloas"]
    expected = set(BUCKET_DELTAS)
    outcomes = {
        "ACCEPT",
        "REJECT_INACTIVE",
        "REJECT_ALREADY_EXITED",
        "REJECT_EXIT_EPOCH",
        "REJECT_TOO_YOUNG",
        "REJECT_PENDING_WITHDRAWAL",
        "REJECT_SIGNATURE",
    }
    assert EPOCHS["current_ge_message_epoch"].granularity == "cmp5"
    assert EPOCHS["current_ge_seasoned"].granularity == "cmp5"
    for profile in ("smoke", "standard", "max"):
        _, records = build_profile(profile, spec=spec)
        assert {r["current_ge_message_epoch"] for r in records} == expected
        assert {r["current_ge_seasoned"] for r in records} == expected
        assert {r["outcome"] for r in records} == outcomes
    _, records = build_profile("normal", spec=spec)
    assert all(record["outcome"] == "ACCEPT" for record in records)
    assert {(r["current_ge_message_epoch"], r["current_ge_seasoned"]) for r in records} == {
        (message, seasoned)
        for message in ("EQ", "GT_1", "GT_FAR")
        for seasoned in ("EQ", "GT_1", "GT_FAR")
    }
    _, records = build_profile("exceptional", spec=spec)
    assert all(record["outcome"] != "ACCEPT" for record in records)
