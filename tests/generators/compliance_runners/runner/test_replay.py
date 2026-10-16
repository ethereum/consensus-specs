"""Replay isolation and serialized fork-choice smoke tests."""

import pytest
import snappy

from eth_consensus_specs.test.helpers.genesis import create_genesis_state
from eth_consensus_specs.test.helpers.specs import spec_targets
from eth_consensus_specs.utils import bls

from . import fork_choice
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
