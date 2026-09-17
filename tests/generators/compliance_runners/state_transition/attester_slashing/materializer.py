"""Materialize Gloas ``process_attester_slashing`` operation vectors."""

from __future__ import annotations

from typing import Any, TYPE_CHECKING

from eth_consensus_specs.test.helpers.attestations import sign_indexed_attestation
from eth_consensus_specs.test.helpers.attester_slashings import (
    get_valid_attester_slashing_by_indices,
)
from eth_consensus_specs.test.helpers.genesis import create_genesis_state
from tests.generators.compliance_runners.state_transition.materializer import Materializer

if TYPE_CHECKING:
    from tests.generators.compliance_runners.gen_base.gen_typing import TestCasePart


_DIMS = [
    "scenario",
    "attestation_data_slashable",
    "attestation_1_indices_well_formed",
    "attestation_1_valid",
    "attestation_2_valid",
    "intersection_size",
    "slashable_intersection",
    "outcome",
]


class AttesterSlashingMaterializer(Materializer):
    runner_name = "operations"
    handler_name = "attester_slashing"

    def _base_state(self) -> Any:
        return create_genesis_state(
            self.spec,
            validator_balances=[self.spec.MAX_EFFECTIVE_BALANCE] * 64,
            activation_threshold=self.spec.MAX_EFFECTIVE_BALANCE,
        )

    def materialize_solution(self, solution: Any) -> tuple[dict, list[TestCasePart]]:
        spec = self.spec
        pre = self._base_state()
        scenario = str(solution.scenario)
        indices = {
            "VALID_TWO": [0, 1],
            "VALID_THREE": [0, 1, 2],
        }.get(scenario, [0])
        slashing = get_valid_attester_slashing_by_indices(
            spec, pre, indices, signed_1=True, signed_2=True
        )

        if scenario == "NOT_SLASHABLE":
            slashing.attestation_2.data = slashing.attestation_1.data.copy()
            sign_indexed_attestation(spec, pre, slashing.attestation_2)
        elif scenario == "INVALID_FIRST_SIGNATURE":
            slashing.attestation_1.signature = spec.BLSSignature()
        elif scenario == "INVALID_EMPTY_INDICES":
            slashing.attestation_1.attesting_indices = spec.AttestingIndices()
        elif scenario == "INVALID_SECOND_SIGNATURE":
            slashing.attestation_2.signature = spec.BLSSignature()
        elif scenario == "NO_SLASHABLE_INTERSECTION":
            pre.validators[0].slashed = True
        elif scenario not in {"VALID_ONE", "VALID_TWO", "VALID_THREE"}:
            raise ValueError(f"unknown attester-slashing scenario: {scenario}")

        post = pre.copy()
        try:
            spec.process_attester_slashing(post, slashing)
        except (AssertionError, IndexError):
            post = None

        claimed = {
            name: bool(value) if isinstance(value := getattr(solution, name), bool) else str(value)
            for name in _DIMS
            if name != "scenario"
        }
        meta = {
            "description": f"process_attester_slashing: {claimed['outcome']}",
            "bls_setting": 1,
            "claimed": claimed,
        }
        parts = [
            ("pre", "ssz", pre.encode_bytes()),
            ("attester_slashing", "ssz", slashing.encode_bytes()),
        ]
        if post is not None:
            parts.append(("post", "ssz", post.encode_bytes()))
        return meta, parts
