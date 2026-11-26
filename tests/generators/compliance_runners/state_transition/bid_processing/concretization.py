"""Concrete witnesses for execution-payload-bid coverage cases."""

from __future__ import annotations

from typing import Any, TYPE_CHECKING

from eth_consensus_specs.test.helpers.keys import builder_pubkeys
from tests.generators.compliance_runners.state_transition.aspects_helpers.byte_witness import (
    distinct_bytes,
)
from tests.generators.compliance_runners.state_transition.aspects_helpers.entity_reference import (
    distinct_indices,
)
from tests.generators.compliance_runners.state_transition.concretization import (
    ConcretizationStrategy,
)

if TYPE_CHECKING:
    from random import Random


def pick_deposit_epoch(
    state_cmp: str, finalized_cmp: str, state_epoch: int, finalized_epoch: int, rng: Random
) -> int:
    """Choose a deposit epoch relative to the state's existing checkpoints."""
    if state_cmp == "EQ":
        return state_epoch
    if finalized_cmp == "LT":
        return rng.randrange(finalized_epoch + 1, state_epoch)
    if finalized_cmp == "EQ":
        return finalized_epoch
    return rng.randrange(finalized_epoch)


def _pick_balance_and_bid_value(
    b_zero: str,
    b_min: str,
    v_zero: str,
    v_funds: str,
    min_deposit: int,
    pending_total: int,
    rng: Random,
) -> tuple[int, int]:
    """Pick (balance, bid_value) satisfying all four comparisons:
    - cmp(balance, 0) = b_zero
    - cmp(balance, min_deposit) = b_min
    - cmp(bid_value, 0) = v_zero
    - cmp(balance, bid_value + min_deposit + pending_total) = v_funds
    """
    min_balance = min_deposit + pending_total

    # Step 1: pick bid_value
    bid_value = 0 if v_zero == "EQ" else rng.randrange(1, 1001)

    # Step 2: pick balance from v_funds (the tighter constraint)
    if v_funds == "EQ":
        balance = bid_value + min_balance
    elif v_funds == "GT":
        balance = bid_value + min_balance + rng.randrange(1, 1001)
    else:  # LT
        target = bid_value + min_balance
        balance = max(0, target - 1) if target > 0 else 0

    # Step 3: check/fix b_zero
    if b_zero == "EQ":
        balance = 0
        # balance=0; bid_value still picked from v_zero (can bid more than balance)
        if v_zero == "EQ":
            bid_value = 0
        else:
            bid_value = rng.randrange(1, 1001)
        return balance, bid_value

    # Step 4: check/fix b_min — adjust balance to also satisfy cmp(balance, min_deposit)
    # We may need to adjust bid_value to keep v_funds consistent.
    def _cmp(a, b):
        return "LT" if a < b else ("EQ" if a == b else "GT")

    if _cmp(balance, min_deposit) != b_min:
        # Pick a balance that satisfies b_min, then adjust bid_value for v_funds
        if b_min == "LT":
            balance = rng.randrange(min_deposit) if min_deposit > 0 else 0
        elif b_min == "EQ":
            balance = min_deposit
        else:  # GT
            balance = min_deposit + rng.randrange(1, 1001)

        # Now re-derive bid_value from v_funds
        if v_funds == "EQ":
            bid_value = balance - min_balance
        elif v_funds == "GT":
            # balance > bid_value + min_balance -> bid_value < balance - min_balance
            avail = balance - min_balance
            bid_value = rng.randrange(1, avail) if avail > 1 else 1
        else:  # LT
            # balance < bid_value + min_balance -> bid_value > balance - min_balance
            avail = balance - min_balance
            bid_value = max(1, avail + rng.randrange(1, 1001))

    # Step 5: enforce v_zero
    if v_zero == "EQ":
        bid_value = 0
    elif bid_value <= 0:
        bid_value = rng.randrange(1, 1001)

    return balance, bid_value


class ManualConcretizer:
    def concretize(self, abstract_case: Any, spec: Any, rng: Random) -> dict[str, Any]:
        rec = vars(abstract_case)
        is_self = rec["builder_type"] == "SELF"
        # Key zero is already in the genesis registry for the exit history.
        builder_key_index, wrong_key_index = distinct_indices(rng, len(builder_pubkeys) - 1, 2)
        builder_address, _ = distinct_bytes(rng, 20)
        result: dict[str, Any] = {
            "is_self": is_self,
            "past_genesis": rec.get("state_slot_past_genesis", True),
            "builder_key_index": builder_key_index + 1,
            "wrong_key_index": wrong_key_index + 1,
            "builder_address": builder_address,
        }

        if not is_self:
            pending_payment_amount = (
                rng.randrange(1, 1001) if rec["has_pending_payments"] is True else 0
            )
            pending_withdrawal_amount = (
                rng.randrange(1, 1001) if rec["has_pending_withdrawals"] is True else 0
            )
            result["pending_payment_amount"] = pending_payment_amount
            result["pending_withdrawal_amount"] = pending_withdrawal_amount
            result["balance"], result["bid_value"] = _pick_balance_and_bid_value(
                rec["cmp_balance_zero"],
                rec["cmp_balance_min_deposit"],
                rec["cmp_bid_value_zero"],
                rec["cmp_builder_balance_to_bid_value_plus_min_balance"],
                int(spec.MIN_DEPOSIT_AMOUNT),
                pending_payment_amount + pending_withdrawal_amount,
                rng,
            )
        else:
            result["bid_value"] = 0 if rec["cmp_bid_value_zero"] == "EQ" else rng.randrange(1, 1001)

        return result


STRATEGY = ConcretizationStrategy("manual", ManualConcretizer())
