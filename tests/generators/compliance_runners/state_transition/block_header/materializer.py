"""Materialize Gloas ``process_block_header`` operation vectors."""

from __future__ import annotations

from typing import Any, TYPE_CHECKING

from eth_consensus_specs.test.helpers.block import build_empty_block
from eth_consensus_specs.test.helpers.genesis import create_genesis_state
from tests.generators.compliance_runners.state_transition.materializer import Materializer

from .witness import complete_obligation, slot_witness

if TYPE_CHECKING:
    from tests.generators.compliance_runners.gen_base.gen_typing import TestCasePart


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
        return state

    def materialize_solution(self, solution: Any) -> tuple[dict, list[TestCasePart]]:
        spec = self.spec
        requested = {
            str(name): value
            for name, value in vars(solution).items()
            if not str(name).startswith("_")
        }
        assignment = complete_obligation(requested)
        state_slot, block_slot, latest_header_slot = slot_witness(assignment)
        pre = self._base_state()
        pre.slot = spec.Slot(state_slot)
        header = pre.latest_block_header
        header.parent_root = spec.Root(self.rng.getrandbits(256).to_bytes(32, "big"))
        header.state_root = spec.Root(self.rng.getrandbits(256).to_bytes(32, "big"))
        header.body_root = spec.Root(self.rng.getrandbits(256).to_bytes(32, "big"))
        header.proposer_index = spec.ValidatorIndex(self.rng.randrange(len(pre.validators)))
        current_epoch = int(spec.get_current_epoch(pre))
        mix_index = (
            current_epoch
            + int(spec.EPOCHS_PER_HISTORICAL_VECTOR)
            - int(spec.MIN_SEED_LOOKAHEAD)
            - 1
        ) % len(pre.randao_mixes)
        pre.randao_mixes[mix_index] = spec.Bytes32(self.rng.getrandbits(256).to_bytes(32, "big"))
        expected_proposer_index = int(spec.get_beacon_proposer_index(pre))

        proposer_index_matches = assignment["proposer_index_matches"]
        parent_matches = assignment["parent_matches"]
        proposer_not_slashed = assignment["proposer_not_slashed"]
        pre.latest_block_header.slot = spec.Slot(latest_header_slot)
        if latest_header_slot == state_slot:
            # A header from the current slot has not had its state root filled
            # by a subsequent process_slot invocation yet.
            pre.latest_block_header.state_root = spec.Root()

        block = build_empty_block(
            spec, pre, slot=state_slot, proposer_index=expected_proposer_index
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
            mismatched_parent_root = bytearray(self.rng.getrandbits(256).to_bytes(32, "big"))
            if mismatched_parent_root == bytes(expected_parent_root):
                mismatched_parent_root[0] ^= 1
            block.parent_root = spec.Root(bytes(mismatched_parent_root))
        if not proposer_not_slashed and int(block.proposer_index) < len(pre.validators):
            pre.validators[block.proposer_index].slashed = True

        post = pre.copy()
        try:
            spec.process_block_header(post, block)
        except (AssertionError, IndexError):
            post = None

        claimed = assignment
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
