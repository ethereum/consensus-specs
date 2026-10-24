"""Native target profiles realize their complete declared coverage."""

from random import Random
from types import SimpleNamespace

import pytest

from eth_consensus_specs.test.helpers.specs import spec_targets
from eth_consensus_specs.utils import bls
from tests.generators.compliance_runners.state_transition.evaluation.coverage_dsl import (
    Context,
    NA,
    score,
)
from tests.generators.compliance_runners.state_transition.provider import load_provider
from tests.generators.compliance_runners.state_transition.validation_helpers import bls_enabled
from tests.generators.compliance_runners.tools.conditional_factors import Model

from .materializer import VoluntaryExitMaterializer
from .target import TARGET
from .test_utils import CHURN_CASES

validation = load_provider("voluntary_exit")
build_profile = load_provider("voluntary_exit").build_profile


@pytest.fixture(scope="module", autouse=True)
def minizinc_available():
    minizinc = pytest.importorskip("minizinc")
    if minizinc.default_driver is None:
        pytest.skip("MiniZinc executable unavailable")
    try:
        minizinc.Solver.lookup("gecode")
    except LookupError:
        pytest.skip("Gecode unavailable")


@pytest.fixture(scope="module", params=("minimal", "mainnet"))
def profiles(request):
    preset = request.param
    spec = spec_targets[preset]["gloas"]
    target = TARGET.for_spec(spec, backend="minizinc")
    records = {name: build_profile(name, spec=spec) for name in target.profiles}
    return preset, spec, target, records


def assignment(record):
    return {n: v for n, v in record.items() if not n.startswith("_") and v != "NA"}


def test_profiles_cover_native_formulas_and_match_python(profiles):
    _, spec, target, profiles = profiles
    python = TARGET.for_spec(spec)
    assert target._configurations(filtered=True)[1] == python._configurations(filtered=True)[1]
    names = {f.name for f in target.factors}
    for name, records in profiles.items():
        assert records
        assert all(set(r) == names for r in records)
        formula = target.profiles[name]
        # Full cross-backend formula equivalence is exercised for this target
        # by evaluation/test_minizinc_backend.py. Keep these provider checks
        # focused on generation, fault scope, and realized coverage.
        if name in ("smoke", "normal", "pending_loop"):
            assert (
                formula.generation_obligations() == python.profiles[name].generation_obligations()
            )
        report = score(target, [assignment(r) for r in records], formula)
        assert report.covered == report.total
        assert not report.unexpected
        assert not report.outcome_mismatches
        if name == "normal":
            assert all(
                r["accepted"] and target.assertion_result(assignment(r)).fault_count == 0
                for r in records
            )
        elif name == "exceptional":
            assert all(
                not r["accepted"] and target.assertion_result(assignment(r)).fault_count == 1
                for r in records
            )
            assert all(r["activation_le_current"] for r in records)
    # These branches were absent from the scenario provider.
    assert {r["matching_pending_entries"] for r in profiles["max"]} == {"ZERO", "ONE", "MANY"}
    assert any(not r["current_lt_exit"] for r in profiles["max"])


def test_provider_uses_native_configuration_generation(monkeypatch):
    def forbidden(*args, **kwargs):
        pytest.fail("provider used Python configuration enumeration")

    monkeypatch.setattr(Model, "configurations", forbidden)
    assert build_profile("smoke", spec=spec_targets["minimal"]["gloas"])


def test_all_profile_witnesses_materialize_exact_dimensions(profiles, monkeypatch):
    preset, spec, target, profiles = profiles
    validation = load_provider("voluntary_exit", spec=spec)
    # Signature verification and processing must work even with BLS disabled
    # globally, without changing that global setting after each case.
    monkeypatch.setattr(bls, "bls_active", False)
    materializer = VoluntaryExitMaterializer(spec, preset_name=preset, seed=124)
    materializer.rng = Random(124)
    unique = {tuple(sorted(r.items())): r for records in profiles.values() for r in records}
    observed_by_witness = {}
    for key, record in unique.items():
        meta, parts = materializer.materialize_solution(SimpleNamespace(**record))
        encoded = {name: data for name, _, data in parts}
        pre = spec.BeaconState.decode_bytes(encoded["pre"])
        operation = spec.SignedVoluntaryExit.decode_bytes(encoded["voluntary_exit"])
        post = spec.BeaconState.decode_bytes(encoded["post"]) if "post" in encoded else None
        observed = target.record(target.observation(Context(spec, pre, operation, post, {})))
        assert {n: v for n, v in observed.items() if v is not NA} == assignment(record), record
        assert (post is not None) == record["accepted"]
        summary = target.assertion_result(observed)
        assert summary.fault_count == meta["claimed"]["fault_count"]
        assert summary.expected_accepted == record["accepted"]
        actual = validation.recover(pre, operation, post)
        assert {n: meta["claimed"][n] for n in actual} == actual
        assert bls.bls_active is False
        observed_by_witness[key] = observed
    for name, records in profiles.items():
        report = score(
            target,
            [observed_by_witness[tuple(sorted(r.items()))] for r in records],
            target.profiles[name],
        )
        assert report.covered == report.total
        assert not report.unexpected
        assert not report.outcome_mismatches


def test_canonical_dimensions_validate_saved_case(profiles, monkeypatch, tmp_path):
    preset, spec, _, profiles = profiles
    validation = load_provider("voluntary_exit", spec=spec)
    records = profiles["normal"]
    materializer = VoluntaryExitMaterializer(spec, preset_name=preset)
    materializer.test_provider = "voluntary_exit"
    with bls_enabled():
        materializer.materialize_reps(tmp_path, [SimpleNamespace(**records[0])])
    case = next(tmp_path.rglob("case_*"))
    assert all(check.status == "ok" for check in validation.validate_case(case))
    (case / "post.ssz_snappy").unlink()
    mismatches = {
        check.dimension for check in validation.validate_case(case) if check.status == "mismatch"
    }
    assert {"accepted", "assertion_outcome"} <= mismatches


def test_churn_profile_coverage(profiles):
    _, _, _, profiles = profiles
    for profile in ("normal", "max"):
        records = profiles[profile]
        assert {
            (
                "NEW_EPOCH"
                if r["earliest_lt_new"]
                else "CARRIED_EXHAUSTED"
                if r["balance_gt_consumable"] in ("GT_1", "GT_FAR")
                else "CARRIED_AVAILABLE",
                r["balance_gt_consumable"],
                "ZERO" if r["additional_epochs"] == "NA" else r["additional_epochs"],
            )
            for r in records
        } == set(CHURN_CASES)
