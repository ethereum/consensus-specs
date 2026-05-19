import contextlib
from collections.abc import Iterable
from pathlib import Path
from typing import NamedTuple

import pytest
from eth_utils import decode_hex
from ruamel.yaml import YAML
from snappy import uncompress

from eth_consensus_specs.test.context import expect_assertion_error
from eth_consensus_specs.test.helpers.fork_choice import get_viable_for_head_checks
from eth_consensus_specs.test.helpers.forks import is_post_gloas
from eth_consensus_specs.test.helpers.specs import spec_targets
from tests.generators.compliance_runners.fork_choice.instantiators.helpers import (
    payload_attestation_to_messages,
)


def read_yaml(fp):
    with Path(fp).open() as f:
        yaml = YAML(typ="safe")
        return yaml.load(f.read())


def read_ssz_snappy(fp):
    with Path(fp).open("rb") as f:
        res = uncompress(f.read())
        return res


def get_test_case(spec, td):
    def get_prefix(p):
        return p.stem

    td_path = Path(td)
    return (
        read_yaml(td_path / "meta.yaml"),
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


class ComplianceTestInfo(NamedTuple):
    preset: str
    fork: str
    test_dir: Path


def run_test(test_info):
    preset, fork, test_dir = test_info
    spec = spec_targets[preset][fork]
    _, anchor_block, anchor_state, blocks, atts, slashings, envelopes, payload_atts, steps = (
        get_test_case(spec, test_dir)
    )
    store = spec.get_forkchoice_store(anchor_state, anchor_block)
    for step in steps:
        if "tick" in step:
            time = step["tick"]
            spec.on_tick(store, time)
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

            cached_head = None

            def get_head():
                nonlocal cached_head
                if cached_head is None:
                    cached_head = spec.get_head(store)
                return cached_head

            for check, value in checks.items():
                if check == "time":
                    expected_time = value
                    assert store.time == expected_time
                elif check == "head":
                    head = get_head()
                    head_root = head.root if hasattr(head, "root") else head
                    assert store.blocks[head_root].slot == value["slot"]
                    assert str(head_root) == value["root"]
                elif check == "proposer_boost_root":
                    assert str(store.proposer_boost_root) == str(value)
                elif check == "justified_checkpoint":
                    checkpoint = store.justified_checkpoint
                    assert checkpoint.epoch == value["epoch"]
                    assert str(checkpoint.root) == str(value["root"])
                elif check == "finalized_checkpoint":
                    checkpoint = store.finalized_checkpoint
                    assert checkpoint.epoch == value["epoch"]
                    assert str(checkpoint.root) == str(value["root"])
                elif check == "viable_for_head_roots_and_weights":
                    actual = value
                    expected = get_viable_for_head_checks(spec, store)
                    assert {frozenset(e) for e in actual} == {frozenset(e) for e in expected}
                elif check == "head_payload_status":
                    head = get_head()
                    assert head.payload_status == value
                elif check in ("payload_timeliness_vote", "payload_data_availability_vote"):
                    target_root = spec.Root(decode_hex(value["block_root"]))
                    assert list(getattr(store, check)[target_root]) == value["votes"]
                else:
                    raise AssertionError
        else:
            raise AssertionError


def gather_tests(tests_dir) -> Iterable[ComplianceTestInfo]:
    for preset in [p.name for p in Path(tests_dir).glob("*") if p.name in spec_targets]:
        for fork in [
            f.name for f in (Path(tests_dir) / preset).glob("*") if f.name in spec_targets[preset]
        ]:
            for test_dir in sorted((Path(tests_dir) / preset / fork).glob("*/*/*/*")):
                yield ComplianceTestInfo(preset, fork, test_dir)


def _select_tests(tests, start=None, limit=None):
    if start is not None:
        tests = tests[start:]
    if limit is not None:
        tests = tests[:limit]
    return tests


def _test_id(test_info: ComplianceTestInfo) -> str:
    test_path = Path(test_info.test_dir)
    return "::".join(
        [
            test_info.preset,
            test_info.fork,
            test_path.parts[-4],
            test_path.parts[-1],
        ]
    )


def pytest_generate_tests(metafunc):
    if "test_info" not in metafunc.fixturenames:
        return

    tests_dir = metafunc.config.getoption("--test-dir")
    if tests_dir is None:
        raise pytest.UsageError("--test-dir is required when running fork-choice compliance tests")

    start = metafunc.config.getoption("--start")
    limit = metafunc.config.getoption("--limit")
    test_infos = _select_tests(list(gather_tests(tests_dir)), start=start, limit=limit)
    metafunc.parametrize(
        "test_info",
        test_infos,
        ids=[_test_id(test_info) for test_info in test_infos],
    )


def test_run_compliance_case(test_info):
    run_test(test_info)
