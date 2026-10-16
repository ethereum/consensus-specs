"""Withdrawal declarations retain legacy inputs and recover actual vector effects."""

import json
from functools import lru_cache
from hashlib import sha256
from types import SimpleNamespace

import pytest

from eth_consensus_specs.test.helpers.specs import spec_targets
from tests.generators.compliance_runners.state_transition.declaration_validation import (
    recover_record,
    validate_record,
)
from tests.generators.compliance_runners.state_transition.evaluation.coverage_dsl import (
    Context,
    load_observations,
)
from tests.generators.compliance_runners.state_transition.provider import (
    load_provider,
    materialize_handler,
)

from .materializer import MATERIALIZER
from .target import TARGET

build_profile = load_provider("withdrawal_request").build_profile
validate_case = load_provider("withdrawal_request").validate_case


@lru_cache
def records(preset, profile):
    return build_profile(profile, spec=spec_targets[preset]["gloas"])


def faults(record):
    count = int(record["partial_queue_capacity"] == "FULL" and not record["is_full_exit_request"])
    count += int(not record["validator_pubkey_found"])
    if record["validator_pubkey_found"]:
        count += int(
            not (
                record["validator_credential"] in ("ETH1", "COMPOUNDING")
                and record["source_address_matches"]
            )
        )
        count += int(not record["validator_active"])
        count += int(record["validator_exiting"])
        count += int(not record["validator_old_enough"])
    return count


@pytest.mark.parametrize("preset", ["minimal", "mainnet"])
def test_smoke_keeps_one_case_per_terminal_outcome(preset):
    smoke = records(preset, "smoke")
    assert len(smoke) == 12
    assert len({record["outcome"] for record in smoke}) == 12


@pytest.mark.parametrize("preset", ["minimal", "mainnet"])
def test_legacy_space_and_all_profile_obligations(preset):
    maximum = records(preset, "max")
    assert len(maximum) == 6369
    # Fingerprints of the legacy MiniZinc space after Boolean/NA normalization
    # and removing its two redundant credential predicates. Covers every row,
    # outcome, effect, conditional role, and churn variant, independent of TARGET.
    for count, expected_count, expected_digest in (
        (None, 6369, "6a646cadeac1a96ff8d75b3c4dae122c081904e9eecf316ebde308aedc248f9a"),
        (0, 207, "5cb6051aa23be6f3bee578dd348282cc6b4c1ee2b106af4c243b101bf321180e"),
        (1, 905, "59eeea9f0d259690a4894e971fe822ef11163b8267164015754303dc3f53aaed"),
    ):
        rows = sorted(
            (tuple(sorted(r.items())) for r in maximum if count is None or faults(r) == count),
            key=repr,
        )
        assert len(rows) == expected_count
        assert sha256(json.dumps(rows).encode()).hexdigest() == expected_digest
    target = TARGET.for_spec(spec_targets[preset]["gloas"], backend="minizinc")
    for name, formula in target.profiles.items():
        selected = records(preset, name)
        active = [{k: v for k, v in r.items() if v != "NA"} for r in selected]
        assert all(target.feasible(r) for r in active)
        assert formula.covered(active) == formula.run()
        if name in ("normal", "exceptional"):
            assert {faults(r) for r in selected} == {0 if name == "normal" else 1}


def vector(materializer, record):
    spec = materializer.spec
    materializer.test_provider = "withdrawal_request"
    solution = SimpleNamespace(**record)
    materializer.rng = materializer._rng_for_solution(solution)
    metadata, parts = materializer.materialize_solution(solution)
    encoded = {name: data for name, _, data in parts}
    return metadata, Context(
        spec,
        spec.BeaconState.decode_bytes(encoded["pre"]),
        spec.WithdrawalRequest.decode_bytes(encoded["withdrawal_request"]),
        spec.BeaconState.decode_bytes(encoded["post"]),
        metadata,
    )


def test_every_minimal_signature_survives_serialization():
    spec = spec_targets["minimal"]["gloas"]
    materializer = MATERIALIZER(spec, seed=124)
    for record in records("minimal", "max"):
        metadata, ctx = vector(materializer, record)
        assert recover_record(TARGET, ctx)[2] == metadata["claimed"] == record


def test_mainnet_standard_vectors_with_manageable_queue_sizes():
    # The actual mainnet full queue contains 134,217,728 entries. Its abstract
    # assignments are audited above; exercise EMPTY and AVAILABLE concretely.
    spec = spec_targets["mainnet"]["gloas"]
    materializer = MATERIALIZER(spec, preset_name="mainnet", seed=124)
    observed = set()
    for record in records("mainnet", "standard"):
        if record["partial_queue_capacity"] == "FULL":
            continue
        metadata, ctx = vector(materializer, record)
        assert len(ctx.pre.pending_partial_withdrawals) <= 64
        assert recover_record(TARGET, ctx)[2] == metadata["claimed"] == record
        observed.add(record["outcome"])
    assert {"FULL_EXIT_INITIATED", "PARTIAL_QUEUED"} <= observed


def test_exceptional_pipeline_and_coverage_loading(tmp_path):
    spec = spec_targets["minimal"]["gloas"]
    generated = materialize_handler("withdrawal_request", "exceptional", tmp_path, seed=7)
    assert generated == len(records("minimal", "exceptional"))
    target = TARGET.for_spec(spec, backend="minizinc")
    observations = load_observations([tmp_path], target, "minimal")
    assert len(observations) == generated
    assert (
        target.profiles["exceptional"].covered([target.record(o) for o in observations])
        == target.profiles["exceptional"].run()
    )
    case = next(tmp_path.rglob("case_*"))
    assert all(c.status == "ok" for c in validate_case(case))
    (case / "post.ssz_snappy").unlink()
    assert any(
        c.dimension == "post_state_present" and c.status == "mismatch" for c in validate_case(case)
    )


@pytest.mark.parametrize("outcome", ["FULL_EXIT_INITIATED", "PARTIAL_QUEUED"])
def test_effect_is_recovered_from_post_state(outcome):
    spec = spec_targets["minimal"]["gloas"]
    record = next(r for r in records("minimal", "normal") if r["outcome"] == outcome)
    materializer = MATERIALIZER(spec, seed=7)
    metadata, ctx = vector(materializer, record)
    assert all(c.status == "ok" for c in validate_record(TARGET, ctx, metadata["claimed"]))
    if outcome == "FULL_EXIT_INITIATED":
        index = next(
            i
            for i, v in enumerate(ctx.pre.validators)
            if v.pubkey == ctx.operation.validator_pubkey
        )
        ctx.post.validators[index].exit_epoch = ctx.pre.validators[index].exit_epoch
    else:
        ctx.post.pending_partial_withdrawals[-1].amount += 1
    assert any(
        c.dimension == "withdrawal_effected" and c.status == "mismatch"
        for c in validate_record(TARGET, ctx, metadata["claimed"])
    )
