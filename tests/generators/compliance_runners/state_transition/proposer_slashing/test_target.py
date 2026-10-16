"""End-to-end declaration coverage, fault counts, and profile completeness."""

from collections import Counter
from itertools import combinations
from random import Random
from types import SimpleNamespace

import pytest
from ruamel.yaml import YAML

from eth_consensus_specs.test.helpers.specs import spec_targets
from eth_consensus_specs.utils import bls
from tests.generators.compliance_runners.state_transition.declaration_coverage import (
    materializer_record,
)
from tests.generators.compliance_runners.state_transition.evaluation.coverage_dsl import (
    Context,
    load_observations,
    NA,
    score,
)
from tests.generators.compliance_runners.state_transition.provider import load_provider
from tests.generators.compliance_runners.state_transition.validation_helpers import bls_enabled
from tests.generators.compliance_runners.tools.conditional_factors import Model

from .materializer import ProposerSlashingMaterializer
from .target import TARGET

validation = load_provider("proposer_slashing")
build_profile = load_provider("proposer_slashing").build_profile

_DIMS = tuple(f.name for f in TARGET.factors)

PROFILES = ("smoke", "normal", "exceptional", "standard", "max")


@pytest.fixture(scope="module")
def minizinc_available():
    minizinc = pytest.importorskip("minizinc")
    if minizinc.default_driver is None:
        pytest.skip("MiniZinc executable unavailable")
    try:
        minizinc.Solver.lookup("gecode")
    except LookupError:
        pytest.skip("Gecode unavailable")


def signature(record):
    return tuple((name, record[name]) for name in _DIMS)


def assignment(record):
    return {name: record[name] for name in _DIMS if record[name] != "NA"}


@pytest.mark.parametrize("preset", ["minimal", "mainnet"])
def test_full_space_and_max_profile_completeness(preset, minizinc_available):
    spec = spec_targets[preset]["gloas"]
    target = TARGET.for_spec(spec)
    configurations = target._configurations(filtered=True)[1]
    # Counts established by the completed migration comparison.
    assert len(configurations) == 1610
    native = TARGET.for_spec(spec, backend="minizinc")
    assert native._configurations(filtered=True)[1] == configurations
    records = [materializer_record(target, dict(c)) for c in configurations]
    generated = build_profile("max", spec=spec)
    low_faults = {
        signature(r) for r in records if target.assertion_result(assignment(r)).fault_count <= 2
    }
    assert len(low_faults) == 360
    assert {signature(r) for r in generated} == low_faults
    assert Counter(target.assertion_result(assignment(r)).fault_count for r in generated) == {
        0: 20,
        1: 80,
        2: 260,
    }

    def exceptional_pairs(records):
        return {
            tuple((name, r[name]) for name in pair)
            for r in records
            if not r["accepted"]
            for pair in combinations(_DIMS, 2)
        }

    assert exceptional_pairs(generated) == exceptional_pairs(records)
    report = score(target, [assignment(r) for r in generated], target.profiles["max"])
    assert report.covered == report.total
    assert not report.unexpected
    assert not report.outcome_mismatches
    for name in PROFILES:
        expected = [
            materializer_record(target, dict(c))
            for c in target.profiles[name].generation_obligations()
        ]
        actual = build_profile(name, spec=spec)
        assert {tuple(sorted(r.items())) for r in actual} == {
            tuple(sorted(r.items())) for r in expected
        }


def test_provider_uses_native_configuration_generation(monkeypatch, minizinc_available):
    def forbidden(*args, **kwargs):
        pytest.fail("provider used Python configuration enumeration")

    monkeypatch.setattr(Model, "configurations", forbidden)
    assert build_profile("standard", spec=spec_targets["minimal"]["gloas"])


@pytest.mark.parametrize("preset", ["minimal", "mainnet"])
def test_all_generated_profiles_match_observed_assertions_and_cover_obligations(
    preset, monkeypatch, minizinc_available
):
    spec = spec_targets[preset]["gloas"]
    validation = load_provider("proposer_slashing", spec=spec)
    target = TARGET.for_spec(spec)
    materializer = ProposerSlashingMaterializer(spec)
    materializer.rng = Random(124)
    generated = build_profile("max", spec=spec)
    observed_by_signature = {}
    for witness in generated:
        meta, parts = materializer.materialize_solution(SimpleNamespace(**witness))
        encoded = {name: data for name, _, data in parts}
        pre = spec.BeaconState.decode_bytes(encoded["pre"])
        operation = spec.ProposerSlashing.decode_bytes(encoded["proposer_slashing"])
        post = spec.BeaconState.decode_bytes(encoded["post"]) if "post" in encoded else None
        observed = target.record(target.observation(Context(spec, pre, operation, post, {})))
        expected = assignment(witness)
        assert {k: v for k, v in observed.items() if v is not NA} == expected
        result = target.assertion_result(observed)
        assert result.fault_count == meta["claimed"]["fault_count"]
        assert result.expected_accepted == observed["accepted"] == (post is not None)
        assert not result.unknown
        recovered = validation.recover(pre, operation, post)
        assert all(recovered[n] == meta["claimed"][n] for n in _DIMS)
        observed_by_signature[signature(witness)] = observed
    for profile in PROFILES:
        representatives = build_profile(profile, spec=spec)
        records = [observed_by_signature[signature(r)] for r in representatives]
        if profile == "exceptional":
            assert all(target.assertion_result(r).fault_count == 1 for r in records)
        if profile == "normal":
            assert all(target.assertion_result(r).fault_count == 0 for r in records)
        report = score(target, records, target.profiles[profile])
        assert report.covered == report.total, report.uncovered
        assert not report.unexpected
        assert not report.outcome_mismatches


def test_mismatched_proposers_use_first_proposer_key_for_both_signatures(monkeypatch):
    spec = spec_targets["minimal"]["gloas"]
    validation = load_provider("proposer_slashing", spec=spec)

    target = TARGET.for_spec(spec)
    configuration = next(
        dict(c)
        for c in target._configurations(filtered=True)[1]
        if target.assertion_result(dict(c)).failed == ("proposers_match",)
    )
    witness = materializer_record(target, configuration)
    materializer = ProposerSlashingMaterializer(spec)
    materializer.rng = Random(7)
    monkeypatch.setattr(bls, "bls_active", False)
    _, parts = materializer.materialize_solution(SimpleNamespace(**witness))
    encoded = {name: data for name, _, data in parts}
    pre = spec.BeaconState.decode_bytes(encoded["pre"])
    operation = spec.ProposerSlashing.decode_bytes(encoded["proposer_slashing"])
    observed = target.record(target.observation(Context(spec, pre, operation, None, {})))
    assert target.assertion_result(observed).failed == ("proposers_match",)
    assert bls.bls_active is False
    h2 = operation.signed_header_2
    domain = spec.get_domain(
        pre, spec.DOMAIN_BEACON_PROPOSER, spec.compute_epoch_at_slot(h2.message.slot)
    )
    with bls_enabled():
        assert not bls.Verify(
            pre.validators[h2.message.proposer_index].pubkey,
            spec.compute_signing_root(h2.message, domain),
            h2.signature,
        )
    # Unlike the old per-header-key observer, the target also detects a bad
    # signature behind the earlier proposer mismatch.
    h2.signature = spec.BLSSignature()
    observed = target.record(target.observation(Context(spec, pre, operation, None, {})))
    assert target.assertion_result(observed).failed == ("proposers_match", "signature_2_valid")
    recovered = validation.recover(pre, operation)
    assert recovered["signature_1_valid"] is True
    assert recovered["signature_2_valid"] is False
    assert recovered["proposers_match"] is False
    assert bls.bls_active is False


def test_missing_validator_is_unknown_and_post_is_not_predicted():
    spec = spec_targets["minimal"]["gloas"]

    target = TARGET.for_spec(spec)
    pre = ProposerSlashingMaterializer(spec)._base_state()
    operation = spec.ProposerSlashing()
    for header in (operation.signed_header_1, operation.signed_header_2):
        header.message.proposer_index = len(pre.validators)
    operation.signed_header_2.message.body_root = spec.Root(b"\x01" * 32)
    observed = target.record(target.observation(Context(spec, pre, operation, None, {})))
    result = target.assertion_result(observed)
    assert result.fault_count is None
    assert result.expected_accepted is None
    assert observed["accepted"] is False
    assert observed["signature_1_valid"] is NA


def test_case_validation_checks_observed_outcome_and_fault_count(
    tmp_path, monkeypatch, minizinc_available
):

    spec = spec_targets["minimal"]["gloas"]

    validation = load_provider("proposer_slashing", spec=spec)
    representatives = build_profile("normal", spec=spec)
    materializer = ProposerSlashingMaterializer(spec)
    materializer.test_provider = "proposer_slashing"
    materializer.materialize_reps(tmp_path, [SimpleNamespace(**representatives[0])])
    case = next(tmp_path.rglob("case_*"))
    assert all(check.status == "ok" for check in validation.validate_case(case))
    target = TARGET.for_spec(spec)
    observations = load_observations([tmp_path], target, "minimal")
    assert len(observations) == 1
    assert target.assertion_result(target.record(observations[0])).fault_count == 0
    yaml = YAML()
    dimensions_path = case / "dimensions.yaml"
    dimensions = yaml.load(dimensions_path.read_text())
    dimensions["claimed"]["fault_count"] = 1
    with dimensions_path.open("w") as stream:
        yaml.dump(dimensions, stream)
    assert any(
        check.dimension == "fault_count" and check.status == "mismatch"
        for check in validation.validate_case(case)
    )
    (case / "post.ssz_snappy").unlink()
    checks = validation.validate_case(case)
    assert any(check.dimension == "accepted" and check.status == "mismatch" for check in checks)
    assert any(
        check.dimension == "assertion_outcome" and check.status == "mismatch" for check in checks
    )


def test_absent_pending_payment_is_not_reported_as_a_clearing_effect():
    spec = spec_targets["minimal"]["gloas"]
    target = TARGET.for_spec(spec)
    configuration = next(
        dict(c)
        for c in target._configurations(filtered=True)[1]
        if dict(c)["accepted"]
        and dict(c)["payment_window"] == "CURRENT"
        and not dict(c)["payment_proposer_matches"]
    )
    materializer = ProposerSlashingMaterializer(spec)
    materializer.rng = Random(124)
    _, parts = materializer.materialize_solution(
        SimpleNamespace(**materializer_record(target, configuration))
    )
    encoded = {name: data for name, _, data in parts}
    pre = spec.BeaconState.decode_bytes(encoded["pre"])
    operation = spec.ProposerSlashing.decode_bytes(encoded["proposer_slashing"])
    index = spec.SLOTS_PER_EPOCH + operation.signed_header_1.message.slot % spec.SLOTS_PER_EPOCH
    pre.builder_pending_payments[index] = spec.BuilderPendingPayment.empty()
    post = pre.copy()
    with bls_enabled():
        spec.process_proposer_slashing(post, operation)
    observed = target.record(target.observation(Context(spec, pre, operation, post, {})))
    assert target.assertion_result(observed).fault_count == 0
    assert observed["accepted"] is True
    assert observed["pending_payment_cleared"] is NA
    assert target.feasible(observed)
