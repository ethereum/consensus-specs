import json
from pathlib import Path

import pytest
import snappy

from eth_consensus_specs.gloas import minimal as spec
from eth_consensus_specs.test.helpers.block import apply_empty_block
from eth_consensus_specs.test.helpers.genesis import create_genesis_state

from .invariant_scan import entry_condition_violations, main, state_invariant_violations


@pytest.fixture
def state():
    return create_genesis_state(spec, [spec.MAX_EFFECTIVE_BALANCE] * 64, spec.MAX_EFFECTIVE_BALANCE)


def test_slot_checks_apply_at_the_handler_entry_point(state):
    assert not list(entry_condition_violations(spec, state, "sanity"))
    state.state_roots[0] = spec.Root(b"\x01" * 32)
    assert not list(state_invariant_violations(spec, state))
    assert list(entry_condition_violations(spec, state, "sanity")) == [
        "first_lap_destination_populated"
    ]
    assert list(entry_condition_violations(spec, state, "epoch_processing")) == [
        "epoch_handler_off_boundary",
        "epoch_slot_roots_missing",
    ]
    state.slot = spec.Slot(spec.SLOTS_PER_HISTORICAL_ROOT)
    assert not list(entry_condition_violations(spec, state, "sanity"))


@pytest.mark.parametrize("ring_offset", [0, spec.SLOTS_PER_HISTORICAL_ROOT])
def test_epoch_entry_requires_both_current_slot_roots(state, ring_offset):
    state.slot = spec.Slot(ring_offset + spec.SLOTS_PER_EPOCH - 1)
    spec.process_slot(state)
    assert not list(entry_condition_violations(spec, state, "epoch_processing"))
    index = state.slot % spec.SLOTS_PER_HISTORICAL_ROOT
    for roots in (state.state_roots, state.block_roots):
        original = roots[index]
        roots[index] = spec.Root()
        assert list(entry_condition_violations(spec, state, "epoch_processing")) == [
            "epoch_slot_roots_missing"
        ]
        roots[index] = original


def test_epoch_entry_detects_stale_block_root_after_ring_wraps(state):
    # Slot 7 caches the genesis header. A block at slot 8 changes the latest header.
    apply_empty_block(spec, state, spec.SLOTS_PER_EPOCH)
    index = spec.SLOTS_PER_EPOCH - 1
    spec.process_slots(state, spec.SLOTS_PER_HISTORICAL_ROOT + index)
    assert state.state_roots[index] != spec.Root()
    assert state.block_roots[index] != spec.Root()
    assert list(entry_condition_violations(spec, state, "epoch_processing")) == [
        "epoch_block_root_mismatch"
    ]

    spec.process_slot(state)
    assert not list(entry_condition_violations(spec, state, "epoch_processing"))


def test_registry_and_payment_invariants(state):
    state.inactivity_scores = type(state.inactivity_scores)()
    state.finalized_checkpoint.epoch = spec.Epoch(1)
    state.builders[0].deposit_epoch = spec.Epoch(1)
    validator = state.validators[0]
    validator.slashed = True
    validator.activation_eligibility_epoch = spec.Epoch(1)
    validator.withdrawable_epoch = spec.Epoch(0)
    validator.effective_balance = spec.Gwei(1)
    state.slashings[0] = spec.Gwei(1)
    state.builder_pending_payments[0].weight = spec.Gwei(1)
    state.builder_pending_withdrawals.append(
        spec.BuilderPendingWithdrawal(
            amount=spec.Gwei(1), builder_index=spec.BuilderIndex(len(state.builders))
        )
    )
    state.next_sync_committee.pubkeys[0] = spec.BLSPubkey()
    assert set(state_invariant_violations(spec, state)) == {
        "parallel_validator_list_lengths",
        "future_finalized_epoch",
        "finalized_ahead_of_justified",
        "future_builder_deposit",
        "slashed_without_exit",
        "eligible_after_activation",
        "withdrawable_before_exit",
        "fractional_effective_increment",
        "fractional_slashings_increment",
        "fractional_payment_weight",
        "positive_weight_without_bid",
        "missing_payment_builder",
        "unregistered_sync_pubkey",
    }


def test_pending_queues(state):
    for epoch in (4, 2):
        state.pending_partial_withdrawals.append(
            spec.PendingPartialWithdrawal(withdrawable_epoch=spec.Epoch(epoch))
        )
    for source in (0, 0, len(state.validators)):
        state.pending_consolidations.append(
            spec.PendingConsolidation(source_index=spec.ValidatorIndex(source))
        )
    assert set(state_invariant_violations(spec, state)) == {
        "partial_queue_unordered",
        "duplicate_consolidation_source",
        "queued_consolidation_without_exit",
    }


def test_cli_reports_all_cases_and_distinguishes_input_errors(tmp_path, state):
    suite = tmp_path / "minimal/gloas/epoch_processing/inactivity_updates/pyspec_tests"
    state.slot = spec.Slot(spec.SLOTS_PER_EPOCH - 1)
    spec.process_slot(state)
    for index, provider in enumerate(
        ("inactivity_updates_loop", "inactivity_updates", "inactivity_updates")
    ):
        case = suite / f"case_{index:04d}"
        case.mkdir(parents=True)
        (case / "dimensions.yaml").write_text(f"test_provider: {provider}\n")
        if index == 2:
            state.validators[0].slashed = True
        (case / "pre.ssz_snappy").write_bytes(snappy.compress(state.encode_bytes()))

    output = tmp_path / "report.json"
    args = ["--test-dir", str(tmp_path), "--json", str(output)]
    assert main([*args, "--provider", "inactivity_updates_loop"]) == 0
    assert main([*args, "--preset", "mainnet"]) == 2
    assert main(args) == 1
    report = json.loads(output.read_text())
    assert (report["scanned"], report["failed"]) == (3, 1)
    assert report["providers"]["minimal/inactivity_updates"] == {
        "scanned": 2,
        "failed": 1,
        "counts": {"slashed_without_exit": 1},
        "examples": {"slashed_without_exit": str((suite / "case_0002").relative_to(tmp_path))},
    }

    (suite / "case_0000/pre.ssz_snappy").write_bytes(b"bad data")
    assert main(args) == 2
    report = json.loads(output.read_text())
    assert (report["scanned"], report["failed"]) == (2, 1)
    assert set(report["errors"]) == {str((suite / "case_0000").relative_to(tmp_path))}


def test_cli_reports_unreadable_suite_alongside_clean_case(tmp_path, state, monkeypatch):
    suites = tmp_path / "minimal/gloas/epoch_processing"
    unreadable = suites / "justification_and_finalization/pyspec_tests"
    unreadable.mkdir(parents=True)
    iterdir = Path.iterdir

    def read_directory(path):
        if path == unreadable:
            raise PermissionError("suite is unreadable")
        return iterdir(path)

    monkeypatch.setattr(Path, "iterdir", read_directory)
    case = suites / "inactivity_updates/pyspec_tests/case_0000"
    case.mkdir(parents=True)
    state.slot = spec.Slot(spec.SLOTS_PER_EPOCH - 1)
    spec.process_slot(state)
    (case / "dimensions.yaml").write_text("test_provider: inactivity_updates\n")
    (case / "pre.ssz_snappy").write_bytes(snappy.compress(state.encode_bytes()))

    output = tmp_path / "report.json"
    assert main(["--test-dir", str(tmp_path), "--json", str(output)]) == 2
    report = json.loads(output.read_text())
    assert (report["scanned"], report["failed"]) == (1, 0)
    assert report["errors"] == {
        str(unreadable.relative_to(tmp_path)): "PermissionError: suite is unreadable"
    }
