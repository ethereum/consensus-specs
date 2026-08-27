"""Materialize aspect-model solutions into process_consolidation_request cases.

The most involved materializer: two validators (source + target), a churn gate
realized by sizing the active validator set (64 -> sufficient, 32 -> ==MIN, i.e.
insufficient), and two queue fills. No BLS. Never raises, so `post` is always
present.

Spec: specs/electra/beacon-chain.md process_consolidation_request (inherited by gloas).
"""

from __future__ import annotations

from typing import Any, TYPE_CHECKING

from eth_consensus_specs.test.helpers.genesis import create_genesis_state
from eth_consensus_specs.test.helpers.keys import pubkeys
from tests.generators.compliance_runners.state_transition.materializer import Materializer

if TYPE_CHECKING:
    from generators.compliance_runners.gen_base.gen_typing import TestCasePart

N_SUFFICIENT = 64  # get_consolidation_churn_limit > MIN_ACTIVATION_BALANCE
N_INSUFFICIENT = 32  # get_consolidation_churn_limit == MIN_ACTIVATION_BALANCE
SOURCE_INDEX = 0
TARGET_INDEX = 1
CURRENT_EPOCH = 70
ADDRESS = b"\x22" * 20
OTHER_ADDRESS = b"\x33" * 20

_SRC_PREFIX = {"CRED_BLS": b"\x00", "CRED_ETH1": b"\x01", "CRED_COMPOUNDING": b"\x02"}

_DIMS = [
    "same_source_target",
    "pending_consolidations_full",
    "sufficient_consolidation_churn",
    "validator_pubkey_found",
    "validator_credential",
    "source_address_matches",
    "validator_active",
    "validator_exiting",
    "validator_old_enough",
    "has_pending_partial_withdrawal",
    "target_found",
    "target_credential",
    "target_active",
    "target_exiting",
    "validator_has_execution_credential",
    "validator_has_compounding_credential",
    "target_has_compounding_credential",
    "outcome",
    "state_effected",
]


def _s(sol: Any, n: str) -> str:
    return str(getattr(sol, n))


def _b(sol: Any, n: str) -> bool:
    return bool(getattr(sol, n))


class ConsolidationRequestMaterializer(Materializer):
    runner_name = "operations"
    handler_name = "consolidation_request"

    def _epochs(self, active: bool, exiting: bool, old_enough: bool) -> tuple[int, int]:
        far = int(self.spec.FAR_FUTURE_EPOCH)
        activation = 0 if old_enough else CURRENT_EPOCH - 10
        if active:
            exit_epoch = (CURRENT_EPOCH + 10) if exiting else far
        elif exiting:
            exit_epoch = CURRENT_EPOCH - 1
        else:
            activation, exit_epoch = CURRENT_EPOCH + 10, far
        return activation, exit_epoch

    def _set_validator(
        self, v: Any, prefix: bytes, active: bool, exiting: bool, old_enough: bool
    ) -> None:
        spec = self.spec
        v.withdrawal_credentials = spec.Bytes32(prefix + b"\x00" * 11 + ADDRESS)
        activation, exit_epoch = self._epochs(active, exiting, old_enough)
        v.activation_epoch = spec.Epoch(activation)
        v.exit_epoch = spec.Epoch(exit_epoch)

    def materialize_solution(self, sol: Any) -> tuple[dict, list[TestCasePart]]:
        spec = self.spec
        n = N_SUFFICIENT if _b(sol, "sufficient_consolidation_churn") else N_INSUFFICIENT
        pre = create_genesis_state(
            spec,
            validator_balances=[spec.MAX_EFFECTIVE_BALANCE] * n,
            activation_threshold=spec.MAX_EFFECTIVE_BALANCE,
        )
        pre.slot = spec.Slot(CURRENT_EPOCH * spec.SLOTS_PER_EPOCH)
        absent_source = pubkeys[n]
        absent_target = pubkeys[n + 1]

        same = _b(sol, "same_source_target")
        source_found = _b(sol, "validator_pubkey_found")

        # ---- source validator --------------------------------------------------
        if source_found:
            self._set_validator(
                pre.validators[SOURCE_INDEX],
                _SRC_PREFIX[_s(sol, "validator_credential")],
                _s(sol, "validator_active") == "T",
                _s(sol, "validator_exiting") == "T",
                _s(sol, "validator_old_enough") == "T",
            )
            source_pubkey = pre.validators[SOURCE_INDEX].pubkey
            source_address = ADDRESS if _s(sol, "source_address_matches") == "T" else OTHER_ADDRESS
        else:
            source_pubkey = absent_source
            source_address = ADDRESS

        # ---- target validator (consolidation path only) ------------------------
        if same:
            target_pubkey = source_pubkey
        elif _s(sol, "target_found") == "T":
            self._set_validator(
                pre.validators[TARGET_INDEX],
                _SRC_PREFIX[_s(sol, "target_credential")],
                _s(sol, "target_active") == "T",
                _s(sol, "target_exiting") == "T",
                old_enough=True,
            )
            target_pubkey = pre.validators[TARGET_INDEX].pubkey
        else:
            target_pubkey = absent_target

        # ---- source pending partial withdrawal ---------------------------------
        if source_found and _s(sol, "has_pending_partial_withdrawal") == "T":
            pre.pending_partial_withdrawals.append(
                spec.PendingPartialWithdrawal(
                    validator_index=spec.ValidatorIndex(SOURCE_INDEX),
                    amount=spec.Gwei(1),
                    withdrawable_epoch=spec.Epoch(CURRENT_EPOCH),
                )
            )

        # ---- pending consolidations queue --------------------------------------
        if _b(sol, "pending_consolidations_full"):
            pre.pending_consolidations = spec.PendingConsolidations(
                data=[
                    spec.PendingConsolidation(
                        source_index=spec.ValidatorIndex(2),
                        target_index=spec.ValidatorIndex(3),
                    )
                    for _ in range(int(spec.PENDING_CONSOLIDATIONS_LIMIT))
                ]
            )

        request = spec.ConsolidationRequest(
            source_address=spec.ExecutionAddress(source_address),
            source_pubkey=spec.BLSPubkey(source_pubkey),
            target_pubkey=spec.BLSPubkey(target_pubkey),
        )
        post = pre.copy()
        spec.process_consolidation_request(post, request)  # never raises

        claimed = {
            k: (_b(sol, k) if isinstance(getattr(sol, k), bool) else _s(sol, k)) for k in _DIMS
        }
        meta = {
            "description": f"process_consolidation_request: {claimed['outcome']}",
            "claimed": claimed,
        }
        parts = [
            ("pre", "ssz", pre.encode_bytes()),
            ("consolidation_request", "ssz", request.encode_bytes()),
            ("post", "ssz", post.encode_bytes()),
        ]
        return meta, parts
