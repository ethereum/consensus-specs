"""Replay isolation and serialized vector regression tests."""

import pytest
import snappy

from eth_consensus_specs.test.helpers.genesis import create_genesis_state
from eth_consensus_specs.test.helpers.specs import spec_targets
from eth_consensus_specs.test.helpers.voluntary_exits import prepare_signed_exits
from eth_consensus_specs.utils import bls
from tests.generators.compliance_runners.state_transition.evaluation import cli as evaluation_cli

from . import fork_choice, state_transition
from .discovery import VectorCase


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
