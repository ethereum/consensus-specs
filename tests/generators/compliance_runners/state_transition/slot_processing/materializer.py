"""Materialize one-slot ``sanity/slots`` vectors for ``process_slot``."""

from __future__ import annotations

from typing import Any, TYPE_CHECKING

from eth_consensus_specs.test.helpers.genesis import create_genesis_state
from tests.generators.compliance_runners.state_transition.materializer import Materializer

if TYPE_CHECKING:
    from tests.generators.compliance_runners.gen_base.gen_typing import TestCasePart


class SlotProcessingMaterializer(Materializer):
    runner_name = "sanity"
    # The sanity reference-test format names this handler ``slots``.
    handler_name = "slots"

    def materialize_solution(self, solution: Any) -> tuple[dict, list[TestCasePart]]:
        spec = self.spec
        period = int(spec.SLOTS_PER_HISTORICAL_ROOT)
        position = str(getattr(solution, "ring_position", "FIRST"))
        slot = {
            "FIRST": 0,
            "MIDDLE": period // 2,
            "LAST": period - 1,
        }[position]
        pre = create_genesis_state(
            spec,
            validator_balances=[spec.MAX_EFFECTIVE_BALANCE] * 64,
            activation_threshold=spec.MAX_EFFECTIVE_BALANCE,
        )
        pre.slot = spec.Slot(slot)
        index = slot % period
        next_index = (slot + 1) % period

        header_empty = bool(getattr(solution, "header_state_root_empty", True))
        pre.latest_block_header.state_root = (
            spec.Bytes32() if header_empty else spec.Bytes32(b"\x01" * 32)
        )
        pre.state_roots[index] = (
            spec.Bytes32(b"\x01" * 32)
            if bool(getattr(solution, "state_root_destination_populated", False))
            else spec.Bytes32()
        )
        pre.block_roots[index] = (
            spec.Bytes32(b"\x01" * 32)
            if bool(getattr(solution, "block_root_destination_populated", False))
            else spec.Bytes32()
        )
        pre.execution_payload_availability[next_index] = spec.Boolean(
            bool(getattr(solution, "next_payload_available_before_clear", False))
        )

        slots = 1
        post = pre.copy()
        spec.process_slots(post, spec.Slot(int(pre.slot) + slots))
        claimed = {
            str(key): value for key, value in vars(solution).items() if not str(key).startswith("_")
        }
        return {
            "description": f"process_slot at {position.lower()} historical-root index",
            "claimed": claimed,
        }, [
            ("pre", "ssz", pre.encode_bytes()),
            ("slots", "data", slots),
            ("post", "ssz", post.encode_bytes()),
        ]


MATERIALIZER = SlotProcessingMaterializer
