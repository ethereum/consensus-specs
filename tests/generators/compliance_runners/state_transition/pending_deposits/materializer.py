"""Materialize Gloas ``process_pending_deposits`` epoch-processing vectors."""

from __future__ import annotations

import shutil
from typing import Any, TYPE_CHECKING

from eth_consensus_specs.test.helpers.deposits import prepare_pending_deposit
from eth_consensus_specs.test.helpers.genesis import create_genesis_state
from eth_consensus_specs.test.utils.dumper import Dumper
from tests.generators.compliance_runners.gen_base.gen_typing import TestCase, TestCaseResult
from tests.generators.compliance_runners.gen_base.output import dump_test_case_result

if TYPE_CHECKING:
    from pathlib import Path

_DIMS = [
    "queue_layout",
    "secondary_role",
    "primary_reached",
    "primary_role",
    "deposit_signature_valid",
    "validator_pubkey_found",
    "validator_active",
    "validator_exiting",
    "withdrawable_epoch_to_next_epoch",
    "initial_churn",
    "primary_amount_to_available",
    "second_amount_to_remaining",
    "churn_effect",
    "outcome",
]
# Minimal Gloas reaches the activation cap at 64 validators.  Twice that count
# makes exit churn strictly larger, so GT cases distinguish activation-only
# deposit churn from the uncapped exit churn.
NUM_VALIDATORS = 128


class PendingDepositsMaterializer:
    def __init__(self, spec: Any, fork_name: str = "gloas", preset_name: str = "minimal"):
        self.spec = spec
        self.fork_name = fork_name
        self.preset_name = preset_name

    def _base_state(self) -> Any:
        state = create_genesis_state(
            self.spec,
            validator_balances=[self.spec.MAX_EFFECTIVE_BALANCE] * NUM_VALIDATORS,
            activation_threshold=self.spec.MAX_EFFECTIVE_BALANCE,
        )
        # Pending deposits can be unfinalized only after the chain has advanced.
        # Keep finality at genesis: slot 1 is then in the past but unfinalized.
        state.slot = self.spec.Slot(self.spec.SLOTS_PER_EPOCH)
        return state

    def _deposit(
        self,
        state: Any,
        validator_index: int,
        amount: Any,
        *,
        signed: bool = True,
        slot: Any = None,
    ):
        return prepare_pending_deposit(
            self.spec,
            validator_index,
            amount,
            signed=signed,
            slot=self.spec.GENESIS_SLOT if slot is None else slot,
        )

    def materialize_solution(self, solution: Any) -> tuple[Any, Any, dict[str, str]]:
        spec = self.spec
        pre = self._base_state()
        layout = str(solution.queue_layout)
        role = str(solution.primary_role)
        carry = str(solution.initial_churn)
        comparison = str(solution.primary_amount_to_available)
        second_comparison = str(solution.second_amount_to_remaining)
        next_epoch = spec.Epoch(spec.get_current_epoch(pre) + 1)

        if carry == "CARRY_NONZERO":
            pre.deposit_balance_to_consume = spec.EFFECTIVE_BALANCE_INCREMENT
        available = pre.deposit_balance_to_consume + spec.get_activation_churn_limit(pre)
        amount = {
            "LT": spec.EFFECTIVE_BALANCE_INCREMENT,
            "EQ": available,
            "GT": available + spec.EFFECTIVE_BALANCE_INCREMENT,
        }.get(comparison, spec.EFFECTIVE_BALANCE_INCREMENT)

        def set_role(index: int, entry_role: str) -> None:
            validator = pre.validators[index]
            if entry_role == "EXITING":
                validator.exit_epoch = spec.Epoch(0)
                validator.withdrawable_epoch = (
                    spec.Epoch(next_epoch + 1)
                    if str(solution.withdrawable_epoch_to_next_epoch) == "GT"
                    else next_epoch
                )
            elif entry_role == "WITHDRAWN":
                validator.exit_epoch = spec.Epoch(0)
                validator.withdrawable_epoch = spec.Epoch(next_epoch - 1)

        def add_primary(entry_role: str, *, slot: Any = None) -> None:
            if entry_role in {"ACTIVE", "EXITING", "WITHDRAWN"}:
                set_role(0, entry_role)
                pre.pending_deposits.append(self._deposit(pre, 0, amount, slot=slot))
            else:
                pre.pending_deposits.append(
                    self._deposit(
                        pre, NUM_VALIDATORS, amount, signed=entry_role == "NEW_VALID", slot=slot
                    )
                )

        if layout == "FIRST_UNFINALIZED":
            add_primary(role, slot=spec.Slot(1))
        elif layout == "SINGLE":
            add_primary(role)
        elif layout == "POSTPONE_THEN_ACTIVE":
            add_primary("EXITING")
            pre.pending_deposits.append(self._deposit(pre, 1, spec.EFFECTIVE_BALANCE_INCREMENT))
        elif layout == "ACTIVE_THEN_UNFINALIZED":
            add_primary(role)
            pre.pending_deposits.append(
                self._deposit(pre, 1, spec.EFFECTIVE_BALANCE_INCREMENT, slot=spec.Slot(1))
            )
        elif layout in {"TWO_PROCESSABLE", "INVALID_THEN_PROCESSABLE"}:
            add_primary("NEW_INVALID" if layout == "INVALID_THEN_PROCESSABLE" else role)
            remaining = available - amount
            second_amount = {
                "LT": spec.EFFECTIVE_BALANCE_INCREMENT,
                "EQ": remaining,
                "GT": remaining + spec.EFFECTIVE_BALANCE_INCREMENT,
            }[second_comparison]
            pre.pending_deposits.append(self._deposit(pre, 1, second_amount))
        elif layout == "LIMIT_AFTER_WITHDRAWN":
            set_role(0, "WITHDRAWN")
            for _ in range(int(spec.MAX_PENDING_DEPOSITS_PER_EPOCH)):
                pre.pending_deposits.append(self._deposit(pre, 0, spec.EFFECTIVE_BALANCE_INCREMENT))
            add_primary(role)
        elif layout != "EMPTY":
            raise ValueError(f"unknown queue layout: {layout}")

        post = pre.copy()
        spec.process_pending_deposits(post)
        claimed = {
            name: bool(value) if isinstance(value := getattr(solution, name), bool) else str(value)
            for name in _DIMS
        }
        return pre, post, claimed

    def write_case(self, dumper: Dumper, output_dir: Path, index: int, solution: Any) -> None:
        pre, post, claimed = self.materialize_solution(solution)
        case_name = f"case_{index:04d}"
        test_case = TestCase(
            fork_name=self.fork_name,
            preset_name=self.preset_name,
            runner_name="epoch_processing",
            handler_name="pending_deposits",
            suite_name="main",
            case_name=case_name,
        )
        test_case.set_output_dir(str(output_dir))
        dump_test_case_result(
            TestCaseResult(
                test_case=test_case,
                meta={"description": f"process_pending_deposits: {claimed['outcome']}"},
                case_parts=[
                    ("pre", "ssz", pre.encode_bytes()),  # type: ignore[arg-type]
                    ("post", "ssz", post.encode_bytes()),  # type: ignore[arg-type]
                ],
            ),
            dumper,
        )
        dumper.dump_data(test_case.dir, "dimensions", {"case": case_name, "claimed": claimed})

    def materialize_reps(self, output_dir: Path, reps: list[Any]) -> int:
        if output_dir.exists():
            shutil.rmtree(output_dir)
        output_dir.mkdir(parents=True)
        dumper = Dumper()
        for index, solution in enumerate(reps):
            self.write_case(dumper, output_dir, index, solution)
        print(f"Generated {len(reps)} test cases in {output_dir}")
        return len(reps)
