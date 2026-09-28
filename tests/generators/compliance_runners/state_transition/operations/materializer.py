"""Materialize the minimal Gloas ``process_operations`` coverage frontier."""

from __future__ import annotations

from typing import Any, TYPE_CHECKING

from eth_consensus_specs.test.helpers.block import build_empty_block
from eth_consensus_specs.test.helpers.genesis import create_genesis_state
from tests.generators.compliance_runners.state_transition.materializer import Materializer

from .witness import complete_obligation, GATES as _GATES

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
_DIMS = [*_GATES, "accepted", "outcome"]


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
        assignment = complete_obligation(vars(solution))
        gates = {name: assignment[name] for name in _GATES}
        accepted = assignment["accepted"]
        body.graffiti = spec.Bytes32(self.rng.getrandbits(256).to_bytes(32, "big"))

        if not gates["deposits_empty"]:
            deposit = spec.Deposit()
            deposit.data.pubkey = spec.BLSPubkey(self._random_bytes(deposit.data.pubkey))
            deposit.data.withdrawal_credentials = spec.Bytes32(
                self._random_bytes(deposit.data.withdrawal_credentials)
            )
            deposit.data.amount = type(deposit.data.amount)(self.rng.getrandbits(64))
            deposit.data.signature = spec.BLSSignature(self._random_bytes(deposit.data.signature))
            for index in range(len(deposit.proof)):
                deposit.proof[index] = type(deposit.proof[index])(
                    self._random_bytes(deposit.proof[index])
                )
            body.deposits.append(deposit)
        for field, operation_type, limit_name, gate in _LIMITS:
            if not gates[gate]:
                values = getattr(body, field)
                for _ in range(int(getattr(spec, limit_name)) + 1):
                    operation = getattr(spec, operation_type)()
                    self._randomize_operation(operation)
                    values.append(operation)

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

    def _random_bytes(self, value: Any) -> bytes:
        return self.rng.getrandbits(len(value) * 8).to_bytes(len(value), "big")

    def _randomize_operation(self, operation: Any) -> None:
        spec = self.spec
        if hasattr(operation, "signed_header_1") and hasattr(operation, "signed_header_2"):
            proposer_index = self.rng.randrange(64)
            body_root = self.rng.getrandbits(256).to_bytes(32, "big")
            for header, root in (
                (operation.signed_header_1, body_root),
                (operation.signed_header_2, bytes([body_root[0] ^ 1]) + body_root[1:]),
            ):
                header.message.proposer_index = spec.ValidatorIndex(proposer_index)
                header.message.body_root = type(header.message.body_root)(root)
        for field in ("signed_header_1", "signed_header_2", "attestation_1", "attestation_2", "message"):
            nested = getattr(operation, field, None)
            if nested is None:
                continue
            if hasattr(nested, "signature"):
                nested.signature = type(nested.signature)(self._random_bytes(nested.signature))
            message = getattr(nested, "message", nested)
            if hasattr(message, "proposer_index") and not hasattr(operation, "signed_header_1"):
                message.proposer_index = type(message.proposer_index)(self.rng.randrange(64))
            if hasattr(message, "validator_index"):
                message.validator_index = type(message.validator_index)(self.rng.randrange(64))
            if hasattr(message, "beacon_block_root"):
                message.beacon_block_root = type(message.beacon_block_root)(
                    self._random_bytes(message.beacon_block_root)
                )
        if hasattr(operation, "signature"):
            operation.signature = type(operation.signature)(self._random_bytes(operation.signature))


MATERIALIZER = OperationsMaterializer
