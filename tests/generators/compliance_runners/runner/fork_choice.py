"""Decode and replay fork-choice event vectors."""

import contextlib
from pathlib import Path

from eth_utils import decode_hex, encode_hex

from eth_consensus_specs.test.context import (
    expect_assertion_error,
    get_copy_of_spec,
    spec_with_config_overrides,
)
from eth_consensus_specs.test.helpers.fork_choice import get_viable_for_head_checks
from eth_consensus_specs.test.helpers.forks import is_post_gloas
from eth_consensus_specs.test.helpers.specs import spec_targets
from eth_consensus_specs.utils import bls
from eth_consensus_specs.utils.kzg import load_trusted_setup

from .io import read_meta, read_ssz_snappy, read_yaml
from .payload_attestation import payload_attestation_to_messages


def get_test_case(spec, td):
    def get_prefix(p):
        return p.stem

    td_path = Path(td)
    return (
        read_meta(td_path / "meta.yaml"),
        spec.BeaconBlock.decode_bytes(read_ssz_snappy(td_path / "anchor_block.ssz_snappy")),
        spec.BeaconState.decode_bytes(read_ssz_snappy(td_path / "anchor_state.ssz_snappy")),
        {
            get_prefix(b): spec.SignedBeaconBlock.decode_bytes(read_ssz_snappy(b))
            for b in td_path.glob("block_*.ssz_snappy")
        },
        {
            get_prefix(b): spec.Attestation.decode_bytes(read_ssz_snappy(b))
            for b in td_path.glob("attestation_*.ssz_snappy")
        },
        {
            get_prefix(b): spec.AttesterSlashing.decode_bytes(read_ssz_snappy(b))
            for b in td_path.glob("attester_slashing_*.ssz_snappy")
        },
        {
            get_prefix(e): spec.SignedExecutionPayloadEnvelope.decode_bytes(read_ssz_snappy(e))
            for e in td_path.glob("execution_payload_envelope_*.ssz_snappy")
        },
        {
            get_prefix(b): spec.PayloadAttestationMessage.decode_bytes(read_ssz_snappy(b))
            for b in td_path.glob("payload_attestation_message_*.ssz_snappy")
        },
        read_yaml(td_path / "steps.yaml"),
    )


def run_test(test_info):
    preset, fork, test_dir = test_info.preset, test_info.fork, test_info.test_dir
    load_trusted_setup()
    spec = spec_targets[preset][fork]
    if is_post_gloas(spec):
        spec, _ = spec_with_config_overrides(get_copy_of_spec(spec), {"GLOAS_FORK_EPOCH": 0})
    meta, anchor_block, anchor_state, blocks, atts, slashings, envelopes, payload_atts, steps = (
        get_test_case(spec, test_dir)
    )
    old_bls_active = bls.bls_active
    bls.bls_active = meta.get("bls_setting", 0) == 1
    try:
        store = spec.get_forkchoice_store(anchor_state, anchor_block)
        for step in steps:
            if "tick" in step:
                time_ms = spec.seconds_to_milliseconds(step["tick"])
                spec.on_tick(store, time_ms)
            elif "block" in step:
                block_id = step["block"]
                valid = step.get("valid", True)
                signed_block = blocks[block_id]
                if valid:
                    spec.on_block(store, signed_block)
                    for block_att in signed_block.message.body.attestations:
                        with contextlib.suppress(AssertionError):
                            spec.on_attestation(store, block_att, is_from_block=True)
                    for block_att_slashing in signed_block.message.body.attester_slashings:
                        with contextlib.suppress(AssertionError):
                            spec.on_attester_slashing(store, block_att_slashing)
                    if is_post_gloas(spec):
                        state = store.block_states[signed_block.message.hash_tree_root()]
                        for payload_attestation in signed_block.message.body.payload_attestations:
                            for ptc_message in payload_attestation_to_messages(
                                spec, state, payload_attestation
                            ):
                                with contextlib.suppress(AssertionError):
                                    spec.on_payload_attestation_message(
                                        store, ptc_message, is_from_block=True
                                    )
                else:
                    expect_assertion_error(lambda sb=signed_block: spec.on_block(store, sb))
            elif "attestation" in step:
                att_id = step["attestation"]
                valid = step.get("valid", True)
                attestation = atts[att_id]
                if valid:
                    spec.on_attestation(store, attestation, is_from_block=False)
                else:
                    expect_assertion_error(
                        lambda att=attestation: spec.on_attestation(store, att, is_from_block=False)
                    )
            elif "attester_slashing" in step:
                slashing_id = step["attester_slashing"]
                valid = step.get("valid", True)
                assert valid
                slashing = slashings[slashing_id]
                spec.on_attester_slashing(store, slashing)
            elif "execution_payload" in step:
                envelope_id = step["execution_payload"]
                valid = step.get("valid", True)
                signed_envelope = envelopes[envelope_id]
                if valid:
                    spec.on_execution_payload_envelope(store, signed_envelope)
                else:
                    expect_assertion_error(
                        lambda se=signed_envelope: spec.on_execution_payload_envelope(store, se)
                    )
            elif "payload_attestation_message" in step:
                ptc_message_id = step["payload_attestation_message"]
                valid = step.get("valid", True)
                ptc_message = payload_atts[ptc_message_id]
                if valid:
                    spec.on_payload_attestation_message(store, ptc_message, is_from_block=False)
                else:
                    expect_assertion_error(
                        lambda msg=ptc_message: spec.on_payload_attestation_message(
                            store, msg, is_from_block=False
                        )
                    )
            elif "checks" in step:
                checks = step["checks"]
                for check, value in checks.items():
                    if check == "time":
                        expected_time = value
                        assert spec.milliseconds_to_seconds(store.time_ms) == expected_time
                    elif check == "head":
                        head = spec.get_head(store)
                        assert store.blocks[head.root].slot == value["slot"]
                        assert encode_hex(head.root) == value["root"]
                        if is_post_gloas(spec):
                            assert head.payload_status == value["payload_status"]
                    elif check == "proposer_boost_root":
                        assert encode_hex(store.proposer_boost_root) == value
                    elif check == "justified_checkpoint":
                        checkpoint = store.justified_checkpoint
                        assert checkpoint.epoch == value["epoch"]
                        assert encode_hex(checkpoint.root) == value["root"]
                    elif check == "finalized_checkpoint":
                        checkpoint = store.finalized_checkpoint
                        assert checkpoint.epoch == value["epoch"]
                        assert encode_hex(checkpoint.root) == value["root"]
                    elif check == "viable_for_head_roots_and_weights":
                        actual = value
                        expected = get_viable_for_head_checks(spec, store)
                        assert {frozenset(e.items()) for e in actual} == {
                            frozenset(e.items()) for e in expected
                        }
                    elif check in ("payload_timeliness_vote", "payload_data_availability_vote"):
                        target_root = spec.Root(decode_hex(value["block_root"]))
                        assert list(getattr(store, check)[target_root]) == value["votes"]
                    else:
                        raise AssertionError
            else:
                raise AssertionError

    finally:
        bls.bls_active = old_bls_active
