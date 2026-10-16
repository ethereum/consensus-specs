"""Complete declaration witnesses survive concrete state construction."""

from random import Random
from types import SimpleNamespace

import pytest

from eth_consensus_specs.gloas import minimal as spec
from tests.generators.compliance_runners.state_transition.evaluation.coverage_dsl import (
    Context,
    NA,
    score,
)
from tests.generators.compliance_runners.state_transition.provider import load_provider


@pytest.mark.parametrize(
    "provider",
    [
        "effective_balance_updates",
        "inactivity_updates",
        "inactivity_updates_loop",
        "registry_updates",
        "rewards_and_penalties",
        "justification_and_finalization",
        "participation_flag_updates",
        "slot_processing",
        "sync_committee_updates",
    ],
)
def test_complete_max_witnesses_match_materialized_observations(provider):
    module = load_provider(provider)
    target = module.TARGET.for_spec(spec)
    formula = target.profiles["max"]
    records = [dict(witness) for witness in formula.generation_obligations()]
    materializer = module.MATERIALIZER(spec)
    materializer.rng = Random(0)
    observed = []
    for record in records:
        meta, parts = materializer.materialize_solution(SimpleNamespace(**record))
        encoded = {name: data for name, _, data in parts}
        context = Context(
            spec,
            spec.BeaconState.decode_bytes(encoded["pre"]),
            encoded.get("slots"),
            spec.BeaconState.decode_bytes(encoded["post"]),
            {},
        )
        actual = target.record(target.observation(context))
        assert meta["claimed"] == {k: "NA" if v is NA else v for k, v in actual.items()}
        assert record == {k: v for k, v in actual.items() if v is not NA}
        observed.append(actual)
    report = score(target, observed, formula)
    assert report.covered == report.total
    assert not report.unexpected
