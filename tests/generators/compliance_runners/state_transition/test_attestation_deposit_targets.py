"""Attestation and pending-deposit declaration witnesses match concrete vectors."""

from types import SimpleNamespace

import pytest

from eth_consensus_specs.test.helpers.specs import spec_targets
from eth_consensus_specs.utils import bls
from tests.generators.compliance_runners.state_transition.declaration_validation import (
    recover_record,
    validate_record,
)
from tests.generators.compliance_runners.state_transition.evaluation.coverage_dsl import (
    Context,
)
from tests.generators.compliance_runners.state_transition.provider import (
    load_provider,
    materialize_handler,
)


def case_context(module, spec, materializer, record):
    solution = SimpleNamespace(**record)
    materializer.rng = materializer._rng_for_solution(solution)
    meta, parts = materializer.materialize_solution(solution)
    encoded = {name: data for name, _, data in parts}
    return meta, Context(
        spec,
        spec.BeaconState.decode_bytes(encoded["pre"]),
        spec.Attestation.decode_bytes(encoded["attestation"])
        if module.TARGET.name == "attestation"
        else None,
        spec.BeaconState.decode_bytes(encoded["post"]) if "post" in encoded else None,
        {},
    )


@pytest.mark.parametrize("preset", ["minimal", "mainnet"])
@pytest.mark.parametrize(("provider", "count"), [("attestation", 111), ("pending_deposits", 74)])
def test_max_vectors_and_profile_obligations(preset, provider, count, monkeypatch):
    module = load_provider(provider)
    spec = spec_targets[preset]["gloas"]
    target = module.TARGET.for_spec(spec, backend="minizinc")
    records = module.build_profile("max", spec=spec)
    assert len(records) == count
    materializer = module.MATERIALIZER(spec, preset_name=preset, seed=124)
    materializer.test_provider = provider
    # Generation and observation must perform real BLS work even when another
    # runner has disabled it globally, and restore that caller's setting.
    monkeypatch.setattr(bls, "bls_active", False)
    observations = []
    for record in records:
        meta, ctx = case_context(module, spec, materializer, record)
        _, observed, actual = recover_record(module.TARGET, ctx)
        assert actual == meta["claimed"] == record
        assert bls.bls_active is False
        observations.append(observed)
    for name, formula in target.profiles.items():
        selected = module.build_profile(name, spec=spec)
        representatives = [{k: v for k, v in record.items() if v != "NA"} for record in selected]
        for observed in (representatives, observations):
            assert formula.covered(observed) == formula.run()
            assert all(target.feasible(record) for record in observed)
        if provider == "attestation" and name in ("normal", "exceptional"):
            for record in selected:
                faults = int(not record["target_epoch_in_window"])
                faults += int(
                    record["target_epoch_in_window"] and not record["target_epoch_matches_slot"]
                )
                faults += int(not record["inclusion_delay_ok"]) + int(not record["index_valid"])
                applicable = record["index_valid"]
                for gate in (
                    "committee_indices_valid",
                    "committee_nonempty",
                    "aggregation_length_valid",
                    "signature_valid",
                ):
                    faults += int(applicable and not record[gate])
                    applicable = applicable and record[gate]
                assert faults == (0 if name == "normal" else 1)
    if provider == "pending_deposits":
        assert module.build_profile("exceptional", spec=spec) == []


@pytest.mark.parametrize("provider", ["attestation", "pending_deposits"])
@pytest.mark.parametrize("preset", ["minimal", "mainnet"])
def test_smoke_provider_pipeline(provider, preset, tmp_path):
    assert materialize_handler(provider, "smoke", tmp_path, preset_name=preset, seed=7) == (
        10 if provider == "attestation" else 5
    )


@pytest.mark.parametrize("provider", ["attestation", "pending_deposits"])
def test_effect_observation_uses_post_state(provider):
    module = load_provider(provider)
    spec = spec_targets["minimal"]["gloas"]
    effect = "payment_weight_increased" if provider == "attestation" else "churn_effect"
    expected = True if provider == "attestation" else "CHURN_RETAINED"
    record = next(r for r in module.build_profile("max", spec=spec) if r[effect] == expected)
    materializer = module.MATERIALIZER(spec, seed=7)
    materializer.test_provider = provider
    _, ctx = case_context(module, spec, materializer, record)
    assert all(check.status == "ok" for check in validate_record(module.TARGET, ctx, record))
    if provider == "attestation":
        ctx.post.builder_pending_payments = ctx.pre.builder_pending_payments.copy()
    else:
        ctx.post.deposit_balance_to_consume = spec.Gwei(0)
    assert any(
        check.dimension == effect and check.status == "mismatch"
        for check in validate_record(module.TARGET, ctx, record)
    )
