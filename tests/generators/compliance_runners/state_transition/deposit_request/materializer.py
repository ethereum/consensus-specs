"""Materialize aspect-model solutions into process_deposit_request cases.

The simplest handler — no gates, no signature check; it always appends a
PendingDeposit and, if the start index is unset, sets it. The request fields are
copied verbatim, so validation's substantive check is output correctness.

Spec: specs/electra/beacon-chain.md process_deposit_request (inherited by gloas).
"""
from __future__ import annotations

from typing import Any

from eth_consensus_specs.test.helpers.genesis import create_genesis_state
from eth_consensus_specs.test.helpers.keys import pubkeys

from ...gen_base.gen_typing import TestCasePart
from tests.generators.compliance_runners.state_transition.materializer import Materializer

NUM_VALIDATORS = 64
REQUEST_INDEX = 5
WITHDRAWAL_CREDENTIALS = b"\x01" + b"\x00" * 11 + b"\x11" * 20
SIGNATURE = b"\x00" * 96  # not verified by this handler

_DIMS = ["amount_nonzero", "pubkey_is_existing_validator", "outcome"]


def _b(sol: Any, n: str) -> bool:
    return bool(getattr(sol, n))


def _s(sol: Any, n: str) -> str:
    return str(getattr(sol, n))


class DepositRequestMaterializer(Materializer):
    runner_name = "operations"
    handler_name = "deposit_request"

    def materialize_solution(self, sol: Any) -> tuple[dict, list[TestCasePart]]:
        spec = self.spec
        pre = create_genesis_state(
            spec, validator_balances=[spec.MAX_EFFECTIVE_BALANCE] * NUM_VALIDATORS,
            activation_threshold=spec.MAX_EFFECTIVE_BALANCE,
        )
        pubkey = pre.validators[0].pubkey if _b(sol, "pubkey_is_existing_validator") else pubkeys[NUM_VALIDATORS]
        amount = spec.MIN_ACTIVATION_BALANCE if _b(sol, "amount_nonzero") else 0
        request = spec.DepositRequest(
            pubkey=spec.BLSPubkey(pubkey),
            withdrawal_credentials=spec.Bytes32(WITHDRAWAL_CREDENTIALS),
            amount=spec.Gwei(amount),
            signature=spec.BLSSignature(SIGNATURE),
            index=spec.Uint64(REQUEST_INDEX),
        )
        post = pre.copy()
        spec.process_deposit_request(post, request)  # never raises

        claimed = {n: (_b(sol, n) if isinstance(getattr(sol, n), bool) else _s(sol, n)) for n in _DIMS}
        meta = {"description": f"process_deposit_request: {claimed['outcome']}", "claimed": claimed}
        parts = [
            ("pre", "ssz", pre.encode_bytes()),
            ("deposit_request", "ssz", request.encode_bytes()),
            ("post", "ssz", post.encode_bytes()),
        ]
        return meta, parts
