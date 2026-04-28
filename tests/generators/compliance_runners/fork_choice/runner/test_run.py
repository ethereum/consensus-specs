from collections import namedtuple
from collections.abc import Iterable
from glob import glob
from pathlib import Path

import pytest
from ruamel.yaml import YAML
from snappy import uncompress

from eth_consensus_specs.test.context import expect_assertion_error
from eth_consensus_specs.test.helpers.forks import is_post_gloas
from eth_consensus_specs.test.helpers.specs import spec_targets

from ..instantiators.helpers import payload_attestation_to_messages


def read_yaml(fp):
    with open(fp) as f:
        yaml = YAML(typ="safe")
        return yaml.load(f.read())


def read_ssz_snappy(fp):
    with open(fp, "rb") as f:
        res = uncompress(f.read())
        return res


def get_test_case(spec, td):
    def get_prefix(p):
        return p[p.rindex("/") + 1 : p.rindex(".")]

    return (
        read_yaml(f"{td}/meta.yaml"),
        spec.BeaconBlock.decode_bytes(read_ssz_snappy(f"{td}/anchor_block.ssz_snappy")),
        spec.BeaconState.decode_bytes(read_ssz_snappy(f"{td}/anchor_state.ssz_snappy")),
        {
            get_prefix(b): spec.SignedBeaconBlock.decode_bytes(read_ssz_snappy(b))
            for b in glob(f"{td}/block_*.ssz_snappy")
        },
        {
            get_prefix(b): spec.Attestation.decode_bytes(read_ssz_snappy(b))
            for b in glob(f"{td}/attestation_*.ssz_snappy")
        },
        {
            get_prefix(b): spec.AttesterSlashing.decode_bytes(read_ssz_snappy(b))
            for b in glob(f"{td}/attester_slashing_*.ssz_snappy")
        },
        {
            get_prefix(e): spec.SignedExecutionPayloadEnvelope.decode_bytes(read_ssz_snappy(e))
            for e in glob(f"{td}/execution_payload_envelope_*.ssz_snappy")
        },
        {
            get_prefix(b): spec.PayloadAttestationMessage.decode_bytes(read_ssz_snappy(b))
            for b in glob(f"{td}/payload_attestation_*.ssz_snappy")
        },
        read_yaml(f"{td}/steps.yaml"),
    )


ComplianceTestInfo = namedtuple(
    "ComplianceTestInfo",
    [
        "preset",
        "fork",
        "test_dir",
    ],
)


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
                    try:
                        spec.on_attestation(store, block_att, is_from_block=True)
                    except AssertionError:
                        pass
                for block_att_slashing in signed_block.message.body.attester_slashings:
                    try:
                        spec.on_attester_slashing(store, block_att_slashing)
                    except AssertionError:
                        pass
                if is_post_gloas(spec):
                    state = store.block_states[signed_block.message.hash_tree_root()]
                    for payload_attestation in signed_block.message.body.payload_attestations:
                        for ptc_message in payload_attestation_to_messages(
                            spec, state, payload_attestation
                        ):
                            try:
                                spec.on_payload_attestation_message(
                                    store, ptc_message, is_from_block=True
                                )
                            except AssertionError:
                                pass
            else:
                expect_assertion_error(lambda: spec.on_block(store, signed_block))
        elif "attestation" in step:
            att_id = step["attestation"]
            valid = step.get("valid", True)
            attestation = atts[att_id]
            if valid:
                spec.on_attestation(store, attestation, is_from_block=False)
            else:
                expect_assertion_error(
                    lambda: spec.on_attestation(store, attestation, is_from_block=False)
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
                    lambda: spec.on_execution_payload_envelope(store, signed_envelope)
                )
        elif "payload_attestation" in step:
            ptc_message_id = step["payload_attestation"]
            valid = step.get("valid", True)
            ptc_message = payload_atts[ptc_message_id]
            if valid:
                spec.on_payload_attestation_message(store, ptc_message, is_from_block=False)
            else:
                expect_assertion_error(
                    lambda: spec.on_payload_attestation_message(
                        store, ptc_message, is_from_block=False
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
                    filtered_block_roots = spec.get_filtered_block_tree(store).keys()
                    leaves_viable_for_head = [
                        root
                        for root in filtered_block_roots
                        if not any(
                            c for c in filtered_block_roots if store.blocks[c].parent_root == root
                        )
                    ]
                    viable_for_head_roots_and_weights = {
                        str(viable_for_head_root): int(spec.get_weight(store, viable_for_head_root))
                        for viable_for_head_root in leaves_viable_for_head
                    }
                    expected = {kv["root"]: kv["weight"] for kv in value}
                    assert expected == viable_for_head_roots_and_weights
                elif check == "head_payload_status":
                    head = get_head()
                    assert head.payload_status == value
                else:
                    assert False
        else:
            assert False


def gather_tests(tests_dir) -> Iterable[ComplianceTestInfo]:
    for preset in [p.name for p in Path(tests_dir).glob("*") if p.name in spec_targets]:
        for fork in [
            f.name for f in (Path(tests_dir) / preset).glob("*") if f.name in spec_targets[preset]
        ]:
            for test_dir in sorted(
                [td for td in (Path(tests_dir) / preset / fork).glob("*/*/*/*")]
            ):
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
