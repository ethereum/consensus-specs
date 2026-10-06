"""Remainder coverage claims agree with concrete epoch transitions."""

from importlib import import_module
from random import Random
from types import SimpleNamespace

import pytest

from eth_consensus_specs.gloas import minimal as spec
from tests.generators.compliance_runners.state_transition.evaluation.coverage_dsl import Context


@pytest.mark.parametrize(
    ("module_name", "factor_name"),
    [
        ("historical_summaries_update", "update_remainder"),
        ("sync_committee_updates", "period_remainder"),
        ("slashings_reset", "destination_position"),
        ("randao_mixes_reset", "destination_position"),
    ],
)
@pytest.mark.parametrize("bucket", ["ZERO", "ONE", "LAST", "INTERIOR"])
def test_epoch_remainder_claims_match_materialized_states(module_name, factor_name, bucket):
    module = import_module(f".{module_name}.coverage", __package__)
    records, _ = module.build_profile("standard", spec=spec)
    record = next(record for record in records if record[factor_name] == bucket)
    materializer_module = import_module(f".{module_name}.materializer", __package__)
    materializer = materializer_module.MATERIALIZER(spec)
    materializer.rng = Random(0)
    meta, parts = materializer.materialize_solution(SimpleNamespace(**record))
    encoded = {name: data for name, _, data in parts}
    pre = spec.BeaconState.decode_bytes(encoded["pre"])
    post = spec.BeaconState.decode_bytes(encoded["post"])
    target = module.TARGET.for_spec(spec)
    actual = target.record(target.observation(Context(spec, pre, None, post, {})))
    assert meta["claimed"] == actual == record
    if module_name == "historical_summaries_update":
        assert len(post.historical_summaries) - len(pre.historical_summaries) == (bucket == "ZERO")
    elif module_name == "sync_committee_updates" and bucket != "ZERO":
        assert post.current_sync_committee == pre.current_sync_committee
        assert post.next_sync_committee == pre.next_sync_committee
    elif module_name == "slashings_reset":
        index = (int(spec.get_current_epoch(pre)) + 1) % int(spec.EPOCHS_PER_SLASHINGS_VECTOR)
        assert post.slashings[index] == 0
    elif module_name == "randao_mixes_reset":
        epoch = int(spec.get_current_epoch(pre))
        length = int(spec.EPOCHS_PER_HISTORICAL_VECTOR)
        assert post.randao_mixes[(epoch + 1) % length] == pre.randao_mixes[epoch % length]
