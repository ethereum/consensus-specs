"""Materialize aspect-model solutions into process_deposit_request cases.

The simplest handler — no gates, no signature check; it always appends a
PendingDeposit and, if the start index is unset, sets it. The request fields are
copied verbatim, so validation's substantive check is output correctness.

Spec: specs/electra/beacon-chain.md process_deposit_request (inherited by gloas).
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

NUM_VALIDATORS = 64
REQUEST_INDEX = 5
WITHDRAWAL_CREDENTIALS = b"\x01" + b"\x00" * 11 + b"\x11" * 20
SIGNATURE = b"\x00" * 96  # not verified by this handler

_DIMS = ["amount_nonzero", "pubkey_is_existing_validator", "outcome"]


def _b(sol: Any, n: str) -> bool:
    return bool(getattr(sol, n))


def _s(sol: Any, n: str) -> str:
    return str(getattr(sol, n))


class DepositRequestMaterializer:
    def __init__(self, spec: Any, model_path: Path, fork_name="gloas", preset_name="minimal"):
        self.spec = spec
        self.model_path = model_path
        self.fork_name = fork_name
        self.preset_name = preset_name

    def materialize_solution(self, sol: Any) -> tuple[Any, Any, Any, dict]:
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
        return pre, request, post, claimed

    def write_case(self, dumper: Dumper, output_dir: Path, index: int, sol: Any) -> None:
        pre, request, post, claimed = self.materialize_solution(sol)
        case_name = f"case_{index:04d}"
        test_case = TestCase(
            fork_name=self.fork_name, preset_name=self.preset_name,
            runner_name="operations", handler_name="deposit_request",
            suite_name="main", case_name=case_name,
        )
        test_case.set_output_dir(str(output_dir))
        case_parts: list[TestCasePart] = [
            ("pre", "ssz", pre.encode_bytes()),  # type: ignore
            ("deposit_request", "ssz", request.encode_bytes()),  # type: ignore
            ("post", "ssz", post.encode_bytes()),  # type: ignore
        ]
        meta = {"description": f"process_deposit_request: {claimed['outcome']}"}
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
