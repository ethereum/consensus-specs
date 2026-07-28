"""Materialize aspect-model solutions into process_consolidation_request cases.

The most involved materializer: two validators (source + target), a churn gate
realized by sizing the active validator set (64 -> sufficient, 32 -> ==MIN, i.e.
insufficient), and two queue fills. No BLS. Never raises, so `post` is always
present.

Spec: specs/electra/beacon-chain.md process_consolidation_request (inherited by gloas).
"""
from __future__ import annotations

import shutil
from pathlib import Path
from typing import Any

from eth_consensus_specs.test.utils.dumper import Dumper
from eth_consensus_specs.test.helpers.genesis import create_genesis_state
from eth_consensus_specs.test.helpers.keys import pubkeys

from ...gen_base.gen_typing import TestCase, TestCaseResult, TestCasePart
from ...gen_base.output import dump_test_case_result

N_SUFFICIENT = 64   # get_consolidation_churn_limit > MIN_ACTIVATION_BALANCE
N_INSUFFICIENT = 32  # get_consolidation_churn_limit == MIN_ACTIVATION_BALANCE
SOURCE_INDEX = 0
TARGET_INDEX = 1
CURRENT_EPOCH = 70
ADDRESS = b"\x22" * 20
OTHER_ADDRESS = b"\x33" * 20

_SRC_PREFIX = {"CRED_BLS": b"\x00", "CRED_ETH1": b"\x01", "CRED_COMPOUNDING": b"\x02"}

_DIMS = [
    "same_source_target", "pending_consolidations_full", "sufficient_consolidation_churn",
    "validator_pubkey_found", "validator_credential", "source_address_matches",
    "validator_active", "validator_exiting", "validator_old_enough", "has_pending_partial_withdrawal",
    "target_found", "target_credential", "target_active", "target_exiting",
    "validator_has_execution_credential", "validator_has_compounding_credential",
    "target_has_compounding_credential",
    "outcome", "state_effected",
]


def _s(sol: Any, n: str) -> str:
    return str(getattr(sol, n))


def _b(sol: Any, n: str) -> bool:
    return bool(getattr(sol, n))


class ConsolidationRequestMaterializer:
    def __init__(self, spec: Any, model_path: Path, fork_name="gloas", preset_name="minimal"):
        self.spec = spec
        self.model_path = model_path
        self.fork_name = fork_name
        self.preset_name = preset_name

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

    def _set_validator(self, v: Any, prefix: bytes, active: bool, exiting: bool, old_enough: bool) -> None:
        spec = self.spec
        v.withdrawal_credentials = spec.Bytes32(prefix + b"\x00" * 11 + ADDRESS)
        activation, exit_epoch = self._epochs(active, exiting, old_enough)
        v.activation_epoch = spec.Epoch(activation)
        v.exit_epoch = spec.Epoch(exit_epoch)

    def materialize_solution(self, sol: Any) -> tuple[Any, Any, Any, dict]:
        spec = self.spec
        n = N_SUFFICIENT if _b(sol, "sufficient_consolidation_churn") else N_INSUFFICIENT
        pre = create_genesis_state(
            spec, validator_balances=[spec.MAX_EFFECTIVE_BALANCE] * n,
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
                pre.validators[SOURCE_INDEX], _SRC_PREFIX[_s(sol, "validator_credential")],
                _s(sol, "validator_active") == "T", _s(sol, "validator_exiting") == "T",
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
                pre.validators[TARGET_INDEX], _SRC_PREFIX[_s(sol, "target_credential")],
                _s(sol, "target_active") == "T", _s(sol, "target_exiting") == "T", True,
            )
            target_pubkey = pre.validators[TARGET_INDEX].pubkey
        else:
            target_pubkey = absent_target

        # ---- source pending partial withdrawal ---------------------------------
        if source_found and _s(sol, "has_pending_partial_withdrawal") == "T":
            pre.pending_partial_withdrawals.append(spec.PendingPartialWithdrawal(
                validator_index=spec.ValidatorIndex(SOURCE_INDEX), amount=spec.Gwei(1),
                withdrawable_epoch=spec.Epoch(CURRENT_EPOCH),
            ))

        # ---- pending consolidations queue --------------------------------------
        if _b(sol, "pending_consolidations_full"):
            pre.pending_consolidations = type(pre.pending_consolidations)(*[
                spec.PendingConsolidation(source_index=spec.ValidatorIndex(2),
                                          target_index=spec.ValidatorIndex(3))
                for _ in range(int(spec.PENDING_CONSOLIDATIONS_LIMIT))
            ])

        request = spec.ConsolidationRequest(
            source_address=spec.ExecutionAddress(source_address),
            source_pubkey=spec.BLSPubkey(source_pubkey),
            target_pubkey=spec.BLSPubkey(target_pubkey),
        )
        post = pre.copy()
        spec.process_consolidation_request(post, request)  # never raises

        claimed = {k: (_b(sol, k) if isinstance(getattr(sol, k), bool) else _s(sol, k)) for k in _DIMS}
        return pre, request, post, claimed

    def write_case(self, dumper: Dumper, output_dir: Path, index: int, sol: Any) -> None:
        pre, request, post, claimed = self.materialize_solution(sol)
        case_name = f"case_{index:04d}"
        test_case = TestCase(
            fork_name=self.fork_name, preset_name=self.preset_name,
            runner_name="operations", handler_name="consolidation_request",
            suite_name="main", case_name=case_name,
        )
        test_case.set_output_dir(str(output_dir))
        case_parts: list[TestCasePart] = [
            ("pre", "ssz", pre.encode_bytes()),  # type: ignore
            ("consolidation_request", "ssz", request.encode_bytes()),  # type: ignore
            ("post", "ssz", post.encode_bytes()),  # type: ignore
        ]
        meta = {"description": f"process_consolidation_request: {claimed['outcome']}"}
        dump_test_case_result(TestCaseResult(test_case=test_case, meta=meta, case_parts=case_parts), dumper)
        dumper.dump_data(test_case.dir, "dimensions", {"case": case_name, "claimed": claimed})

    def materialize_reps(self, output_dir: Path, reps: list) -> int:
        if output_dir.exists():
            shutil.rmtree(output_dir)
        output_dir.mkdir(parents=True, exist_ok=True)
        dumper = Dumper()
        for i, sol in enumerate(reps):
            self.write_case(dumper, output_dir, i, sol)
        print(f"Generated {len(reps)} test cases in {output_dir}")
        return len(reps)
