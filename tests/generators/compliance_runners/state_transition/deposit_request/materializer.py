"""Materialize aspect-model solutions into process_deposit_request cases.

The simplest handler — no gates, no signature check; it always appends a
PendingDeposit and, if the start index is unset, sets it. The request fields are
copied verbatim, so validation's substantive check is output correctness.

Spec: specs/electra/beacon-chain.md process_deposit_request (inherited by gloas).
"""
from __future__ import annotations

from typing import Any

from eth_consensus_specs.test.helpers.genesis import create_genesis_state
from eth_consensus_specs.test.helpers.deposits import build_deposit_data
from eth_consensus_specs.test.helpers.keys import privkeys, pubkeys

from ...gen_base.gen_typing import TestCasePart
from tests.generators.compliance_runners.state_transition.materializer import Materializer

NUM_VALIDATORS = 64
REQUEST_INDEX = 5
INVALID_SIGNATURE = b"\x00" * 96  # not verified by this handler

_DIMS = [
    "amount_profile",
    "amount_nonzero",
    "withdrawal_credentials_profile",
    "signature_profile",
    "pubkey_is_existing_validator",
]


def _b(sol: Any, n: str) -> bool:
    return bool(getattr(sol, n))


def _s(sol: Any, n: str) -> str:
    return str(getattr(sol, n))


def _amount(spec: Any, profile: str) -> int:
    return {
        "ZERO": 0,
        "MINIMUM": int(spec.MIN_DEPOSIT_AMOUNT),
        "ACTIVATION": int(spec.MIN_ACTIVATION_BALANCE),
        "ABOVE_ACTIVATION": int(spec.MIN_ACTIVATION_BALANCE + spec.EFFECTIVE_BALANCE_INCREMENT),
    }[profile]


def _withdrawal_credentials(spec: Any, profile: str) -> bytes:
    prefix = {
        "BLS": spec.BLS_WITHDRAWAL_PREFIX,
        "ETH1": spec.ETH1_ADDRESS_WITHDRAWAL_PREFIX,
        "COMPOUNDING": spec.COMPOUNDING_WITHDRAWAL_PREFIX,
        "BUILDER": spec.BUILDER_WITHDRAWAL_PREFIX,
    }[profile]
    return prefix + b"\x00" * 11 + b"\x11" * 20


class DepositRequestMaterializer(Materializer):
    runner_name = "operations"
    handler_name = "deposit_request"

    def materialize_solution(self, sol: Any) -> tuple[dict, list[TestCasePart]]:
        spec = self.spec
        pre = create_genesis_state(
            spec, validator_balances=[spec.MAX_EFFECTIVE_BALANCE] * NUM_VALIDATORS,
            activation_threshold=spec.MAX_EFFECTIVE_BALANCE,
        )
        key_index = 0 if _b(sol, "pubkey_is_existing_validator") else NUM_VALIDATORS
        pubkey = pre.validators[key_index].pubkey if key_index == 0 else pubkeys[key_index]
        amount_profile = _s(sol, "amount_profile")
        credentials_profile = _s(sol, "withdrawal_credentials_profile")
        signature_profile = _s(sol, "signature_profile")
        amount = _amount(spec, amount_profile)
        withdrawal_credentials = _withdrawal_credentials(spec, credentials_profile)
        deposit_data = build_deposit_data(
            spec,
            pubkey,
            privkeys[key_index],
            amount,
            withdrawal_credentials,
            signed=signature_profile == "VALID",
        )
        request = spec.DepositRequest(
            pubkey=spec.BLSPubkey(pubkey),
            withdrawal_credentials=spec.Bytes32(withdrawal_credentials),
            amount=spec.Gwei(amount),
            signature=(
                deposit_data.signature
                if signature_profile == "VALID"
                else spec.BLSSignature(INVALID_SIGNATURE)
            ),
            index=spec.Uint64(REQUEST_INDEX),
        )
        post = pre.copy()
        spec.process_deposit_request(post, request)  # never raises

        claimed = {n: (_b(sol, n) if isinstance(getattr(sol, n), bool) else _s(sol, n)) for n in _DIMS}
        meta = {"description": "process_deposit_request", "claimed": claimed}
        parts = [
            ("pre", "ssz", pre.encode_bytes()),
            ("deposit_request", "ssz", request.encode_bytes()),
            ("post", "ssz", post.encode_bytes()),
        ]
        return meta, parts
