"""End-to-end declaration coverage, fault counts, and profile completeness."""

from collections import Counter
from itertools import combinations
from random import Random
from types import SimpleNamespace

import pytest
from ruamel.yaml import YAML

from eth_consensus_specs.test.helpers.specs import spec_targets
from eth_consensus_specs.utils import bls
from tests.generators.compliance_runners.state_transition.evaluation.coverage_dsl import (
    Context,
    load_observations,
    NA,
    score,
)
from tests.generators.compliance_runners.state_transition.validation_helpers import bls_enabled

from . import validation
from .coverage import build_profile
from .materializer import _DIMS, ProposerSlashingMaterializer
from .target import TARGET
from .witness import assignment_from_legacy, materializer_record

PROFILES = ("smoke", "normal", "exceptional", "standard", "max")


def signature(record):
    return tuple((name, record[name]) for name in _DIMS)


@pytest.mark.parametrize("preset", ["minimal", "mainnet"])
def test_full_space_and_max_profile_completeness(preset):
    spec = spec_targets[preset]["gloas"]
    target = TARGET.for_spec(spec)
    configurations = target._configurations(filtered=True)[1]
    # Counts established by the completed migration comparison.
    assert len(configurations) == 1610
    records = [materializer_record(dict(c)) for c in configurations]
    _, generated = build_profile("max", spec=spec)
    low_faults = {
        signature(r)
        for r in records
        if r["_nfaults"] <= 2
    }
    assert len(low_faults) == 360
    assert {signature(r) for r in generated} == low_faults
    assert Counter(r["_nfaults"] for r in generated) == {0: 20, 1: 80, 2: 260}

    def exceptional_pairs(records):
        return {
            tuple((name, r[name]) for name in pair)
            for r in records
            if not r["state_effected"]
            for pair in combinations(_DIMS, 2)
        }

    assert exceptional_pairs(generated) == exceptional_pairs(records)
    report = score(target, [assignment_from_legacy(r) for r in generated], target.profiles["max"])
    assert report.covered == report.total
    assert not report.unexpected
    assert not report.outcome_mismatches


@pytest.mark.parametrize("preset", ["minimal", "mainnet"])
def test_all_generated_profiles_match_observed_assertions_and_cover_obligations(
    preset, monkeypatch
):
    spec = spec_targets[preset]["gloas"]
    monkeypatch.setattr(validation, "spec", spec)
    target = TARGET.for_spec(spec)
    materializer = ProposerSlashingMaterializer(spec)
    materializer.rng = Random(124)
    _, generated = build_profile("max", spec=spec)
    observed_by_signature = {}
    for witness in generated:
        meta, parts = materializer.materialize_solution(SimpleNamespace(**witness))
        encoded = {name: data for name, _, data in parts}
        pre = spec.BeaconState.decode_bytes(encoded["pre"])
        operation = spec.ProposerSlashing.decode_bytes(encoded["proposer_slashing"])
        post = spec.BeaconState.decode_bytes(encoded["post"]) if "post" in encoded else None
        observed = target.record(target.observation(Context(spec, pre, operation, post, {})))
        expected = assignment_from_legacy(witness)
        assert {k: v for k, v in observed.items() if v is not NA} == expected
        result = target.assertion_result(observed)
        assert result.fault_count == witness["_nfaults"] == meta["claimed"]["fault_count"]
        assert result.expected_accepted == observed["accepted"] == (post is not None)
        assert not result.unknown
        recovered = validation.recover(pre, operation)
        assert all(recovered[n] == meta["claimed"][n] for n in _DIMS)
        observed_by_signature[signature(witness)] = observed
    for profile in PROFILES:
        _, representatives = build_profile(profile, spec=spec)
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

    target = TARGET.for_spec(spec)
    configuration = next(
        dict(c)
        for c in target._configurations(filtered=True)[1]
        if target.assertion_result(dict(c)).failed == ("proposers_match",)
    )
    witness = materializer_record(configuration)
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


def test_case_validation_checks_observed_outcome_and_fault_count(tmp_path, monkeypatch):

    spec = spec_targets["minimal"]["gloas"]

    monkeypatch.setattr(validation, "spec", spec)
    _, representatives = build_profile("normal", spec=spec)
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
        SimpleNamespace(**materializer_record(configuration))
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
