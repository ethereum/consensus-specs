"""Fixed coverage regressions and end-to-end payload-attestation validation."""

from collections import Counter
from itertools import combinations
from types import SimpleNamespace

import pytest
from ruamel.yaml import YAML

from eth_consensus_specs.test.helpers.specs import spec_targets
from eth_consensus_specs.utils import bls
from tests.generators.compliance_runners.runner.state_transition import run_processing_case
from tests.generators.compliance_runners.state_transition.declaration_coverage import (
    materializer_record,
)
from tests.generators.compliance_runners.state_transition.evaluation.coverage_dsl import (
    Context,
    load_observations,
    NA,
    score,
)
from tests.generators.compliance_runners.state_transition.provider import decode, load_provider
from tests.generators.compliance_runners.state_transition.validation_helpers import bls_enabled
from tests.generators.compliance_runners.tools.conditional_factors import Model

from .materializer import PayloadAttestationMaterializer
from .target import TARGET

validation = load_provider("payload_attestation")
build_profile = load_provider("payload_attestation").build_profile

PROFILES = ("smoke", "normal", "exceptional", "standard", "max")
COUNTS = {"smoke": 5, "normal": 2, "exceptional": 4, "standard": 6, "max": 17}
OBLIGATIONS = {**COUNTS, "max": 87}
_DIMS = tuple(f.name for f in TARGET.factors if f.name != "accepted")

# Signatures established by the completed migration comparison, in _DIMS order.
EXPECTED_SIGNATURES = {
    (False, False, "ALL", True, False, "REJECT_PARENT_ROOT"),
    (False, False, "ALL", True, True, "REJECT_PARENT_ROOT"),
    (False, False, "EMPTY", False, "NA", "REJECT_PARENT_ROOT"),
    (False, False, "PARTIAL", True, False, "REJECT_PARENT_ROOT"),
    (False, False, "PARTIAL", True, True, "REJECT_PARENT_ROOT"),
    (False, True, "ALL", True, False, "REJECT_PARENT_ROOT"),
    (False, True, "ALL", True, True, "REJECT_PARENT_ROOT"),
    (False, True, "EMPTY", False, "NA", "REJECT_PARENT_ROOT"),
    (False, True, "PARTIAL", True, False, "REJECT_PARENT_ROOT"),
    (False, True, "PARTIAL", True, True, "REJECT_PARENT_ROOT"),
    (True, False, "ALL", True, False, "REJECT_SLOT"),
    (True, False, "ALL", True, True, "REJECT_SLOT"),
    (True, False, "EMPTY", False, "NA", "REJECT_SLOT"),
    (True, False, "PARTIAL", True, False, "REJECT_SLOT"),
    (True, False, "PARTIAL", True, True, "REJECT_SLOT"),
    (True, True, "ALL", True, False, "REJECT_SIGNATURE"),
    (True, True, "ALL", True, True, "ACCEPT"),
    (True, True, "EMPTY", False, "NA", "REJECT_EMPTY"),
    (True, True, "PARTIAL", True, False, "REJECT_SIGNATURE"),
    (True, True, "PARTIAL", True, True, "ACCEPT"),
}
EXPECTED_RECORDS = [dict(zip(_DIMS, row, strict=True)) for row in EXPECTED_SIGNATURES]
OUTCOMES = {r["outcome"] for r in EXPECTED_RECORDS}


def fault_count(record):
    return (
        int(not record["parent_root_matches"])
        + int(not record["slot_is_previous"])
        + int(not record["attesting_indices_nonempty"])
        + int(record["signature_valid"] is False)
    )


def signature(record):
    return tuple(record[name] for name in _DIMS)


def assignment(record):
    values = {name: record[name] for name in _DIMS if name != "signature_valid"}
    if record["attesting_indices_nonempty"]:
        values["signature_valid"] = record["signature_valid"]
    values["accepted"] = record["outcome"] == "ACCEPT"
    return values


def exceptional_pairs(records):
    return {
        tuple((n, r[n]) for n in names)
        for r in records
        if fault_count(r) > 0
        for names in combinations(_DIMS, 2)
    }


@pytest.fixture(scope="module", autouse=True)
def minizinc_available():
    minizinc = pytest.importorskip("minizinc")
    if minizinc.default_driver is None:
        pytest.skip("MiniZinc executable unavailable")
    try:
        minizinc.Solver.lookup("gecode")
    except LookupError:
        pytest.skip("Gecode unavailable")


@pytest.fixture(params=("minimal", "mainnet"))
def configured_spec(request, monkeypatch):
    preset = request.param
    spec = spec_targets[preset]["gloas"]
    # The materializer needs a matching post-Gloas configuration.
    monkeypatch.setattr(spec, "config", spec.config._replace(GLOAS_FORK_EPOCH=spec.GENESIS_EPOCH))
    return preset, spec


def test_full_feasible_space_and_fault_counts(configured_spec):
    _, spec = configured_spec
    python = TARGET.for_spec(spec)
    solver = TARGET.for_spec(spec, backend="minizinc")
    configurations = solver._configurations(filtered=True)[1]
    assert configurations == python._configurations(filtered=True)[1]
    records = [materializer_record(solver, dict(c)) for c in configurations]
    assert {signature(r) for r in records} == EXPECTED_SIGNATURES
    assert Counter(solver.assertion_result(assignment(r)).fault_count for r in records) == {
        0: 2,
        1: 7,
        2: 8,
        3: 3,
    }
    for r in records:
        assert solver.assertion_result(assignment(r)).fault_count == fault_count(r)
        assert (r["signature_valid"] == "NA") == (not r["attesting_indices_nonempty"])


@pytest.mark.parametrize("profile_name", PROFILES)
def test_profiles_preserve_coverage(configured_spec, profile_name):
    _, spec = configured_spec
    target = TARGET.for_spec(spec, backend="minizinc")
    records = build_profile(profile_name, spec=spec)
    assert len(records) == COUNTS[profile_name]
    assert {signature(r) for r in records} <= EXPECTED_SIGNATURES
    for record in records:
        assert record["accepted"] == (record["outcome"] == "ACCEPT")
        assert set(record) == {f.name for f in target.factors}
        assert target.assertion_result(assignment(record)).fault_count == fault_count(record)
    normal = {signature(r) for r in EXPECTED_RECORDS if fault_count(r) == 0}
    if profile_name == "normal":
        assert {signature(r) for r in records} == normal
    elif profile_name == "max":
        assert {signature(r) for r in records} == {
            signature(r) for r in EXPECTED_RECORDS if fault_count(r) <= 2
        }
        assert exceptional_pairs(records) == exceptional_pairs(EXPECTED_RECORDS)
    else:
        assert {r["outcome"] for r in records} == (
            OUTCOMES - {"ACCEPT"} if profile_name == "exceptional" else OUTCOMES
        )
        assert Counter(fault_count(r) for r in records) == (
            {1: 4}
            if profile_name == "exceptional"
            else {0: 1, 1: 4}
            if profile_name == "smoke"
            else {0: 2, 1: 4}
        )
        if profile_name == "standard":
            assert {signature(r) for r in records if fault_count(r) == 0} == normal
    report = score(target, [assignment(r) for r in records], target.profiles[profile_name])
    assert report.covered == report.total == OBLIGATIONS[profile_name]
    assert not report.unexpected
    assert not report.outcome_mismatches


def test_provider_uses_minizinc_not_python_enumeration(configured_spec, monkeypatch):
    def forbidden(*args, **kwargs):
        pytest.fail("provider used Python configuration enumeration")

    monkeypatch.setattr(Model, "configurations", forbidden)
    _, spec = configured_spec
    records = build_profile("standard", spec=spec)
    assert len(records) == COUNTS["standard"]


def test_materialized_space_validates_and_covers_profiles(configured_spec, tmp_path, monkeypatch):
    preset, spec = configured_spec
    validation = load_provider("payload_attestation", spec=spec)
    target = TARGET.for_spec(spec, backend="minizinc")
    records = sorted(
        (materializer_record(target, dict(c)) for c in target._configurations(filtered=True)[1]),
        key=lambda r: repr(signature(r)),
    )
    materializer = PayloadAttestationMaterializer(spec, preset_name=preset, seed=124)
    materializer.test_provider = "payload_attestation"
    observed_by_signature = {}
    with bls_enabled():
        count = materializer.materialize_reps(tmp_path, [SimpleNamespace(**r) for r in records])
        assert count == 20
        cases = sorted(tmp_path.rglob("case_*"))
        assert len(cases) == 20
        for case in cases:
            assert all(c.status == "ok" for c in validation.validate_case(case))
            claimed = YAML(typ="safe").load((case / "dimensions.yaml").read_text())["claimed"]
            pre = decode(case / "pre.ssz_snappy", spec.BeaconState)
            operation = decode(case / "payload_attestation.ssz_snappy", spec.PayloadAttestation)
            post = (
                decode(case / "post.ssz_snappy", spec.BeaconState)
                if (case / "post.ssz_snappy").exists()
                else None
            )
            observed = target.record(target.observation(Context(spec, pre, operation, post, {})))
            assert validation.recover(pre, operation, post) == {
                n: v for n, v in claimed.items() if n != "fault_count"
            }
            if post is not None:
                assert validation.recover(pre, operation)["accepted"] is False
            assert {n: v for n, v in observed.items() if v is not NA} == assignment(claimed)
            assert target.assertion_result(observed).fault_count == fault_count(claimed)
            assert observed["accepted"] == (claimed["outcome"] == "ACCEPT")
            run_processing_case(spec.process_payload_attestation, pre.copy(), operation, post)
            observed_by_signature[signature(claimed)] = observed
        assert len(load_observations([tmp_path], target, preset)) == 20
        for name in PROFILES:
            chosen = build_profile(name, spec=spec)
            observations = [observed_by_signature[signature(r)] for r in chosen]
            report = score(target, observations, target.profiles[name])
            assert report.covered == report.total == OBLIGATIONS[name]
            assert not report.unexpected
            assert not report.outcome_mismatches
    # An invalid signature remains observable with BLS disabled globally.
    bad = next(
        case
        for case in cases
        if YAML(typ="safe").load((case / "dimensions.yaml").read_text())["claimed"][
            "signature_valid"
        ]
        is False
    )
    pre = decode(bad / "pre.ssz_snappy", spec.BeaconState)
    operation = decode(bad / "payload_attestation.ssz_snappy", spec.PayloadAttestation)
    monkeypatch.setattr(bls, "bls_active", False)
    observed = target.record(target.observation(Context(spec, pre, operation, None, {})))
    assert observed["signature_valid"] is False
    assert validation.recover(pre, operation)["signature_valid"] is False
    assert all(c.status == "ok" for c in validation.validate_case(bad))
    assert bls.bls_active is False
