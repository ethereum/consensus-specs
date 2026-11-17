"""Replay isolation and serialized vector regression tests."""

import pytest
import snappy
from ssz.exceptions import SSZValueError, ValueFault

from eth_consensus_specs.test.context import get_copy_of_spec, spec_with_config_overrides
from eth_consensus_specs.test.helpers.genesis import create_genesis_state
from eth_consensus_specs.test.helpers.specs import spec_targets
from eth_consensus_specs.test.helpers.voluntary_exits import prepare_signed_exits
from eth_consensus_specs.test.utils.dumper import Dumper
from eth_consensus_specs.utils import bls
from tests.generators.compliance_runners.state_transition.evaluation import cli as evaluation_cli

from . import fork_choice, state_transition
from .discovery import VectorCase


@pytest.mark.parametrize("case_type", ["processing", "blocks"])
@pytest.mark.parametrize("direction", ["overflow", "underflow"])
def test_invalid_transition_accepts_uint64_range_error(case_type, direction):
    spec = spec_targets["minimal"]["gloas"]

    def process(*args, **kwargs):
        if direction == "overflow":
            return spec.Uint64((1 << 64) - 1) + 1
        return spec.Uint64(0) - 1

    if case_type == "processing":
        state_transition.run_processing_case(process, None, None, None)
    else:
        class BlockSpec:
            state_transition = staticmethod(process)

        state_transition.run_sanity_blocks_case(BlockSpec, None, [object()], None)


def test_invalid_transition_does_not_hide_other_ssz_errors():
    def process(state):
        raise SSZValueError(ValueFault.NOT_A_BIT, value=2)

    with pytest.raises(SSZValueError, match="boolean"):
        state_transition.run_processing_case(process, None, None, None)


def test_valid_transition_does_not_hide_uint64_range_error():
    def process(state):
        spec = spec_targets["minimal"]["gloas"]
        return spec.Uint64(0) - 1

    with pytest.raises(SSZValueError):
        state_transition.run_processing_case(process, None, None, object())


@pytest.mark.parametrize(
    ("runner", "handler"),
    [("epoch_processing", "pending_deposits_churn"), ("operations", "voluntary_exit_churn")],
)
def test_replay_churn_handler_aliases(tmp_path, runner, handler):
    spec = spec_targets["minimal"]["gloas"]
    pre = create_genesis_state(spec, [spec.MAX_EFFECTIVE_BALANCE] * 64, spec.MAX_EFFECTIVE_BALANCE)
    vectors = {"pre": pre}
    if runner == "operations":
        pre.slot = spec.Slot(int(spec.config.SHARD_COMMITTEE_PERIOD) * int(spec.SLOTS_PER_EPOCH))
        operation = prepare_signed_exits(spec, pre, [0])[0]
        vectors["voluntary_exit"] = operation
    post = pre.copy()
    if runner == "operations":
        spec.process_voluntary_exit(post, operation)
    else:
        spec.process_pending_deposits(post)
    vectors["post"] = post
    for name, value in vectors.items():
        (tmp_path / f"{name}.ssz_snappy").write_bytes(snappy.compress(value.encode_bytes()))

    state_transition.run_test(VectorCase("minimal", "gloas", runner, handler, "main", tmp_path))


@pytest.mark.parametrize("invalid", [False, True])
def test_fork_choice_replay_restores_bls(tmp_path, invalid):
    spec = spec_targets["minimal"]["phase0"]
    state = create_genesis_state(
        spec, [spec.MAX_EFFECTIVE_BALANCE] * 64, spec.MAX_EFFECTIVE_BALANCE
    )
    block = spec.BeaconBlock(state_root=state.hash_tree_root())
    for name, value in (("anchor_state", state), ("anchor_block", block)):
        (tmp_path / f"{name}.ssz_snappy").write_bytes(snappy.compress(value.encode_bytes()))
    (tmp_path / "meta.yaml").write_text(f"bls_setting: {int(not bls.bls_active)}\n")
    (tmp_path / "steps.yaml").write_text("- unknown: true\n" if invalid else "[]\n")
    original = bls.bls_active
    case = VectorCase("minimal", "phase0", "fork_choice", "handler", "main", tmp_path)
    if invalid:
        with pytest.raises(AssertionError):
            fork_choice.run_test(case)
    else:
        fork_choice.run_test(case)
    assert bls.bls_active == original


@pytest.mark.parametrize("replay_mode", ["runner", "evaluation"])
@pytest.mark.parametrize("initial_bls_active", [False, True])
@pytest.mark.parametrize("valid_signature", [False, True])
@pytest.mark.parametrize("bls_setting", [None, 0, 1, 2])
def test_state_transition_replay_bls_settings(
    tmp_path, monkeypatch, replay_mode, initial_bls_active, valid_signature, bls_setting
):
    spec = spec_targets["minimal"]["gloas"]
    pre = create_genesis_state(spec, [spec.MAX_EFFECTIVE_BALANCE] * 64, spec.MAX_EFFECTIVE_BALANCE)
    pre.slot = spec.Slot(int(spec.config.SHARD_COMMITTEE_PERIOD) * int(spec.SLOTS_PER_EPOCH))
    monkeypatch.setattr(bls, "bls_active", True)
    operation = prepare_signed_exits(spec, pre, [0])[0]
    post = pre.copy()
    spec.process_voluntary_exit(post, operation)
    if not valid_signature:
        operation.signature = spec.BLSSignature()
    for name, value in (("pre", pre), ("voluntary_exit", operation), ("post", post)):
        (tmp_path / f"{name}.ssz_snappy").write_bytes(snappy.compress(value.encode_bytes()))
    metadata = "{}\n" if bls_setting is None else f"bls_setting: {bls_setting}\n"
    (tmp_path / "meta.yaml").write_text(metadata)
    case = VectorCase("minimal", "gloas", "operations", "voluntary_exit", "main", tmp_path)
    monkeypatch.setattr(bls, "bls_active", initial_bls_active)

    def replay_case():
        if replay_mode == "runner":
            state_transition.run_test(case)
        else:
            evaluation_cli.run_case(case, spec.process_voluntary_exit)

    if bls_setting == 1 and not valid_signature:
        with pytest.raises(AssertionError):
            replay_case()
    else:
        replay_case()
    assert bls.bls_active is initial_bls_active


@pytest.fixture(params=["capella", "gloas"])
def configured_exit_case(tmp_path, monkeypatch, request):
    spec = spec_targets["minimal"][request.param]
    overrides = {
        "SHARD_COMMITTEE_PERIOD": 0,
        "MIN_VALIDATOR_WITHDRAWABILITY_DELAY": 3,
        "CAPELLA_FORK_VERSION": b"\x00\x00\xab\xcd",
    }
    configured, output_config = spec_with_config_overrides(get_copy_of_spec(spec), overrides)
    monkeypatch.setattr(bls, "bls_active", True)
    pre = create_genesis_state(
        configured, [configured.MAX_EFFECTIVE_BALANCE] * 64, configured.MAX_EFFECTIVE_BALANCE
    )
    operation = prepare_signed_exits(configured, pre, [0])[0]
    post = pre.copy()
    configured.process_voluntary_exit(post, operation)
    for name, value in (("pre", pre), ("voluntary_exit", operation), ("post", post)):
        (tmp_path / f"{name}.ssz_snappy").write_bytes(snappy.compress(value.encode_bytes()))
    (tmp_path / "meta.yaml").write_text("bls_setting: 1\n")
    case = VectorCase("minimal", request.param, "operations", "voluntary_exit", "main", tmp_path)
    return spec, configured, output_config, overrides, post, case


@pytest.mark.parametrize("full_config", [False, True])
@pytest.mark.parametrize("corrupt_post", [False, True])
def test_state_transition_case_config_is_isolated(configured_exit_case, full_config, corrupt_post):
    spec, configured, output_config, overrides, post, case = configured_exit_case
    original_config = spec.config
    Dumper().dump_cfg(case.test_dir, "config", output_config if full_config else overrides)
    loaded = state_transition.load_spec(case.preset, case.fork, case.test_dir)
    assert loaded.config == configured.config
    assert hash(loaded.config) == hash(configured.config)
    if corrupt_post:
        post.slot += 1
        (case.test_dir / "post.ssz_snappy").write_bytes(snappy.compress(post.encode_bytes()))
        with pytest.raises(AssertionError):
            state_transition.run_test(case)
    else:
        state_transition.run_test(case)
    assert spec.config is original_config
    assert spec.config.SHARD_COMMITTEE_PERIOD != configured.config.SHARD_COMMITTEE_PERIOD
    # The next replay without config.yaml must use the default committee period.
    (case.test_dir / "config.yaml").unlink()
    with pytest.raises(AssertionError):
        state_transition.run_test(case)


def test_case_config_prevents_unrelated_negative_pass(configured_exit_case):
    spec, _, output_config, _, _, case = configured_exit_case
    original_config = spec.config
    Dumper().dump_cfg(case.test_dir, "config", output_config)
    (case.test_dir / "post.ssz_snappy").unlink()
    # This exit is valid under its case config, so declaring it invalid must fail.
    with pytest.raises(AssertionError, match="expected an assertion error, but got none"):
        state_transition.run_test(case)
    assert spec.config is original_config
