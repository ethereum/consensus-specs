"""Boundary claims agree with signed exits and the spec's assertion outcomes."""

from random import Random
from types import SimpleNamespace

import pytest

from eth_consensus_specs.test.helpers.specs import spec_targets
from tests.generators.compliance_runners.state_transition.evaluation.coverage_dsl import Context
from tests.generators.compliance_runners.state_transition.provider import load_provider
from tests.generators.compliance_runners.state_transition.validation_helpers import bls_enabled

from .materializer import VoluntaryExitMaterializer
from .target import EPOCHS, TARGET
from .test_utils import make_record
from .witness import BUCKET_DELTAS

validation = load_provider("voluntary_exit")


@pytest.mark.parametrize("preset", ["minimal", "mainnet"])
@pytest.mark.parametrize("message_bucket", list(BUCKET_DELTAS))
@pytest.mark.parametrize("seasoned_bucket", list(BUCKET_DELTAS))
def test_signed_exit_epoch_boundaries(preset, message_bucket, seasoned_bucket, monkeypatch):
    spec = spec_targets[preset]["gloas"]
    validation = load_provider("voluntary_exit", spec=spec)
    period = int(spec.config.SHARD_COMMITTEE_PERIOD)
    record = make_record(
        spec, current_ge_message_epoch=message_bucket, current_ge_seasoned=seasoned_bucket
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
    assert (post is not None) == actual["accepted"]
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
    assert target.assertion_result(observed).fault_count == meta["claimed"]["fault_count"]
    assert all(
        observed[name] == value
        for name, value in record.items()
        if not name.startswith("_") and value != "NA"
    )


@pytest.mark.parametrize("preset", ["minimal", "mainnet"])
def test_epoch_feasibility(preset):
    spec = spec_targets[preset]["gloas"]
    target = TARGET.for_spec(spec)
    assert EPOCHS["current_ge_message_epoch"].granularity == "cmp5"
    for bucket in ("LT_1", "EQ", "GT_1", "GT_FAR"):
        assert not target.feasible({"activation_le_current": False, "current_ge_seasoned": bucket})
