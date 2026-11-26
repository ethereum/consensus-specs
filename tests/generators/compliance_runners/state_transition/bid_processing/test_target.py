"""Bid declarations preserve finality-compatible signatures and recover vectors independently."""

import json
from functools import lru_cache
from hashlib import sha256
from itertools import combinations
from random import Random
from types import SimpleNamespace

import pytest
from ruamel.yaml import YAML

from eth_consensus_specs.test.helpers.execution_payload import compute_el_block_hash
from eth_consensus_specs.test.helpers.specs import spec_targets
from eth_consensus_specs.utils import bls
from tests.generators.compliance_runners.runner.discovery import gather_tests
from tests.generators.compliance_runners.runner.state_transition import (
    run_test,
)
from tests.generators.compliance_runners.state_transition.declaration_coverage import (
    profile_records,
)
from tests.generators.compliance_runners.state_transition.declaration_validation import (
    recover_record,
)
from tests.generators.compliance_runners.state_transition.evaluation.coverage_dsl import (
    Context,
    load_observations,
    score,
)
from tests.generators.compliance_runners.state_transition.evaluation.invariant_scan import (
    state_invariant_violations,
)
from tests.generators.compliance_runners.state_transition.provider import (
    load_provider,
    materialize_handler,
)

from .concretization import _pick_balance_and_bid_value
from .materializer import MATERIALIZER
from .target import INPUT_ASPECTS, TARGET

validate_case = load_provider("bid_processing").validate_case


@lru_cache
def target(preset):
    bound = TARGET.for_spec(spec_targets[preset]["gloas"])
    assert bound.backend == "minizinc"
    return bound


@lru_cache
def records(preset, profile):
    return profile_records(target(preset), profile)


def digest(rows):
    canonical = sorted((tuple(sorted(r.items())) for r in rows), key=repr)
    return sha256(json.dumps(canonical).encode()).hexdigest()


def input_pairs(rows):
    return {
        tuple((name, r[name]) for name in sorted({f.name for a in pair for f in a.declarations}))
        for pair in combinations(INPUT_ASPECTS, 2)
        for r in rows
    }


@pytest.mark.parametrize("preset", ["minimal", "mainnet"])
def test_finality_compatible_legacy_space_and_fault_scopes(preset):
    # Fingerprints of the original max rows after applying the finality
    # constraints to deposits and exits.
    all_records = records(preset, "max")
    for faults, count, expected in (
        (None, 661, "5816b8b0f0ccf3916945fc58a429d4a70fd584b3a26b2f993728e2751236c338"),
        (0, 34, "3e1385d450db5b9871ae0e7b72c04029dae381476ab78e8ba3590475cc08e99d"),
        (1, 353, "946fa0e13214041a3eef9eaab45e596a1cd58f6c9d8599953eb002c7b982deb3"),
        (2, 274, "5c1e9c7fd1a7d4d70d998a2571997239092faa058ea0d955472efa28733e64b5"),
    ):
        selected = [r for r in all_records if faults is None or r["fault_count"] == faults]
        assert len(selected) == count
        assert digest(selected) == expected
    assert all(
        target(preset).feasible({k: v for k, v in r.items() if v != "NA"}) for r in all_records
    )


@pytest.mark.parametrize("preset", ["minimal", "mainnet"])
def test_profile_coverage_and_small_smoke(preset):
    smoke = records(preset, "smoke")
    assert len(smoke) == 12
    assert {r["outcome"] for r in smoke} == {r["outcome"] for r in records(preset, "max")}
    assert all(r["fault_count"] <= 1 for r in smoke)
    normal = records(preset, "normal")
    assert len(normal) == 21
    assert all(r["fault_count"] == 0 and r["outcome"] == "ACCEPT" for r in normal)
    # Compare against the grouped pairwise obligations of the retained legacy rows.
    projections = input_pairs(normal)
    assert len(projections) == 189
    assert (
        sha256(json.dumps(sorted(projections, key=repr)).encode()).hexdigest()
        == "3cc2b4277660e2f324b3e536b96fb59bd507157a8d3883b8ee144f0bd1a8f944"
    )
    exceptional = records(preset, "exceptional")
    assert len(exceptional) == len({r["outcome"] for r in exceptional}) == 11
    assert all(r["fault_count"] == 1 for r in exceptional)
    assert len(records(preset, "standard")) == 32


@pytest.mark.parametrize("preset", ["minimal", "mainnet"])
def test_profiles_and_python_reference_on_legacy_validated_rows(preset):
    bound = target(preset)
    reference = TARGET.for_spec(spec_targets[preset]["gloas"], backend="python")
    # Full Python Cartesian enumeration is prohibitive. Feasibility is checked
    # independently against legacy fingerprints above; compare the reference
    # projections and completion over that exhaustively validated finite space.
    reference._cache[True] = (
        reference.definition.model(reference.bound_constants),
        bound._configurations(filtered=True)[1],
    )
    for name, formula in bound.profiles.items():
        selected = records(preset, name)
        observations = [{k: v for k, v in r.items() if v != "NA"} for r in selected]
        expected = reference.profiles[name]
        assert formula.run() == expected.run()
        assert formula.generation_obligations() == expected.generation_obligations()
        assert profile_records(reference, name) == selected
        result = score(bound, observations, formula, name)
        assert result.covered == result.total
        assert not result.unexpected
        assert not result.outcome_mismatches


@pytest.mark.parametrize("preset", ["minimal", "mainnet"])
@pytest.mark.parametrize("seed", [7, 124])
def test_numeric_balance_witnesses_for_every_signature(preset, seed):
    minimum = int(spec_targets[preset]["gloas"].MIN_DEPOSIT_AMOUNT)
    rng = Random(seed)

    def cmp(a, b):
        return "LT" if a < b else "GT" if a > b else "EQ"

    for r in records(preset, "max"):
        if r["builder_type"] == "SELF":
            continue
        pending = rng.randrange(1, 1001) * (
            int(r["has_pending_payments"]) + int(r["has_pending_withdrawals"])
        )
        balance, value = _pick_balance_and_bid_value(
            r["cmp_balance_zero"],
            r["cmp_balance_min_deposit"],
            r["cmp_bid_value_zero"],
            r["cmp_builder_balance_to_bid_value_plus_min_balance"],
            minimum,
            pending,
            rng,
        )
        assert cmp(balance, 0) == r["cmp_balance_zero"]
        assert cmp(balance, minimum) == r["cmp_balance_min_deposit"]
        assert cmp(value, 0) == r["cmp_bid_value_zero"]
        assert (
            cmp(balance, value + minimum + pending)
            == r["cmp_builder_balance_to_bid_value_plus_min_balance"]
        )


@lru_cache
def materializer(preset):
    m = MATERIALIZER(spec_targets[preset]["gloas"], preset_name=preset, seed=124)
    m.test_provider = "bid_processing"
    return m


def vector(preset, record):
    m = materializer(preset)
    spec = m.spec
    solution = SimpleNamespace(**record)
    m.rng = m._rng_for_solution(solution)
    metadata, parts = m.materialize_solution(solution)
    encoded = {name: data for name, _, data in parts}
    return metadata, Context(
        spec,
        spec.BeaconState.decode_bytes(encoded["pre"]),
        spec.SignedExecutionPayloadBid.decode_bytes(encoded["execution_payload_bid"]),
        spec.BeaconState.decode_bytes(encoded["post"]) if "post" in encoded else None,
        {},
    )


def test_exit_payload_carries_expected_withdrawals(monkeypatch):
    spec = spec_targets["minimal"]["gloas"]
    m = MATERIALIZER(spec)
    base = m._base
    assert not base.payload_expected_withdrawals
    assert spec.get_expected_withdrawals(base).withdrawals

    verify_envelope = spec.verify_execution_payload_envelope
    verified_block_hashes = []

    def verify_exit_envelope(state, signed_envelope, engine):
        envelope = signed_envelope.message
        assert envelope.execution_requests.builder_exits
        assert envelope.payload.block_hash == compute_el_block_hash(
            spec, envelope.payload, base, envelope.execution_requests
        )
        verify_envelope(state, signed_envelope, engine)
        verified_block_hashes.append(envelope.payload.block_hash)

    monkeypatch.setattr(spec, "verify_execution_payload_envelope", verify_exit_envelope)
    exited_bases = m._exited_bases
    (block_hash,) = verified_block_hashes
    assert all(state.latest_block_hash == block_hash for state in exited_bases.values())


@pytest.mark.parametrize("preset", ["minimal", "mainnet"])
def test_standard_and_builder_state_witnesses_survive_serialization(preset, monkeypatch):
    # Cover every standard witness, every builder state, and all self-build
    # signatures, without serializing the same large mainnet state for every row.
    monkeypatch.setattr(bls, "bls_active", False)
    selected = {tuple(sorted(r.items())): r for r in records(preset, "standard")}
    states = set()
    for r in records(preset, "max"):
        state = tuple((f.name, r[f.name]) for a in INPUT_ASPECTS[7:] for f in a.declarations)
        if r["builder_type"] == "SELF" or state not in states:
            selected[tuple(sorted(r.items()))] = r
            states.add(state)
    assert len(states) == 25  # 24 external builder states plus the inactive self state.
    for r in selected.values():
        metadata, ctx = vector(preset, r)
        assert recover_record(TARGET, ctx)[2] == metadata["claimed"] == r
        assert (ctx.post is not None) == (r["outcome"] == "ACCEPT")
        assert ctx.operation.message.block_hash != ctx.operation.message.parent_block_hash
        assert not list(state_invariant_violations(ctx.spec, ctx.pre))
        spec, pre = ctx.spec, ctx.pre
        checkpoint = pre.finalized_checkpoint
        if r["cmp_state_epoch_deposit_epoch"] == r["cmp_finalized_epoch_deposit_epoch"] == "EQ":
            assert spec.get_current_epoch(pre) == spec.GENESIS_EPOCH
            assert checkpoint == spec.Checkpoint()
            assert pre.builders[ctx.operation.message.builder_index].withdrawable_epoch == (
                spec.FAR_FUTURE_EPOCH
            )
        else:
            assert checkpoint.epoch > spec.GENESIS_EPOCH
            assert checkpoint.root == spec.get_block_root(pre, checkpoint.epoch)
        if r["withdrawable_epoch_set"] is True:
            builder = pre.builders[ctx.operation.message.builder_index]
            # The block that processed the exit is still the latest block.
            exit_epoch = spec.compute_epoch_at_slot(pre.latest_block_header.slot)
            assert builder.deposit_epoch < checkpoint.epoch <= exit_epoch
            assert builder.withdrawable_epoch == (
                exit_epoch + spec.config.MIN_BUILDER_WITHDRAWABILITY_DELAY
            )
        assert bls.bls_active is False


@pytest.mark.parametrize("preset", ["minimal", "mainnet"])
def test_smoke_pipeline_validation_loading_and_replay(preset, tmp_path):
    assert (
        materialize_handler("execution_payload_bid", "smoke", tmp_path, preset_name=preset, seed=7)
        == 12
    )
    bound = target(preset)
    observations = load_observations([tmp_path], bound, preset)
    result = score(bound, [bound.record(o) for o in observations], bound.profiles["smoke"], "smoke")
    assert result.covered == result.total == 12
    assert not result.unexpected
    for case in gather_tests(tmp_path):
        run_test(case)
    case = next(tmp_path.rglob("case_*"))
    spec = spec_targets[preset]["gloas"]
    assert all(c.status == "ok" for c in validate_case.for_spec(spec, case))
    yaml = YAML()
    path = case / "dimensions.yaml"
    metadata = yaml.load(path.read_text())
    metadata["claimed"]["outcome"] = "TAMPERED"
    with path.open("w") as stream:
        yaml.dump(metadata, stream)
    assert any(
        c.dimension == "outcome" and c.status == "mismatch"
        for c in validate_case.for_spec(spec, case)
    )


def test_signature_observation_uses_real_bls_without_claims(monkeypatch):
    r = next(r for r in records("minimal", "normal") if r["builder_type"] == "EXTERNAL")
    _, ctx = vector("minimal", r)
    ctx.operation.signature = ctx.spec.BLSSignature(b"\x00" * 96)
    monkeypatch.setattr(bls, "bls_active", False)
    observed = target("minimal").record(target("minimal").observation(ctx))
    assert observed["bid_signature"] == "INVALID"
    assert observed["outcome"] == "REJECT_BAD_SIGNATURE"
    assert observed["fault_count"] == 1
    assert bls.bls_active is False
