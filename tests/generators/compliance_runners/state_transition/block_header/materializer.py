"""Materialize Gloas ``process_block_header`` operation vectors."""

from __future__ import annotations

from typing import Any, TYPE_CHECKING

from eth_consensus_specs.test.helpers.block import build_empty_block
from eth_consensus_specs.test.helpers.genesis import create_genesis_state
from tests.generators.compliance_runners.state_transition.materializer import Materializer

if TYPE_CHECKING:
    from tests.generators.compliance_runners.gen_base.gen_typing import TestCasePart


def _value(solution: Any, name: str, *, default: bool) -> bool:
    return bool(getattr(solution, name, default))


class BlockHeaderMaterializer(Materializer):
    runner_name = "operations"
    handler_name = "block_header"

    def _base_state(self) -> Any:
        spec = self.spec
        state = create_genesis_state(
            spec,
            validator_balances=[spec.MAX_EFFECTIVE_BALANCE] * 64,
            activation_threshold=spec.MAX_EFFECTIVE_BALANCE,
        )
        state.slot = spec.Slot(1)
        return state

    def materialize_solution(self, solution: Any) -> tuple[dict, list[TestCasePart]]:
        spec = self.spec
        pre = self._base_state()
        expected_proposer_index = int(spec.get_beacon_proposer_index(pre))

        gates = {
            name: _value(solution, name, default=True)
            for name in (
                "slot_matches_state",
                "slot_is_newer",
                "proposer_index_matches",
                "parent_matches",
                "proposer_not_slashed",
            )
        }
        accepted = _value(solution, "accepted", default=True)
        if not accepted and all(gates.values()):
            for name in gates:
                if not hasattr(solution, name):
                    gates[name] = False
                    break
            else:
                gates["slot_matches_state"] = False

        slot_matches_state = gates["slot_matches_state"]
        slot_is_newer = gates["slot_is_newer"]
        proposer_index_matches = gates["proposer_index_matches"]
        parent_matches = gates["parent_matches"]
        proposer_not_slashed = gates["proposer_not_slashed"]

        block_slot = int(pre.slot) if slot_matches_state else int(pre.slot) + 1
        latest_header_slot = block_slot - 1 if slot_is_newer else block_slot
        pre.latest_block_header.slot = spec.Slot(latest_header_slot)

        block = build_empty_block(
            spec, pre, slot=block_slot, proposer_index=expected_proposer_index
        )
        block.slot = spec.Slot(block_slot)
        block.proposer_index = spec.ValidatorIndex(expected_proposer_index)
        if not proposer_index_matches:
            block.proposer_index = spec.ValidatorIndex(
                (expected_proposer_index + 1) % len(pre.validators)
            )
        expected_parent_root = spec.hash_tree_root(pre.latest_block_header)
        block.parent_root = expected_parent_root
        if not parent_matches:
            block.parent_root = spec.Root(b"\xff" * 32)
            if block.parent_root == expected_parent_root:
                block.parent_root = spec.Root(b"\x00" * 32)
        if not proposer_not_slashed and int(block.proposer_index) < len(pre.validators):
            pre.validators[block.proposer_index].slashed = True

        post = pre.copy()
        try:
            spec.process_block_header(post, block)
        except (AssertionError, IndexError):
            post = None

        claimed = {
            name: bool(getattr(solution, name))
            for name in (
                "slot_matches_state",
                "slot_is_newer",
                "proposer_index_matches",
                "parent_matches",
                "proposer_not_slashed",
                "accepted",
            )
            if hasattr(solution, name)
        }
        claimed["accepted"] = post is not None
        meta = {
            "description": f"process_block_header: {'ACCEPT' if post is not None else 'REJECT'}",
            "bls_setting": 0,
            "claimed": claimed,
        }
        parts = [
            ("pre", "ssz", pre.encode_bytes()),
            ("block_header", "ssz", block.encode_bytes()),
        ]
        if post is not None:
            parts.append(("post", "ssz", post.encode_bytes()))
        return meta, parts


MATERIALIZER = BlockHeaderMaterializer
