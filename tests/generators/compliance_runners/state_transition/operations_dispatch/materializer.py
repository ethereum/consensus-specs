"""Materialize block vectors that exercise Gloas operation dispatch."""

from __future__ import annotations

from typing import Any, TYPE_CHECKING

from eth_consensus_specs.test.helpers.attestations import get_valid_attestation, sign_attestation
from eth_consensus_specs.test.helpers.attester_slashings import (
    get_valid_attester_slashing_by_indices,
)
from eth_consensus_specs.test.helpers.block import apply_empty_block, build_empty_block
from eth_consensus_specs.test.helpers.bls_to_execution_changes import get_signed_address_change
from eth_consensus_specs.test.helpers.genesis import create_genesis_state
from eth_consensus_specs.test.helpers.payload_attestation import prepare_signed_payload_attestation
from eth_consensus_specs.test.helpers.proposer_slashings import get_valid_proposer_slashing
from eth_consensus_specs.test.helpers.state import next_slots
from eth_consensus_specs.test.helpers.voluntary_exits import prepare_signed_exits
from eth_consensus_specs.utils import bls
from tests.generators.compliance_runners.state_transition.materializer import Materializer

if TYPE_CHECKING:
    from tests.generators.compliance_runners.gen_base.gen_typing import TestCasePart


_FIELDS = (
    "proposer_slashings",
    "attester_slashings",
    "attestations",
    "voluntary_exits",
    "bls_to_execution_changes",
    "payload_attestations",
)


class OperationsDispatchMaterializer(Materializer):
    runner_name = "sanity"
    handler_name = "blocks"

    def _genesis(self) -> Any:
        spec = self.spec
        return create_genesis_state(
            spec,
            validator_balances=[spec.MAX_EFFECTIVE_BALANCE] * 64,
            activation_threshold=spec.MAX_EFFECTIVE_BALANCE,
        )

    def _parent_state(self) -> Any:
        spec = self.spec
        pre = self._genesis()
        pre.slot = spec.Slot(
            int(spec.config.SHARD_COMMITTEE_PERIOD) * int(spec.SLOTS_PER_EPOCH) + 2
        )
        parent = build_empty_block(spec, pre, slot=int(pre.slot) + 1)
        spec.state_transition(pre, spec.SignedBeaconBlock(message=parent), validate_result=False)
        return pre

    def _missed_slot_state(self) -> Any:
        spec = self.spec
        pre = self._genesis()
        for slot in (1, 2, 3):
            apply_empty_block(spec, pre, slot)
        next_slots(spec, pre, 1)  # Slot 4 has no block; the parent block is at slot 3.
        pre.execution_payload_availability[3] = spec.Boolean(1)
        pre.execution_payload_availability[4] = spec.Boolean(0)
        return pre

    def _populate(self, scenario: str, pre: Any, block: Any) -> dict:
        spec, body = self.spec, block.body
        claimed: dict[str, Any] = {}
        if scenario == "all_lists":
            for index in (1, 5):
                body.proposer_slashings.append(
                    get_valid_proposer_slashing(
                        spec, pre, slashed_index=index, signed_1=True, signed_2=True
                    )
                )
            body.attester_slashings.append(
                get_valid_attester_slashing_by_indices(
                    spec, pre, [2], slot=int(pre.slot), signed_1=True, signed_2=True
                )
            )
            body.attestations.append(
                get_valid_attestation(spec, pre, slot=int(pre.slot), signed=True)
            )
            body.voluntary_exits.append(prepare_signed_exits(spec, pre, [3])[0])
            body.bls_to_execution_changes.append(
                get_signed_address_change(spec, pre, validator_index=4)
            )
            body.payload_attestations.append(
                prepare_signed_payload_attestation(
                    spec, pre, slot=int(pre.slot), beacon_block_root=block.parent_root
                )
            )
        elif scenario == "slash_before_exit":
            body.proposer_slashings.append(
                get_valid_proposer_slashing(
                    spec, pre, slashed_index=1, signed_1=True, signed_2=True
                )
            )
            body.voluntary_exits.append(prepare_signed_exits(spec, pre, [1])[0])
            claimed["shared_slash_exit"] = True
        elif scenario == "invalid_payload_attestation":
            body.payload_attestations.append(
                prepare_signed_payload_attestation(
                    spec, pre, slot=int(pre.slot), beacon_block_root=spec.Root(b"\xff" * 32)
                )
            )
            claimed["payload_root_matches"] = False
        elif scenario in ("parent_slot_matches", "parent_slot_mismatches"):
            advanced = pre.copy()
            spec.process_slots(advanced, spec.Slot(5))
            attestation = get_valid_attestation(
                spec,
                advanced,
                slot=4,
                beacon_block_root=spec.get_block_root_at_slot(advanced, spec.Slot(4)),
            )
            attestation.data.index = spec.CommitteeIndex(
                1 if scenario == "parent_slot_matches" else 0
            )
            sign_attestation(spec, advanced, attestation)
            body.attestations.append(attestation)
            claimed.update(
                parent_slot_differs_from_attestation_slot=True,
                parent_slot_payload_available=True,
                attestation_slot_payload_available=False,
                head_flag_set=scenario == "parent_slot_matches",
            )
        else:
            raise ValueError(f"unknown dispatch scenario: {scenario}")
        claimed["counts"] = {field: len(getattr(body, field)) for field in _FIELDS}
        return claimed

    def materialize_solution(self, solution: Any) -> tuple[dict, list[TestCasePart]]:
        spec = self.spec
        scenario = str(solution.scenario)
        old_bls_active = bls.bls_active
        bls.bls_active = True
        try:
            pre = (
                self._missed_slot_state()
                if scenario.startswith("parent_slot_")
                else self._parent_state()
            )
            block = build_empty_block(spec, pre, slot=int(pre.slot) + 1)
            claimed = self._populate(scenario, pre, block)
            signed_block = spec.SignedBeaconBlock(message=block)
            post = pre.copy()
            try:
                spec.state_transition(post, signed_block, validate_result=False)
            except (AssertionError, IndexError):
                post = None
        finally:
            bls.bls_active = old_bls_active

        claimed["accepted"] = bool(solution.accepted)
        claimed["outcome"] = "ACCEPT" if solution.accepted else "REJECT"
        meta = {
            "description": f"process_operations dispatch: {scenario}",
            "bls_setting": 1,
            "blocks_count": 1,
            "claimed": claimed,
        }
        parts: list[TestCasePart] = [
            ("pre", "ssz", pre.encode_bytes()),
            ("blocks_0", "ssz", signed_block.encode_bytes()),
        ]
        if post is not None:
            parts.append(("post", "ssz", post.encode_bytes()))
        return meta, parts


MATERIALIZER = OperationsDispatchMaterializer
