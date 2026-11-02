"""Decode and replay operations, epoch processing, and sanity vectors."""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING

from eth_consensus_specs.test.context import expect_assertion_error
from eth_consensus_specs.test.helpers.forks import is_post_gloas
from eth_consensus_specs.test.helpers.specs import spec_targets
from eth_consensus_specs.utils import bls

from .formats import OPERATION_INPUTS
from .io import read_ssz_snappy, read_yaml

if TYPE_CHECKING:
    from .discovery import VectorCase

OPERATION_PROCESSORS = {
    "attestation": "process_attestation",
    "block_header": "process_block_header",
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
    "proposer_lookahead": "process_proposer_lookahead",
}


def decode_file(spec, test_dir: Path, name: str, typ):
    return typ.decode_bytes(read_ssz_snappy(test_dir / f"{name}.ssz_snappy"))


def get_test_case(spec, test_dir: Path, handler: str):
    return {
        "meta": read_yaml(test_dir / "meta.yaml"),
        "pre": decode_file(spec, test_dir, "pre", spec.BeaconState),
        "operation": decode_optional_operation(spec, test_dir, handler),
        "blocks": decode_blocks(spec, test_dir),
        "slots": read_yaml(test_dir / "slots.yaml") if (test_dir / "slots.yaml").exists() else None,
        "post": decode_optional_post(spec, test_dir),
    }


def decode_blocks(spec, test_dir: Path):
    meta = read_yaml(test_dir / "meta.yaml")
    return [
        decode_file(spec, test_dir, f"blocks_{index}", spec.SignedBeaconBlock)
        for index in range(meta.get("blocks_count", 0))
    ]


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


def run_test(test_info: VectorCase):
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

        if runner == "sanity":
            if handler == "blocks":
                run_sanity_blocks_case(spec, state, test_case["blocks"], expected_post)
                return
            if handler == "slots":
                run_sanity_slots_case(spec, state, test_case["slots"], expected_post)
                return
            raise ValueError(f"Unsupported sanity handler: {handler}")

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


def run_sanity_blocks_case(spec, state, blocks, expected_post):
    def run_blocks():
        for block in blocks:
            spec.state_transition(state, block, validate_result=False)

    if expected_post is None:
        expect_assertion_error(run_blocks)
    else:
        run_blocks()
        assert state.hash_tree_root() == expected_post.hash_tree_root()


def run_sanity_slots_case(spec, state, slots, expected_post):
    if slots is None:
        raise ValueError("sanity/slots case is missing slots.yaml")
    run_processing_case(
        spec.process_slots,
        state,
        spec.Slot(int(state.slot) + int(slots)),
        expected_post,
    )


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
