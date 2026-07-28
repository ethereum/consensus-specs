"""Materialize aspect-model solutions into process_builder_deposit_request cases.

Realizes each applicable coverage dimension into a concrete pre /
BuilderDepositRequest / post vector (real BLS deposit signatures) and serializes
the solution. The operation never raises, so `post` is always present.

Spec: specs/gloas/beacon-chain.md process_builder_deposit_request.
"""
from __future__ import annotations

import shutil
from pathlib import Path
from typing import Any

from eth_consensus_specs.test.utils.dumper import Dumper
from eth_consensus_specs.test.helpers.genesis import create_genesis_state
from eth_consensus_specs.test.helpers.keys import builder_pubkeys, builder_pubkey_to_privkey
from eth_consensus_specs.utils import bls

from ...gen_base.gen_typing import TestCase, TestCaseResult, TestCasePart
from ...gen_base.output import dump_test_case_result

REQUEST_PUBKEY = builder_pubkeys[0]
WRONG_PUBKEY = builder_pubkeys[1]
EPOCHS_PAST_GENESIS = 10

_DIMS = [
    "wc_is_builder_prefix", "builder_pubkey_found", "builder_signature_valid", "amount_nonzero",
    "builder_withdrawable_epoch_set", "builder_balance_zero",
    "reset_applies", "builder_credited", "outcome",
]


def _s(sol: Any, n: str) -> str:
    return str(getattr(sol, n))


def _b(sol: Any, n: str) -> bool:
    return bool(getattr(sol, n))


class BuilderDepositRequestMaterializer:
    def __init__(self, spec: Any, model_path: Path, fork_name="gloas", preset_name="minimal"):
        self.spec = spec
        self.model_path = model_path
        self.fork_name = fork_name
        self.preset_name = preset_name

    def _sign(self, request: Any, privkey: int) -> Any:
        spec = self.spec
        message = spec.DepositMessage(
            pubkey=request.pubkey,
            withdrawal_credentials=request.withdrawal_credentials,
            amount=request.amount,
        )
        root = spec.compute_signing_root(message, spec.compute_domain(spec.DOMAIN_BUILDER_DEPOSIT))
        return bls.Sign(privkey, root)

    def _base_state(self) -> Any:
        spec = self.spec
        state = create_genesis_state(
            spec, validator_balances=[spec.MAX_EFFECTIVE_BALANCE] * 64,
            activation_threshold=spec.MAX_EFFECTIVE_BALANCE,
        )
        state.builders = type(state.builders)()
        state.slot = spec.Slot(EPOCHS_PAST_GENESIS * spec.SLOTS_PER_EPOCH)
        return state

    def materialize_solution(self, sol: Any) -> tuple[Any, Any, Any, dict]:
        spec = self.spec
        found = _b(sol, "builder_pubkey_found")
        pre = self._base_state()
        current_epoch = int(spec.get_current_epoch(pre))
        address_tail = spec.hash(REQUEST_PUBKEY)[12:]

        if found:
            wset = _s(sol, "builder_withdrawable_epoch_set") == "T"
            bzero = _s(sol, "builder_balance_zero") == "T"
            pre.builders.append(
                spec.Builder(
                    pubkey=spec.BLSPubkey(REQUEST_PUBKEY),
                    version=spec.PAYLOAD_BUILDER_VERSION,
                    execution_address=spec.ExecutionAddress(address_tail),
                    balance=spec.Gwei(0) if bzero else spec.Gwei(spec.MIN_ACTIVATION_BALANCE),
                    deposit_epoch=spec.Epoch(0),
                    withdrawable_epoch=spec.Epoch(current_epoch) if wset else spec.FAR_FUTURE_EPOCH,
                )
            )

        if _b(sol, "wc_is_builder_prefix"):
            wc = spec.BUILDER_WITHDRAWAL_PREFIX + b"\x00" * 11 + address_tail
        else:
            wc = b"\x01" + b"\x00" * 11 + address_tail
        amount = spec.MIN_ACTIVATION_BALANCE if _b(sol, "amount_nonzero") else 0

        request = spec.BuilderDepositRequest(
            pubkey=spec.BLSPubkey(REQUEST_PUBKEY),
            withdrawal_credentials=spec.Bytes32(wc),
            amount=spec.Gwei(amount),
        )
        signer = REQUEST_PUBKEY if _s(sol, "builder_signature_valid") == "T" else WRONG_PUBKEY
        request.signature = self._sign(request, builder_pubkey_to_privkey[signer])

        post = pre.copy()
        spec.process_builder_deposit_request(post, request)  # never raises

        claimed = {n: (_b(sol, n) if isinstance(getattr(sol, n), bool) else _s(sol, n)) for n in _DIMS}
        return pre, request, post, claimed

    def write_case(self, dumper: Dumper, output_dir: Path, index: int, sol: Any) -> None:
        pre, request, post, claimed = self.materialize_solution(sol)
        case_name = f"case_{index:04d}"
        test_case = TestCase(
            fork_name=self.fork_name, preset_name=self.preset_name,
            runner_name="operations", handler_name="builder_deposit_request",
            suite_name="main", case_name=case_name,
        )
        test_case.set_output_dir(str(output_dir))
        case_parts: list[TestCasePart] = [
            ("pre", "ssz", pre.encode_bytes()),  # type: ignore
            ("builder_deposit_request", "ssz", request.encode_bytes()),  # type: ignore
            ("post", "ssz", post.encode_bytes()),  # type: ignore
        ]
        meta = {"description": f"process_builder_deposit_request: {claimed['outcome']}", "bls_setting": 1}
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
