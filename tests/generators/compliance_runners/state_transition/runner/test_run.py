from __future__ import annotations

from pathlib import Path
from typing import NamedTuple

import pytest
from ruamel.yaml import YAML
from snappy import uncompress

from eth_consensus_specs.test.context import expect_assertion_error
from eth_consensus_specs.test.helpers.forks import is_post_gloas
from eth_consensus_specs.test.helpers.specs import spec_targets
from eth_consensus_specs.utils import bls

OPERATION_INPUTS = {
    "attestation": ("attestation", "Attestation"),
    "builder_deposit_request": ("builder_deposit_request", "BuilderDepositRequest"),
    "builder_exit_request": ("builder_exit_request", "BuilderExitRequest"),
    "consolidation_request": ("consolidation_request", "ConsolidationRequest"),
    "deposit_request": ("deposit_request", "DepositRequest"),
    "execution_payload_bid": ("execution_payload_bid", "SignedExecutionPayloadBid"),
    "parent_execution_payload": ("block", "BeaconBlock"),
    "payload_attestation": ("payload_attestation", "PayloadAttestation"),
    "proposer_slashing": ("proposer_slashing", "ProposerSlashing"),
    "attester_slashing": ("attester_slashing", "AttesterSlashing"),
    "deposit": ("deposit", "Deposit"),
    "bls_to_execution_change": ("address_change", "SignedBLSToExecutionChange"),
    "voluntary_exit": ("voluntary_exit", "SignedVoluntaryExit"),
    "withdrawal_request": ("withdrawal_request", "WithdrawalRequest"),
    "sync_aggregate": ("sync_aggregate", "SyncAggregate"),
}

OPERATION_PROCESSORS = {
    "attestation": "process_attestation",
    "builder_deposit_request": "process_builder_deposit_request",
    "builder_exit_request": "process_builder_exit_request",
    "consolidation_request": "process_consolidation_request",
    "deposit_request": "process_deposit_request",
    "execution_payload_bid": "process_execution_payload_bid",
    "parent_execution_payload": "process_parent_execution_payload",
    "payload_attestation": "process_payload_attestation",
    "proposer_slashing": "process_proposer_slashing",
    "attester_slashing": "process_attester_slashing",
    "deposit": "process_deposit",
    "bls_to_execution_change": "process_bls_to_execution_change",
    "voluntary_exit": "process_voluntary_exit",
    "withdrawal_request": "process_withdrawal_request",
    "sync_aggregate": "process_sync_aggregate",
    "withdrawals": "process_withdrawals",
}

EPOCH_PROCESSORS = {
    "builder_pending_payments": "process_builder_pending_payments",
    "justification_and_finalization": "process_justification_and_finalization",
    "registry_updates": "process_registry_updates",
    "slashings": "process_slashings",
    "pending_deposits": "process_pending_deposits",
    "ptc_window": "process_ptc_window",
    "pending_consolidations": "process_pending_consolidations",
    "effective_balance_updates": "process_effective_balance_updates",
    "inactivity_updates": "process_inactivity_updates",
    "rewards_and_penalties": "process_rewards_and_penalties",
    "participation_flag_updates": "process_participation_flag_updates",
    "slashings_reset": "process_slashings_reset",
    "randao_mixes_reset": "process_randao_mixes_reset",
    "eth1_data_reset": "process_eth1_data_reset",
    "historical_summaries_update": "process_historical_summaries_update",
    "sync_committee_updates": "process_sync_committee_updates",
}


class StateTransitionTestInfo(NamedTuple):
    preset: str
    fork: str
    runner: str
    handler: str
    suite: str
    test_dir: Path


def read_yaml(path: Path):
    yaml = YAML(typ="safe")
    return yaml.load(path.read_text())


def read_ssz_snappy(path: Path) -> bytes:
    return uncompress(path.read_bytes())


def decode_file(spec, test_dir: Path, name: str, typ):
    return typ.decode_bytes(read_ssz_snappy(test_dir / f"{name}.ssz_snappy"))


def get_test_case(spec, test_dir: Path, handler: str):
    return {
        "meta": read_yaml(test_dir / "meta.yaml"),
        "pre": decode_file(spec, test_dir, "pre", spec.BeaconState),
        "operation": decode_optional_operation(spec, test_dir, handler),
        "post": decode_optional_post(spec, test_dir),
    }


def decode_optional_operation(spec, test_dir: Path, handler: str):
    input_name = OPERATION_INPUTS.get(handler, (handler, None))[0]
    if not (test_dir / f"{input_name}.ssz_snappy").exists():
        return None
    return decode_operation(spec, test_dir, handler)


def decode_operation(spec, test_dir: Path, handler: str):
    if handler in OPERATION_INPUTS:
        input_name, type_name = OPERATION_INPUTS[handler]
        return decode_file(spec, test_dir, input_name, getattr(spec, type_name))
    raise ValueError(f"Unsupported operations handler: {handler}")


def decode_optional_post(spec, test_dir: Path):
    post_path = test_dir / "post.ssz_snappy"
    if not post_path.exists():
        return None
    return spec.BeaconState.decode_bytes(read_ssz_snappy(post_path))


def run_test(test_info: StateTransitionTestInfo):
    preset, fork, runner, handler, _, test_dir = test_info
    spec = spec_targets[preset][fork]

    test_case = get_test_case(spec, Path(test_dir), handler)
    state = test_case["pre"]
    expected_post = test_case["post"]
    old_bls_active = bls.bls_active
    bls.bls_active = bool(test_case["meta"].get("bls_setting", 0))

    try:
        if runner == "epoch_processing":
            run_epoch_processing_case(spec, state, handler, expected_post)
            return

        if runner != "operations":
            raise ValueError(f"Unsupported state-transition runner: {runner}")

        if handler in OPERATION_PROCESSORS:
            process_fn = getattr(spec, OPERATION_PROCESSORS[handler])
            extra_args = ()
            if handler == "attestation" and is_post_gloas(spec):
                extra_args = (spec.Slot(test_case["meta"]["parent_slot"]),)
            run_processing_case(
                process_fn,
                state,
                test_case["operation"],
                expected_post,
                extra_args,
            )
            return

        raise ValueError(f"Unsupported operations handler: {handler}")
    finally:
        bls.bls_active = old_bls_active


def run_epoch_processing_case(spec, state, handler, expected_post):
    if handler not in EPOCH_PROCESSORS:
        raise ValueError(f"Unsupported epoch_processing handler: {handler}")
    process_fn = getattr(spec, EPOCH_PROCESSORS[handler])
    run_processing_case(process_fn, state, None, expected_post)


def run_processing_case(process_fn, state, operation, expected_post, extra_args=()):
    def run_processing():
        if operation is None:
            process_fn(state, *extra_args)
        else:
            process_fn(state, operation, *extra_args)

    if expected_post is None:
        expect_assertion_error(run_processing)
        return

    run_processing()
    assert state == expected_post


def gather_tests(tests_dir):
    if isinstance(tests_dir, (list, tuple)):
        for path in tests_dir:
            yield from gather_tests(path)
        return

    tests_path = Path(tests_dir)
    reftests_dirs = (
        [tests_path]
        if any(path.name in spec_targets for path in tests_path.glob("*"))
        else sorted(tests_path.glob("*/reftests"))
    )
    for reftests_dir in reftests_dirs:
        for preset in [p.name for p in reftests_dir.glob("*") if p.name in spec_targets]:
            for fork in [
                f.name for f in (reftests_dir / preset).glob("*") if f.name in spec_targets[preset]
            ]:
                for test_dir in sorted((reftests_dir / preset / fork).glob("*/*/*/*")):
                    manifest_path = test_dir / "manifest.yaml"
                    if not manifest_path.exists():
                        continue
                    manifest = read_yaml(manifest_path)
                    yield StateTransitionTestInfo(
                        preset,
                        fork,
                        manifest["runner"],
                        manifest["handler"],
                        manifest["suite"],
                        test_dir,
                    )


def select_tests(tests, start=None, limit=None):
    if start is not None:
        tests = tests[start:]
    if limit is not None:
        tests = tests[:limit]
    return tests


def _test_id(test_info: StateTransitionTestInfo) -> str:
    return (
        f"{test_info.preset}::{test_info.fork}::{test_info.runner}::"
        f"{test_info.handler}::{test_info.suite}::{Path(test_info.test_dir).name}"
    )


def pytest_generate_tests(metafunc):
    if "test_info" not in metafunc.fixturenames:
        return

    tests_dir = metafunc.config.getoption("--test-dir")
    if tests_dir is None:
        raise pytest.UsageError(
            "--test-dir is required when running state-transition compliance tests"
        )

    start = metafunc.config.getoption("--start")
    limit = metafunc.config.getoption("--limit")
    test_infos = select_tests(list(gather_tests(tests_dir)), start=start, limit=limit)
    metafunc.parametrize(
        "test_info",
        test_infos,
        ids=[_test_id(test_info) for test_info in test_infos],
    )


def test_run_state_transition_case(test_info):
    run_test(test_info)
