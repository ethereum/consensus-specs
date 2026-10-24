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
        intersection_count = {
            "NONE": 0,
            "ONE": 1,
            "TWO": 2,
            "THREE_OR_MORE": 3,
        }[solution.intersection_size]
        if intersection_count:
            shared_indices = sorted(self.rng.sample(range(len(pre.validators)), intersection_count))
            indices_1 = shared_indices
            indices_2 = shared_indices
        else:
            indices_1, indices_2 = sorted(self.rng.sample(range(len(pre.validators)), 2))
            indices_1 = [indices_1]
            indices_2 = [indices_2]
        slashing = get_valid_attester_slashing_by_indices(
            spec, pre, indices_1, indices_2, signed_1=True, signed_2=True
        )

        if not solution.attestation_data_slashable:
            slashing.attestation_2.data = slashing.attestation_1.data.copy()
            sign_indexed_attestation(spec, pre, slashing.attestation_2)
        if not solution.attestation_1_indices_well_formed:
            slashing.attestation_1.attesting_indices = spec.AttestingIndices()
        if not solution.attestation_1_valid:
            slashing.attestation_1.signature = spec.BLSSignature()
        if not solution.attestation_2_valid:
            slashing.attestation_2.signature = spec.BLSSignature()
        if not solution.slashable_intersection:
            for index in set(slashing.attestation_1.attesting_indices).intersection(
                slashing.attestation_2.attesting_indices
            ):
                pre.validators[index].slashed = True

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
