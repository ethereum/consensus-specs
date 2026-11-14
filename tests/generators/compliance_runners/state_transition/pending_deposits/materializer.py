"""Materialize Gloas ``process_pending_deposits`` epoch-processing vectors."""

from __future__ import annotations

from typing import Any, TYPE_CHECKING

from eth_consensus_specs.test.helpers.deposits import prepare_pending_deposit
from eth_consensus_specs.test.helpers.genesis import create_genesis_state
from tests.generators.compliance_runners.state_transition.aspects_helpers.comparison_witness import (
    value_for_comparison,
)
from tests.generators.compliance_runners.state_transition.materializer import (
    ConcretizingMaterializer,
)
from tests.generators.compliance_runners.state_transition.validation_helpers import bls_enabled

from .concretization import NUM_VALIDATORS, STRATEGY
from .target import TARGET

if TYPE_CHECKING:
    from tests.generators.compliance_runners.gen_base.gen_typing import TestCasePart


class PendingDepositsMaterializer(ConcretizingMaterializer):
    runner_name = "epoch_processing"
    handler_name = "pending_deposits"
    strategy = STRATEGY

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
        with bls_enabled():
            return prepare_pending_deposit(
                self.spec,
                validator_index,
                amount,
                signed=signed,
                slot=self.spec.GENESIS_SLOT if slot is None else slot,
            )

    def materialize_concrete_attributes(
        self, solution: Any, attributes: dict[str, Any]
    ) -> tuple[dict, list[TestCasePart]]:
        spec = self.spec
        pre = self._base_state()
        carry = attributes["initial_churn"]
        comparison = attributes["primary_amount_to_available"]
        second_comparison = attributes["second_amount_to_remaining"]
        withdrawable_comparison = attributes["withdrawable_epoch_to_next_epoch"]
        next_epoch = spec.Epoch(spec.get_current_epoch(pre) + 1)
        primary_index = attributes["primary_index"]
        secondary_index = attributes["secondary_index"]
        new_validator_index = attributes["new_validator_index"]
        unfinalized_slot = spec.Slot(attributes["unfinalized_slot"])

        if carry == "CARRY_NONZERO":
            pre.deposit_balance_to_consume = spec.Gwei(
                self.rng.randrange(1, int(spec.EFFECTIVE_BALANCE_INCREMENT) + 1)
            )
        available = int(pre.deposit_balance_to_consume + spec.get_activation_churn_limit(pre))
        amount = (
            value_for_comparison(self.rng, comparison, available, lower_bound=1)
            if comparison != "NA"
            else int(spec.EFFECTIVE_BALANCE_INCREMENT)
        )

        def set_role(index: int, entry_role: str) -> None:
            validator = pre.validators[index]
            if entry_role == "EXITING":
                validator.exit_epoch = spec.Epoch(0)
                validator.withdrawable_epoch = (
                    spec.Epoch(next_epoch + self.rng.randrange(1, 11))
                    if withdrawable_comparison == "GT"
                    else next_epoch
                )
            elif entry_role == "WITHDRAWN":
                validator.exit_epoch = spec.Epoch(0)
                validator.withdrawable_epoch = spec.Epoch(next_epoch - 1)

        def add_primary(entry_role: str, amount: int, *, slot: Any = None) -> None:
            if entry_role in {"ACTIVE", "EXITING", "WITHDRAWN"}:
                set_role(primary_index, entry_role)
                pre.pending_deposits.append(self._deposit(pre, primary_index, amount, slot=slot))
            else:
                pre.pending_deposits.append(
                    self._deposit(
                        pre,
                        new_validator_index,
                        amount,
                        signed=entry_role == "NEW_VALID",
                        slot=slot,
                    )
                )

        if attributes["initially_withdrawn"]:
            set_role(primary_index, "WITHDRAWN")
            for _ in range(attributes["fill_withdrawn_limit"]):
                pre.pending_deposits.append(
                    self._deposit(pre, primary_index, spec.EFFECTIVE_BALANCE_INCREMENT)
                )

        for entry in attributes["entries"]:
            source = entry["source"]
            entry_amount = entry["amount"]
            slot = unfinalized_slot if entry.get("slot") == "unfinalized" else None
            if entry_amount == "primary":
                entry_amount = amount
            elif entry_amount == "increment":
                entry_amount = spec.EFFECTIVE_BALANCE_INCREMENT
            elif entry_amount == "second":
                remaining = available - amount
                entry_amount = value_for_comparison(
                    self.rng, second_comparison, remaining, lower_bound=1
                )

            if source == "primary":
                add_primary(entry["role"], entry_amount, slot=slot)
            elif source == "secondary":
                pre.pending_deposits.append(
                    self._deposit(pre, secondary_index, entry_amount, slot=slot)
                )
            else:
                raise ValueError(f"unknown pending-deposit source: {source}")

        post = pre.copy()
        with bls_enabled():
            spec.process_pending_deposits(post)
        claimed = self.claimed_record(TARGET, solution)
        meta = {
            "description": f"process_pending_deposits: {claimed['outcome']}",
            "bls_setting": 1,
            "claimed": claimed,
        }
        parts = [("pre", "ssz", pre.encode_bytes()), ("post", "ssz", post.encode_bytes())]
        return meta, parts


MATERIALIZER = PendingDepositsMaterializer
