"""Materialize aspect-model solutions for Gloas payload attestations."""

from __future__ import annotations

from typing import Any

from eth_consensus_specs.test.helpers.genesis import create_genesis_state
from eth_consensus_specs.test.helpers.payload_attestation import prepare_signed_payload_attestation

from ...gen_base.gen_typing import TestCasePart
from tests.generators.compliance_runners.state_transition.materializer import Materializer

_DIMS = [
    "parent_root_matches",
    "slot_is_previous",
    "attesting_indices_nonempty",
    "signature_valid",
    "state_effected",
    "outcome",
]


def _s(sol: Any, name: str) -> str:
    return str(getattr(sol, name))


def _b(sol: Any, name: str) -> bool:
    return bool(getattr(sol, name))


class PayloadAttestationMaterializer(Materializer):
    runner_name = "operations"
    handler_name = "payload_attestation"

    def _base_state(self) -> Any:
        state = create_genesis_state(
            self.spec,
            validator_balances=[self.spec.MAX_EFFECTIVE_BALANCE] * 64,
            activation_threshold=self.spec.MAX_EFFECTIVE_BALANCE,
        )
        self.spec.process_slots(state, self.spec.Slot(3))
        return state

    def materialize_solution(self, sol: Any) -> tuple[dict, list[TestCasePart]]:
        spec, pre = self.spec, self._base_state()
        slot = pre.slot - 1 if _b(sol, "slot_is_previous") else pre.slot
        root = (
            pre.latest_block_header.parent_root
            if _b(sol, "parent_root_matches")
            else spec.Root(b"\x42" * 32)
        )
        nonempty = _b(sol, "attesting_indices_nonempty")
        operation = prepare_signed_payload_attestation(
            spec,
            pre,
            slot=slot,
            beacon_block_root=root,
            attesting_indices=None if nonempty else [],
            valid_signature=nonempty and _s(sol, "signature_valid") == "T",
        )
        post = pre.copy()
        try:
            spec.process_payload_attestation(post, operation)
        except (AssertionError, IndexError):
            post = None
        claimed = {
            name: (_b(sol, name) if isinstance(getattr(sol, name), bool) else _s(sol, name))
            for name in _DIMS
        }
        parts: list[TestCasePart] = [
            ("pre", "ssz", pre.encode_bytes()),
            ("payload_attestation", "ssz", operation.encode_bytes()),
        ]
        if post is not None:
            parts.append(("post", "ssz", post.encode_bytes()))
        meta = {"description": f"process_payload_attestation: {claimed['outcome']}", "bls_setting": 1, "claimed": claimed}
        return meta, parts
