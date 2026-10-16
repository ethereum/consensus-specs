"""Consolidation declarations preserve legacy coverage and observe concrete effects."""

import json
from functools import lru_cache
from hashlib import sha256
from types import SimpleNamespace

import pytest

from eth_consensus_specs.test.helpers.specs import spec_targets
from tests.generators.compliance_runners.state_transition.declaration_coverage import (
    materializer_record,
    profile_records,
)
from tests.generators.compliance_runners.state_transition.declaration_validation import (
    recover_record,
    validate_record,
)
from tests.generators.compliance_runners.state_transition.evaluation.coverage_dsl import (
    Context,
    load_observations,
    score,
)
from tests.generators.compliance_runners.state_transition.evaluation.declarations import (
    BoundFormula,
    exhaustive,
)
from tests.generators.compliance_runners.state_transition.provider import (
    load_provider,
    materialize_handler,
)

from .materializer import MATERIALIZER
from .target import FACTORS, NORMAL_SCOPE, SINGLE_FAULT, TARGET

validate_case = load_provider("consolidation_request").validate_case


@lru_cache
def target(preset):
    return TARGET.for_spec(spec_targets[preset]["gloas"], backend="minizinc")


@lru_cache
def records(preset, profile):
    return profile_records(target(preset), profile)


@pytest.mark.parametrize("preset", ["minimal", "mainnet"])
def test_legacy_space_and_fault_scope_fingerprints(preset):
    bound = target(preset)
    # Legacy MiniZinc rows, after Boolean/NA normalization and removal of the
    # three redundant credential-predicate columns. These compare every row,
    # including inactive roles, switch balances, and consolidation churn.
    for scope, expected_count, expected_digest in (
        (None, 27996, "2f528143d0c8c39fb9e586dd6b1bc7ad45ceef8a46cc0cbdb4fd9850e00550be"),
        (NORMAL_SCOPE, 118, "0349c85e8bbf27bbff12f1807534a6711957f07f10148546e760fa4240c30325"),
        (SINGLE_FAULT, 311, "104d5b495c1149c19230c1281ea36f566ab20f94514bb91836bd42e79dd0a1d0"),
    ):
        plan = exhaustive(FACTORS)
        if scope is not None:
            plan = plan * scope
        configurations = BoundFormula(bound, plan).run()
        rows = sorted(
            (tuple(sorted(materializer_record(bound, dict(c)).items())) for c in configurations),
            key=repr,
        )
        assert len(rows) == expected_count
        assert sha256(json.dumps(rows).encode()).hexdigest() == expected_digest


@pytest.mark.parametrize("preset", ["minimal", "mainnet"])
def test_small_smoke_and_all_profile_obligations(preset):
    smoke = records(preset, "smoke")
    assert len(smoke) == len({r["outcome"] for r in smoke}) == 19
    bound = target(preset)
    for name, formula in bound.profiles.items():
        selected = records(preset, name)
        active = [{k: v for k, v in r.items() if v != "NA"} for r in selected]
        assert all(bound.feasible(r) for r in active)
        if name == "max":
            assert {frozenset(r.items()) for r in active} == formula.run()
        else:
            assert formula.covered(active) == formula.run()


def vector(materializer, record):
    spec = materializer.spec
    materializer.test_provider = "consolidation_request"
    solution = SimpleNamespace(**record)
    materializer.rng = materializer._rng_for_solution(solution)
    metadata, parts = materializer.materialize_solution(solution)
    encoded = {name: data for name, _, data in parts}
    return metadata, Context(
        spec,
        spec.BeaconState.decode_bytes(encoded["pre"]),
        spec.ConsolidationRequest.decode_bytes(encoded["consolidation_request"]),
        spec.BeaconState.decode_bytes(encoded["post"]),
        metadata,
    )


def test_every_minimal_signature_survives_serialization():
    spec = spec_targets["minimal"]["gloas"]
    materializer = MATERIALIZER(spec, seed=124)
    for record in records("minimal", "max"):
        metadata, ctx = vector(materializer, record)
        assert recover_record(TARGET, ctx)[2] == metadata["claimed"] == record


def test_mainnet_standard_vectors_and_all_churn_boundaries():
    spec = spec_targets["mainnet"]["gloas"]
    materializer = MATERIALIZER(spec, preset_name="mainnet", seed=124)
    observed = set()
    for record in records("mainnet", "standard"):
        # Full mainnet queues are tested once through smoke below; repeating
        # their 262,144 entries adds no churn or lifecycle coverage here.
        if record["pending_consolidations_capacity"] == "FULL":
            continue
        metadata, ctx = vector(materializer, record)
        assert recover_record(TARGET, ctx)[2] == metadata["claimed"] == record
        observed.add(record["consolidation_churn_to_min_activation"])
        for index, validator in enumerate(ctx.pre.validators):
            assert int(validator.effective_balance) <= int(
                spec.get_max_effective_balance(validator)
            )
            if index >= 64 and spec.is_active_validator(validator, spec.get_current_epoch(ctx.pre)):
                assert spec.has_compounding_withdrawal_credential(validator)
    assert observed == {"LT", "EQ", "GT"}


@pytest.mark.parametrize("preset", ["minimal", "mainnet"])
def test_smoke_pipeline_and_coverage_loading(preset, tmp_path):
    assert (
        materialize_handler("consolidation_request", "smoke", tmp_path, preset_name=preset, seed=7)
        == 19
    )
    bound = target(preset)
    observations = load_observations([tmp_path], bound, preset)
    assert len(observations) == 19
    report = score(bound, [bound.record(o) for o in observations], bound.profiles["smoke"], "smoke")
    assert report.covered == report.total == 19
    assert report.unexpected == []
    assert (
        bound.profiles["smoke"].covered([bound.record(o) for o in observations])
        == bound.profiles["smoke"].run()
    )
    case = next(tmp_path.rglob("case_*"))
    assert all(
        c.status == "ok" for c in validate_case.for_spec(spec_targets[preset]["gloas"], case)
    )
    (case / "post.ssz_snappy").unlink()
    assert any(
        c.dimension == "post_state_present" and c.status == "mismatch"
        for c in validate_case.for_spec(spec_targets[preset]["gloas"], case)
    )


@pytest.mark.parametrize("effect", ["switch", "excess", "consolidation"])
def test_effects_are_observed_from_the_post_state(effect):
    spec = spec_targets["minimal"]["gloas"]
    record = next(
        r
        for r in records("minimal", "normal")
        if (
            r["outcome"]
            == ("CONSOLIDATED" if effect == "consolidation" else "SWITCHED_TO_COMPOUNDING")
            and (effect != "excess" or r["switch_excess_queued"])
        )
    )
    metadata, ctx = vector(MATERIALIZER(spec, seed=7), record)
    assert all(c.status == "ok" for c in validate_record(TARGET, ctx, metadata["claimed"]))
    source = next(
        i for i, v in enumerate(ctx.pre.validators) if v.pubkey == ctx.operation.source_pubkey
    )
    dimension = "state_effected"
    if effect == "switch":
        ctx.post.validators[source].withdrawal_credentials = ctx.pre.validators[
            source
        ].withdrawal_credentials
    elif effect == "excess":
        ctx.post.pending_deposits[-1].amount += 1
        dimension = "switch_excess_queued"
    else:
        ctx.post.pending_consolidations[-1].target_index = source
    assert any(
        c.dimension == dimension and c.status == "mismatch"
        for c in validate_record(TARGET, ctx, metadata["claimed"])
    )


@pytest.mark.parametrize("preset", ["minimal", "mainnet"])
def test_smoke_scoring_avoids_unfiltered_enumeration(preset, monkeypatch):
    bound = TARGET.for_spec(spec_targets[preset]["gloas"], backend="minizinc")
    backend = bound._solver_backend()
    configurations = backend.configurations

    def filtered_only(*, filtered=True, scopes=()):
        assert filtered, "scoring must not enumerate the 2,932,776 unfiltered rows"
        return configurations(filtered=filtered, scopes=scopes)

    monkeypatch.setattr(backend, "configurations", filtered_only)
    selected = profile_records(bound, "smoke")
    assert len(selected) == 19
    monkeypatch.setattr(
        type(backend.model),
        "configurations",
        lambda *a, **kw: pytest.fail("raw native enumeration"),
    )
    observations = [{k: v for k, v in record.items() if v != "NA"} for record in selected]
    formula = bound.profiles["smoke"]
    report = score(bound, observations, formula, "smoke")
    assert report.covered == report.total == 19
    assert report.uncovered == report.unexpected == report.outcome_mismatches == []

    corrupted = next(r for r in observations if r["outcome"] == "CONSOLIDATED")
    corrupted["state_effected"] = False
    report = score(bound, observations, formula, "smoke")
    assert report.covered == 18
    assert report.unexpected == [{"outcome": "CONSOLIDATED", "state_effected": False}]
