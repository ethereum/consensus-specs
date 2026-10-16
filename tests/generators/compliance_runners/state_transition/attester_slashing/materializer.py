"""Materialize Gloas ``process_attester_slashing`` operation vectors."""

from __future__ import annotations

from typing import Any, TYPE_CHECKING

from eth_consensus_specs.test.helpers.attestations import sign_indexed_attestation
from eth_consensus_specs.test.helpers.attester_slashings import (
    get_valid_attester_slashing_by_indices,
)
from eth_consensus_specs.test.helpers.genesis import create_genesis_state
from tests.generators.compliance_runners.state_transition.materializer import Materializer

from .target import TARGET

if TYPE_CHECKING:
    from tests.generators.compliance_runners.gen_base.gen_typing import TestCasePart


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
        outcome = str(solution.outcome)
        if outcome == "ACCEPT":
            scenario = {
                "ONE": "VALID_ONE",
                "TWO": "VALID_TWO",
                "THREE_OR_MORE": "VALID_THREE",
            }[str(solution.intersection_size)]
        else:
            scenario = {
                "REJECT_NOT_SLASHABLE": "NOT_SLASHABLE",
                "REJECT_FIRST_ATTESTATION": "INVALID_FIRST_SIGNATURE",
                "REJECT_MALFORMED_FIRST_INDICES": "INVALID_EMPTY_INDICES",
                "REJECT_SECOND_ATTESTATION": "INVALID_SECOND_SIGNATURE",
                "REJECT_NO_SLASHABLE_INTERSECTION": "NO_SLASHABLE_INTERSECTION",
            }[outcome]
        intersection_size = {
            "VALID_TWO": 2,
            "VALID_THREE": 3,
        }.get(scenario, 1)
        indices = sorted(self.rng.sample(range(len(pre.validators)), intersection_size))
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
            for index in set(slashing.attestation_1.attesting_indices).intersection(
                slashing.attestation_2.attesting_indices
            ):
                pre.validators[index].slashed = True
        elif scenario not in {"VALID_ONE", "VALID_TWO", "VALID_THREE"}:
            raise ValueError(f"unknown attester-slashing scenario: {scenario}")

        post = pre.copy()
        try:
            spec.process_attester_slashing(post, slashing)
        except (AssertionError, IndexError):
            post = None

        claimed = self.claimed_record(TARGET, solution)
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


MATERIALIZER = AttesterSlashingMaterializer
