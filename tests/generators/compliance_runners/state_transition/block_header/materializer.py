"""Materialize Gloas ``process_block_header`` operation vectors."""

from __future__ import annotations

from functools import cached_property
from typing import Any, TYPE_CHECKING

from eth_consensus_specs.test.helpers.attester_slashings import (
    get_valid_attester_slashing_by_indices,
)
from eth_consensus_specs.test.helpers.block import build_empty_block, get_proposer_index_maybe
from eth_consensus_specs.test.helpers.genesis import create_genesis_state
from eth_consensus_specs.test.helpers.state import state_transition_and_sign_block
from tests.generators.compliance_runners.state_transition.materializer import Materializer
from tests.generators.compliance_runners.state_transition.validation_helpers import bls_enabled

from .target import TARGET
from .witness import slot_witness

if TYPE_CHECKING:
    from tests.generators.compliance_runners.gen_base.gen_typing import TestCasePart


class BlockHeaderMaterializer(Materializer):
    runner_name = "operations"
    handler_name = "block_header"

    @cached_property
    def _genesis_state(self) -> Any:
        spec = self.spec
        return create_genesis_state(
            spec,
            validator_balances=[spec.MAX_EFFECTIVE_BALANCE] * 64,
            activation_threshold=spec.MAX_EFFECTIVE_BALANCE,
        )

    def materialize_solution(self, solution: Any) -> tuple[dict, list[TestCasePart]]:
        spec = self.spec
        assignment = {f.name: getattr(solution, f.name) for f in TARGET.factors}
        state_slot, block_slot, latest_header_slot = slot_witness(assignment)
        pre = self._genesis_state.copy()
        expected_proposer = get_proposer_index_maybe(spec, pre, spec.Slot(state_slot))
        proposer_index = expected_proposer
        if not assignment["proposer_index_matches"]:
            proposer_index = spec.ValidatorIndex((int(expected_proposer) + 1) % len(pre.validators))

        with bls_enabled():
            prior_block = build_empty_block(spec, pre, slot=spec.Slot(latest_header_slot))
            prior_block.body.graffiti = spec.Bytes32(self.rng.getrandbits(256).to_bytes(32, "big"))
            if not assignment["proposer_not_slashed"]:
                slashing = get_valid_attester_slashing_by_indices(
                    spec, pre, [proposer_index], signed_1=True, signed_2=True
                )
                prior_block.body.attester_slashings.append(slashing)
            state_transition_and_sign_block(spec, pre, prior_block)
        if pre.slot < state_slot:
            spec.process_slots(pre, spec.Slot(state_slot))
        assert spec.get_beacon_proposer_index(pre) == expected_proposer

        block = build_empty_block(spec, pre)
        block.slot = spec.Slot(block_slot)
        block.proposer_index = proposer_index
        expected_parent_root = spec.hash_tree_root(pre.latest_block_header)
        block.parent_root = expected_parent_root
        if not assignment["parent_matches"]:
            mismatched_parent_root = bytearray(self.rng.getrandbits(256).to_bytes(32, "big"))
            if mismatched_parent_root == bytes(expected_parent_root):
                mismatched_parent_root[0] ^= 1
            block.parent_root = spec.Root(bytes(mismatched_parent_root))
        post = pre.copy()
        try:
            spec.process_block_header(post, block)
        except (AssertionError, IndexError):
            post = None

        claimed = self.claimed_record(TARGET, solution)
        meta = {
            "description": f"process_block_header: {'ACCEPT' if post is not None else 'REJECT'}",
            "bls_setting": 0,
            "claimed": claimed,
        }
        parts = [
            ("pre", "ssz", pre.encode_bytes()),
            ("block", "ssz", block.encode_bytes()),
        ]
        if post is not None:
            parts.append(("post", "ssz", post.encode_bytes()))
        return meta, parts


MATERIALIZER = BlockHeaderMaterializer
