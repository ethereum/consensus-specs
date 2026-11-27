from random import Random
from types import SimpleNamespace

from eth_consensus_specs.gloas import minimal as spec
from tests.generators.compliance_runners.state_transition.evaluation.invariant_scan import (
    state_invariant_violations,
)
from tests.generators.compliance_runners.state_transition.provider import load_provider


def test_already_slashed_intersection_has_consistent_exit():
    provider = load_provider("attester_slashing")
    record = next(
        record
        for record in provider.build_profile("max", spec=spec)
        if record["outcome"] == "REJECT_NO_SLASHABLE_INTERSECTION"
    )
    materializer = provider.MATERIALIZER(spec)
    materializer.rng = Random(0)
    _, parts = materializer.materialize_solution(SimpleNamespace(**record))
    encoded = {name: data for name, _, data in parts}
    pre = spec.BeaconState.decode_bytes(encoded["pre"])
    (slashed,) = [validator for validator in pre.validators if validator.slashed]

    assert "post" not in encoded
    assert not list(state_invariant_violations(spec, pre))
    assert pre.slashings[spec.get_current_epoch(pre) % spec.EPOCHS_PER_SLASHINGS_VECTOR] == (
        slashed.effective_balance
    )
