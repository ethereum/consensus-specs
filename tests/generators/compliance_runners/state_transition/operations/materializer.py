"""Materialize the minimal Gloas ``process_operations`` coverage frontier."""

from __future__ import annotations

from typing import Any, TYPE_CHECKING

from eth_consensus_specs.test.helpers.block import build_empty_block
from eth_consensus_specs.test.helpers.genesis import create_genesis_state
from tests.generators.compliance_runners.state_transition.materializer import Materializer

if TYPE_CHECKING:
    from tests.generators.compliance_runners.gen_base.gen_typing import TestCasePart


_LIMITS = (
    (
        "proposer_slashings",
        "ProposerSlashing",
        "MAX_PROPOSER_SLASHINGS",
        "proposer_slashings_within_limit",
    ),
    (
        "attester_slashings",
        "AttesterSlashing",
        "MAX_ATTESTER_SLASHINGS_ELECTRA",
        "attester_slashings_within_limit",
    ),
    ("attestations", "Attestation", "MAX_ATTESTATIONS_ELECTRA", "attestations_within_limit"),
    (
        "voluntary_exits",
        "SignedVoluntaryExit",
        "MAX_VOLUNTARY_EXITS",
        "voluntary_exits_within_limit",
    ),
    (
        "bls_to_execution_changes",
        "SignedBLSToExecutionChange",
        "MAX_BLS_TO_EXECUTION_CHANGES",
        "bls_to_execution_changes_within_limit",
    ),
    (
        "payload_attestations",
        "PayloadAttestation",
        "MAX_PAYLOAD_ATTESTATIONS",
        "payload_attestations_within_limit",
    ),
)
_GATES = ("deposits_empty",) + tuple(item[3] for item in _LIMITS)
_DIMS = [*_GATES, "accepted", "outcome"]


def _bool(solution: Any, name: str, default: bool = True) -> bool:
    value = getattr(solution, name, default)
    return bool(value)


class OperationsMaterializer(Materializer):
    runner_name = "sanity"
    handler_name = "blocks"

    def _base_state(self) -> Any:
        spec = self.spec
        return create_genesis_state(
            spec,
            validator_balances=[spec.MAX_EFFECTIVE_BALANCE] * 64,
            activation_threshold=spec.MAX_EFFECTIVE_BALANCE,
        )

    def materialize_solution(self, solution: Any) -> tuple[dict, list[TestCasePart]]:
        spec = self.spec
        pre = self._base_state()
        block = build_empty_block(spec, pre, slot=1)
        body = block.body
        gates = {name: _bool(solution, name) for name in _GATES}
        requested_acceptance = getattr(solution, "accepted", None)
        accepted = (
            bool(requested_acceptance)
            if requested_acceptance is not None
            else all(gates.values())
        )

        # A partial exceptional obligation must still select a failing gate.
        # The first unspecified gate is the least surprising deterministic
        # witness and preserves every explicitly requested value.
        if not accepted and all(gates.values()):
            gates[_GATES[0]] = False

        if not gates["deposits_empty"]:
            body.deposits.append(spec.Deposit())
        for field, operation_type, limit_name, gate in _LIMITS:
            if not gates[gate]:
                values = getattr(body, field)
                for _ in range(int(getattr(spec, limit_name)) + 1):
                    values.append(getattr(spec, operation_type)())

        signed_block = spec.SignedBeaconBlock(message=block)
        post = pre.copy()
        try:
            spec.state_transition(post, signed_block, validate_result=False)
        except (AssertionError, IndexError):
            post = None

        outcome = "ACCEPT_EMPTY"
        if not gates["deposits_empty"]:
            outcome = "REJECT_DEPOSITS_NONZERO"
        else:
            for _, _, _, gate in _LIMITS:
                if not gates[gate]:
                    outcome = {
                        "proposer_slashings_within_limit": "REJECT_PROPOSER_SLASHINGS_OVER_LIMIT",
                        "attester_slashings_within_limit": "REJECT_ATTESTER_SLASHINGS_OVER_LIMIT",
                        "attestations_within_limit": "REJECT_ATTESTATIONS_OVER_LIMIT",
                        "voluntary_exits_within_limit": "REJECT_VOLUNTARY_EXITS_OVER_LIMIT",
                        "bls_to_execution_changes_within_limit": "REJECT_BLS_TO_EXECUTION_CHANGES_OVER_LIMIT",
                        "payload_attestations_within_limit": "REJECT_PAYLOAD_ATTESTATIONS_OVER_LIMIT",
                    }[gate]
                    break

        claimed = {name: gates[name] for name in _GATES}
        # Keep the requested outcome authoritative. Validation must detect a
        # transition that does not realize this obligation.
        claimed.update(accepted=accepted, outcome=outcome)
        meta = {
            "description": f"process_operations: {outcome}",
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


MATERIALIZER = OperationsMaterializer
