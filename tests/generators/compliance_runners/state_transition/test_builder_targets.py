"""Check builder declaration coverage and the materialized fixtures."""

from random import Random
from types import SimpleNamespace

import pytest
from ruamel.yaml import YAML

from eth_consensus_specs.test.helpers.specs import spec_targets
from tests.generators.compliance_runners.state_transition.declaration_validation import (
    recover_record,
)
from tests.generators.compliance_runners.state_transition.evaluation.coverage_dsl import (
    Context,
    score,
)
from tests.generators.compliance_runners.state_transition.evaluation.invariant_scan import (
    entry_condition_violations,
    state_invariant_violations,
)
from tests.generators.compliance_runners.state_transition.materializer.common import (
    process_execution_requests_after_empty_parent,
)
from tests.generators.compliance_runners.state_transition.provider import load_provider, PROFILES


def test_builder_deposit_request_history_rejects_below_execution_minimum():
    spec = spec_targets["minimal"]["gloas"]
    module = load_provider("builder_deposit_request")
    pre = module.MATERIALIZER(spec)._first_slot_state.copy()
    for amount in (0, spec.MIN_DEPOSIT_AMOUNT - 1):
        request = spec.BuilderDepositRequest(amount=spec.Gwei(amount))
        requests = spec.ExecutionRequests(builder_deposits=spec.BuilderDepositRequests.of(request))
        with pytest.raises(AssertionError, match="execution-layer minimum"):
            process_execution_requests_after_empty_parent(spec, pre, requests)


@pytest.mark.parametrize("preset", ["minimal", "mainnet"])
@pytest.mark.parametrize(
    ("provider", "configuration_count"),
    [("builder_deposit_request", 306), ("builder_pending_payments", 240)],
)
def test_complete_builder_witnesses_match_vectors_and_cover_profiles(
    preset, provider, configuration_count
):
    module = load_provider(provider)
    spec = spec_targets[preset]["gloas"]
    target = module.TARGET.for_spec(spec)
    records = module.build_profile("max", spec=spec)
    assert len(records) == configuration_count
    materializer = module.MATERIALIZER(spec, preset_name=preset, seed=124)
    materializer.rng = Random(124)
    observed = []
    for record in records:
        meta, parts = materializer.materialize_solution(SimpleNamespace(**record))
        encoded = {name: data for name, _, data in parts}
        pre = spec.BeaconState.decode_bytes(encoded["pre"])
        post = spec.BeaconState.decode_bytes(encoded["post"])
        operation = (
            spec.BuilderDepositRequest.decode_bytes(encoded[provider])
            if provider == "builder_deposit_request"
            else None
        )
        ctx = Context(spec, pre, operation, post, meta)
        actual = target.record(target.observation(ctx))
        # Metadata is the solver's assignment; observation must recover it
        # from the bytes without using metadata to choose a branch.
        assert recover_record(module.TARGET, ctx)[2] == meta["claimed"] == record
        assert not list(state_invariant_violations(spec, pre))
        assert not list(state_invariant_violations(spec, post))
        if provider == "builder_deposit_request":
            if record["reset_applies"] or record["reuses_swept_slot"] is True:
                swept = pre.builders[0]
                assert swept.balance == 0
                assert any(
                    w.validator_index == spec.convert_builder_index_to_validator_index(0)
                    and w.address == swept.execution_address
                    and w.amount > 0
                    for w in pre.payload_expected_withdrawals
                )
            if record["outcome"] == "TOPPED_UP_AFTER_RESET":
                assert post.builders[0].withdrawable_epoch == (
                    spec.get_current_epoch(pre) + spec.config.MIN_BUILDER_WITHDRAWABILITY_DELAY
                )
                assert post.builders[0].balance == operation.amount
            if record["reuses_swept_slot"] is True:
                assert len(post.builders) == len(pre.builders)
                assert post.builders[0].pubkey == operation.pubkey != swept.pubkey
                assert post.builders[0].balance == operation.amount
        else:
            assert not list(entry_condition_violations(spec, pre, "epoch_processing"))
            slots = spec.SLOTS_PER_EPOCH
            quorum = spec.get_builder_payment_quorum_threshold(pre)
            empty = spec.BuilderPendingPayment.empty()
            previous = list(pre.builder_pending_payments[:slots])
            retained = list(pre.builder_pending_payments[slots:])
            assert all(
                payment.withdrawal.amount > 0
                for payment in pre.builder_pending_payments
                if payment != empty
            )
            assert retained[-1].weight == 0
            if record["next_epoch_payments_occupancy"] != "EMPTY":
                assert any(p.weight > quorum for p in retained)
            if record["next_epoch_payments_occupancy"] == "MULTIPLE":
                occupied = [i for i, p in enumerate(retained) if p != empty]
                assert occupied[-1] - occupied[0] + 1 > len(occupied)
            appended = [p.withdrawal for p in previous if p.weight >= quorum]
            if (
                record["previous_epoch_occupancy"] == "FULL"
                and record["qualifying_payment_count"] == "MANY"
            ):
                assert previous[-1].weight >= quorum
            if (
                record["previous_epoch_occupancy"] == "MULTIPLE"
                and record["mixed_quorum_relations"]
            ):
                assert any(p.weight >= quorum for p in previous[previous.index(empty) + 1 :])
                assert len({w.builder_index for w in appended}) >= 2
                assert len({w.fee_recipient for w in appended}) >= 2
                assert all(
                    w.fee_recipient != pre.builders[w.builder_index].execution_address
                    for w in appended
                )
            assert list(post.builder_pending_withdrawals) == [
                *pre.builder_pending_withdrawals,
                *appended,
            ]
            assert list(post.builder_pending_payments[:slots]) == retained
            assert all(payment == empty for payment in post.builder_pending_payments[slots:])
        observed.append(actual)
    for profile in PROFILES:
        representatives = module.build_profile(profile, spec=spec)
        if profile == "exceptional" and provider == "builder_pending_payments":
            assert representatives == []
            continue
        report = score(
            target,
            [{k: v for k, v in r.items() if v != "NA"} for r in representatives],
            target.profiles[profile],
        )
        assert report.covered == report.total
        assert not report.unexpected
        report = score(target, observed, target.profiles[profile])
        assert report.covered == report.total
        # Other profiles deliberately include witnesses outside this scope.
        if profile in ("smoke", "standard", "max"):
            assert not report.unexpected


@pytest.mark.parametrize("provider", ["builder_deposit_request", "builder_pending_payments"])
def test_case_validator_rejects_missing_post_and_changed_claim(provider, tmp_path):
    module = load_provider(provider)
    spec = spec_targets["minimal"]["gloas"]
    records = module.build_profile("smoke", spec=spec)
    materializer = module.MATERIALIZER(spec, seed=7)
    materializer.test_provider = provider
    materializer.materialize_reps(tmp_path, [SimpleNamespace(**records[0])])
    case = next(tmp_path.rglob("case_*"))
    assert all(c.status == "ok" for c in module.validate_case(case))
    (case / "post.ssz_snappy").unlink()
    assert any(
        c.dimension == "post_state_present" and c.status == "mismatch"
        for c in module.validate_case(case)
    )
    yaml = YAML()
    path = case / "dimensions.yaml"
    metadata = yaml.load(path.read_text())
    metadata["claimed"]["outcome"] = "INCORRECT"
    with path.open("w") as stream:
        yaml.dump(metadata, stream)
    assert any(
        c.dimension == "outcome" and c.status == "mismatch" for c in module.validate_case(case)
    )
