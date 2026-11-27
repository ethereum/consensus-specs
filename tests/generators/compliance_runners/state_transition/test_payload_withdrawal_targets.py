"""Parent-payload and pending-withdrawal declarations survive concrete serialization."""

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
from tests.generators.compliance_runners.state_transition.evaluation.invariant_scan import (
    state_invariant_violations,
)
from tests.generators.compliance_runners.state_transition.provider import (
    decode,
    load_provider,
    materialize_handler,
)

aggregate_provider = load_provider("withdrawal_processing")

MODULES = {
    "parent_execution_payload": "parent_execution_payload",
    "builder_pending_withdrawal_processing": "builder_pending_withdrawal_processing",
}


def provider_module(provider):
    return load_provider(MODULES[provider])


def vector(module, spec, materializer, record):
    solution = SimpleNamespace(**record)
    materializer.rng = materializer._rng_for_solution(solution)
    meta, parts = materializer.materialize_solution(solution)
    encoded = {name: data for name, _, data in parts}
    ctx = Context(
        spec,
        spec.BeaconState.decode_bytes(encoded["pre"]),
        spec.BeaconBlock.decode_bytes(encoded["block"])
        if module.TARGET.name == "parent_execution_payload"
        else None,
        spec.BeaconState.decode_bytes(encoded["post"]) if "post" in encoded else None,
        {},
    )
    return meta, ctx


def assert_pending_withdrawal_history(ctx, record):
    spec, pre, post = ctx.spec, ctx.pre, ctx.post
    assert not list(state_invariant_violations(spec, pre))
    assert not list(state_invariant_violations(spec, post))
    (withdrawal,) = pre.builder_pending_withdrawals
    index = withdrawal.builder_index
    parent_bid = pre.latest_execution_payload_bid
    assert spec.is_active_builder(pre, index)
    assert pre.latest_block_header.slot == pre.slot > parent_bid.slot
    assert pre.execution_payload_availability[parent_bid.slot % spec.SLOTS_PER_HISTORICAL_ROOT]
    assert index == parent_bid.builder_index != 0
    assert withdrawal.amount == parent_bid.value
    assert withdrawal.fee_recipient == parent_bid.fee_recipient != spec.ExecutionAddress()
    assert withdrawal.fee_recipient != pre.builders[index].execution_address

    reserved = spec.get_pending_balance_to_withdraw_for_builder(post, index)
    assert bool(reserved) == record["has_pending_payments"]
    assert post.builder_pending_payments == pre.builder_pending_payments
    assert pre.builders[index].balance == spec.MIN_DEPOSIT_AMOUNT + reserved + withdrawal.amount
    assert post.builders[index].balance == spec.MIN_DEPOSIT_AMOUNT + reserved
    assert list(post.payload_expected_withdrawals) == [
        spec.Withdrawal(
            index=pre.next_withdrawal_index,
            validator_index=spec.convert_builder_index_to_validator_index(index),
            address=withdrawal.fee_recipient,
            amount=withdrawal.amount,
        )
    ]


@pytest.mark.parametrize("preset", ["minimal", "mainnet"])
@pytest.mark.parametrize(
    ("provider", "count"),
    [("parent_execution_payload", 768), ("builder_pending_withdrawal_processing", 2)],
)
def test_max_vectors_and_profile_coverage(preset, provider, count):
    module = provider_module(provider)
    spec = spec_targets[preset]["gloas"]
    target = module.TARGET.for_spec(spec, backend="minizinc")
    records = module.build_profile("max", spec=spec)
    assert len(records) == count
    materializer = module.MATERIALIZER(spec, preset_name=preset, seed=124)
    materializer.test_provider = provider
    observed = []
    for record in records:
        meta, ctx = vector(module, spec, materializer, record)
        _, observation, actual = recover_record(module.TARGET, ctx)
        assert actual == meta["claimed"] == record
        if provider == "builder_pending_withdrawal_processing":
            assert_pending_withdrawal_history(ctx, record)
        observed.append(observation)
    for name, formula in target.profiles.items():
        selected = module.build_profile(name, spec=spec)
        for observations in (selected, observed):
            assert formula.covered(observations) == formula.run()
            assert all(target.feasible(r) for r in observations)
        if provider == "parent_execution_payload" and name in ("normal", "exceptional"):
            for record in selected:
                faults = (
                    int(not record["requests_empty"] and not record["parent_payload_revealed"])
                    + int(record["parent_payload_revealed"] and not record["requests_root_matches"])
                    + sum(
                        not record[f"{field}_within_cap"]
                        for field in (
                            "withdrawals",
                            "consolidations",
                            "builder_deposits",
                            "builder_exits",
                        )
                    )
                )
                assert faults == (0 if name == "normal" else 1)


@pytest.mark.parametrize("preset", ["minimal", "mainnet"])
def test_parent_payload_smoke_pipeline(preset, tmp_path):
    assert (
        materialize_handler(
            "parent_execution_payload", "smoke", tmp_path, preset_name=preset, seed=7
        )
        == 13
    )


@pytest.mark.parametrize("preset", ["minimal", "mainnet"])
def test_pending_provider_shares_withdrawals_pipeline(preset, tmp_path):
    # Also exercise the aggregate provider after the newly migrated provider,
    # including shared materialization, numbering, validation, and CLI selection.
    generated = materialize_handler("withdrawals", "smoke", tmp_path, preset_name=preset, seed=7)
    module = provider_module("builder_pending_withdrawal_processing")
    spec = spec_targets[preset]["gloas"]
    target = module.TARGET.for_spec(spec)
    records = module.build_profile("smoke", spec=spec)
    observations = load_observations([tmp_path], target, preset)
    assert len(observations) == len(records) < generated
    assert (
        target.profiles["smoke"].covered([target.record(o) for o in observations])
        == target.profiles["smoke"].run()
    )


def test_mainnet_aggregate_can_place_eligible_validator_outside_sweep(tmp_path):
    spec = spec_targets["mainnet"]["gloas"]
    records = aggregate_provider.build_profile("max", spec=spec)
    record = next(
        r
        for r in records
        if (
            r["validators_eligible_for_sweep_exist"]
            and not r["swept_validators_hit_limit"]
            and not r["partial_validator_sweep_withdrawal"]
        )
    )
    materializer = aggregate_provider.MATERIALIZER(spec, preset_name="mainnet", seed=7)
    materializer.test_provider = "withdrawal_processing"
    solution = SimpleNamespace(**record)
    materializer.materialize_reps(tmp_path, [solution])
    case = next(tmp_path.rglob("case_*"))
    pre = decode(case / "pre.ssz_snappy", spec.BeaconState)
    window = int(spec.MAX_VALIDATORS_PER_WITHDRAWALS_SWEEP)
    assert len(pre.validators) > window
    epoch = spec.get_current_epoch(pre)
    eligible = [
        i
        for i, v in enumerate(pre.validators)
        if spec.is_fully_withdrawable_validator(v, pre.balances[i], epoch)
        or spec.is_partially_withdrawable_validator(v, pre.balances[i])
    ]
    assert eligible == [window]
    # Verify the serialized case through the shared TARGET validator too.
    assert all(
        check.status == "ok" for check in aggregate_provider.validate_case.for_spec(spec, case)
    )


@pytest.mark.parametrize(
    ("provider", "effect"),
    [
        ("parent_execution_payload", "state_effected"),
        ("parent_execution_payload", "payment_withdrawal_appended"),
        ("parent_execution_payload", "payment_slot_cleared"),
        ("builder_pending_withdrawal_processing", "withdrawal_balance_applied"),
        ("builder_pending_withdrawal_processing", "pending_withdrawal_consumed"),
    ],
)
def test_effects_are_observed_from_the_post_state(provider, effect):
    module = provider_module(provider)
    spec = spec_targets["minimal"]["gloas"]
    record = next(r for r in module.build_profile("max", spec=spec) if r[effect])
    materializer = module.MATERIALIZER(spec, seed=7)
    materializer.test_provider = provider
    _, ctx = vector(module, spec, materializer, record)
    assert all(check.status == "ok" for check in validate_record(module.TARGET, ctx, record))
    if effect == "state_effected":
        ctx.post = ctx.pre.copy()
    elif effect == "payment_withdrawal_appended":
        ctx.post.builder_pending_withdrawals = ctx.pre.builder_pending_withdrawals.copy()
    elif effect == "payment_slot_cleared":
        ctx.post.builder_pending_payments = ctx.pre.builder_pending_payments.copy()
    elif effect == "withdrawal_balance_applied":
        index = ctx.pre.builder_pending_withdrawals[0].builder_index
        ctx.post.builders[index].balance = ctx.pre.builders[index].balance
    else:
        ctx.post.builder_pending_withdrawals = ctx.pre.builder_pending_withdrawals.copy()
    assert any(
        check.dimension == effect and check.status == "mismatch"
        for check in validate_record(module.TARGET, ctx, record)
    )
