"""Materialize Gloas ``process_bls_to_execution_change`` operation vectors."""

from __future__ import annotations

from typing import Any, TYPE_CHECKING

from eth_consensus_specs.test.helpers.bls_to_execution_changes import get_signed_address_change
from eth_consensus_specs.test.helpers.genesis import create_genesis_state
from tests.generators.compliance_runners.state_transition.materializer import Materializer

if TYPE_CHECKING:
    from tests.generators.compliance_runners.gen_base.gen_typing import TestCasePart


_DIMS = [
    "scenario",
    "validator_index_in_range",
    "has_bls_withdrawal_credential",
    "from_pubkey_matches",
    "signature_valid",
    "outcome",
]
_VALIDATOR_COUNT = 64
_VALIDATOR_INDEX = 0


class BLSToExecutionChangeMaterializer(Materializer):
    runner_name = "operations"
    handler_name = "bls_to_execution_change"

    def _base_state(self) -> Any:
        return create_genesis_state(
            self.spec,
            validator_balances=[self.spec.MAX_EFFECTIVE_BALANCE] * _VALIDATOR_COUNT,
            activation_threshold=self.spec.MAX_EFFECTIVE_BALANCE,
        )

    def materialize_solution(self, solution: Any) -> tuple[dict, list[TestCasePart]]:
        spec = self.spec
        pre = self._base_state()
        scenario = str(solution.scenario)
        index = _VALIDATOR_COUNT if scenario == "OUT_OF_RANGE" else _VALIDATOR_INDEX
        signed_change = get_signed_address_change(spec, pre, validator_index=index)

        if scenario != "OUT_OF_RANGE":
            validator = pre.validators[index]
            validator.withdrawal_credentials = spec.Bytes32(
                spec.BLS_WITHDRAWAL_PREFIX + spec.sha256(signed_change.message.from_bls_pubkey)[1:]
            )
            if scenario == "NON_BLS_CREDENTIAL":
                validator.withdrawal_credentials = spec.Bytes32(
                    spec.ETH1_ADDRESS_WITHDRAWAL_PREFIX + b"\x00" * 31
                )
            elif scenario == "PUBKEY_MISMATCH":
                validator.withdrawal_credentials = spec.Bytes32(
                    spec.BLS_WITHDRAWAL_PREFIX + b"\x00" * 31
                )
            elif scenario == "INVALID_SIGNATURE":
                signed_change.signature = spec.BLSSignature()
            elif scenario != "VALID":
                raise ValueError(f"unknown BLS-to-execution-change scenario: {scenario}")

        post = pre.copy()
        try:
            spec.process_bls_to_execution_change(post, signed_change)
        except (AssertionError, IndexError):
            post = None

        claimed = {
            name: bool(value) if isinstance(value := getattr(solution, name), bool) else str(value)
            for name in _DIMS
            if name != "scenario"
        }
        meta = {
            "description": f"process_bls_to_execution_change: {claimed['outcome']}",
            "bls_setting": 1,
            "claimed": claimed,
        }
        parts = [
            ("pre", "ssz", pre.encode_bytes()),
            ("address_change", "ssz", signed_change.encode_bytes()),
        ]
        if post is not None:
            parts.append(("post", "ssz", post.encode_bytes()))
        return meta, parts
