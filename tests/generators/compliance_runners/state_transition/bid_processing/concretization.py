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


def _pick_deposit_epoch(s_dep: str, state_epoch: int, rng: Random) -> int:
    """Pick deposit_epoch satisfying cmp(state_epoch, deposit_epoch) = s_dep.
    s_dep=EQ -> deposit == state; GT -> state > deposit.
    Ensure deposit_epoch >= 1 so finalized can be below it when needed.
    """
    if s_dep == "EQ":
        return state_epoch
    # GT: state > deposit. Keep it positive so finalized can be below it.
    return rng.randrange(1, state_epoch)


def _pick_finalized_epoch(f_dep: str, deposit_epoch: int, rng: Random) -> int:
    """Pick finalized_epoch satisfying cmp(finalized_epoch, deposit_epoch) = f_dep.
    f_dep=LT means finalized < deposit; EQ means equal; GT means finalized > deposit.
    """
    if f_dep == "LT":
        return rng.randrange(deposit_epoch)
    elif f_dep == "EQ":
        return deposit_epoch
    return deposit_epoch + rng.randrange(1, 11)


def _pick_withdrawable_epoch(w_cmp: str, state_epoch: int, rng: Random) -> int:
    """Pick a withdrawable epoch satisfying the requested comparison.
    cmp(state_epoch, withdrawable_epoch) = w_cmp.
    LT -> state < withdrawable (withdrawable = state + 1)
    EQ -> state == withdrawable
    GT -> state > withdrawable (withdrawable = state - 1)
    """
    if w_cmp == "LT":
        return state_epoch + rng.randrange(1, 11)
    elif w_cmp == "EQ":
        return state_epoch
    return rng.randrange(state_epoch)


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


# ``make_base_state(..., preprocess=True)`` advances the state by two epochs.
_STATE_EPOCH = 2


class ManualConcretizer:
    def concretize(self, abstract_case: Any, spec: Any, rng: Random) -> dict[str, Any]:
        rec = vars(abstract_case)
        is_self = rec["builder_type"] == "SELF"
        builder_key_index, wrong_key_index = distinct_indices(rng, len(builder_pubkeys), 2)
        builder_address, _ = distinct_bytes(rng, 20)
        result: dict[str, Any] = {
            "is_self": is_self,
            "past_genesis": rec.get("state_slot_past_genesis", True),
            "current_epoch": _STATE_EPOCH,
            "builder_key_index": builder_key_index,
            "wrong_key_index": wrong_key_index,
            "builder_address": builder_address,
        }

        if not is_self:
            deposit_epoch = _pick_deposit_epoch(
                rec["cmp_state_epoch_deposit_epoch"], _STATE_EPOCH, rng
            )
            result["deposit_epoch"] = deposit_epoch
            result["finalized_epoch"] = _pick_finalized_epoch(
                rec["cmp_finalized_epoch_deposit_epoch"], deposit_epoch, rng
            )
            result["finalized_root"] = distinct_bytes(rng, 32)[0]
            if rec["withdrawable_epoch_set"] is True:
                result["withdrawable_epoch"] = _pick_withdrawable_epoch(
                    rec["cmp_state_epoch_withdrawal_epoch"], _STATE_EPOCH, rng
                )

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
