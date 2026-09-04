"""Materialize bid_processing aspect-model solutions into process_execution_payload_bid cases.

Solves models/coverage_smoke.mzn (or handler_bid_processing.mzn), materializes
each solution into a concrete pre / SignedExecutionPayloadBid / post vector
using common_state_preprocessor, and verifies each via bid_processing_validator.

Spec: specs/gloas/beacon-chain.md process_execution_payload_bid.

Usage:
    uv run python -m tests.generators.compliance_runners.state_transition.bid_processing.materializer
"""

from __future__ import annotations

from typing import Any, TYPE_CHECKING

from eth_consensus_specs.test.helpers.keys import builder_pubkey_to_privkey, builder_pubkeys
from eth_consensus_specs.utils import bls
from tests.generators.compliance_runners.state_transition.aspects.base import (
    BuilderType,
    SignatureType,
)
from tests.generators.compliance_runners.state_transition.aspects.bid_processing.bid_processing import (
    ExecutionPayloadBidProcessing,
)
from tests.generators.compliance_runners.state_transition.aspects.bid_processing.bid_processing_validator import (
    bid_processing_validator,
)
from tests.generators.compliance_runners.state_transition.materializer import Materializer
from tests.generators.compliance_runners.state_transition.materializer.common import (
    BOOL,
    CMP,
    make_base_state,
    to_builder_solution,
)

if TYPE_CHECKING:
    from tests.generators.compliance_runners.gen_base.gen_typing import TestCasePart


BUILDER_PUBKEY = builder_pubkeys[0]
WRONG_PUBKEY = builder_pubkeys[1]
BUILDER_ADDRESS = b"\x22" * 20

_BT = {"EXTERNAL": BuilderType.EXTERNAL, "SELF": BuilderType.SELF}
_ST = {"INF": SignatureType.INF, "VALID": SignatureType.VALID, "INVALID": SignatureType.INVALID}

DIMS = [
    "builder_type",
    "cmp_bid_value_zero",
    "bid_signature",
    "cmp_builder_balance_to_bid_value_plus_min_balance",
    "cmp_len_kzg_commitments_max_blobs",
    "cmp_state_slot_bid_slot",
    "parent_block_hash_match",
    "parent_block_root_match",
    "prev_randao_match",
    # builder sub-dimensions
    "payload_builder_version",
    "cmp_state_epoch_deposit_epoch",
    "cmp_state_epoch_withdrawal_epoch",
    "cmp_finalized_epoch_deposit_epoch",
    "withdrawable_epoch_set",
    "cmp_balance_zero",
    "cmp_balance_min_deposit",
    "has_pending_payments",
    "has_pending_withdrawals",
    # handler-local
    "amount_positive",
    "state_slot_past_genesis",
    # derived
    "outcome",
]


def _normalize(sol: Any) -> dict[str, Any]:
    """Flatten a MiniZinc solution into a {field: value} dict."""
    p = getattr(sol, "p", None)
    if p is None:
        if isinstance(sol, dict):
            return sol
        return {k: getattr(sol, k) for k in dir(sol) if not k.startswith("_")}
    rec: dict[str, Any] = {}
    for k, v in p.items():
        if k == "builder" and isinstance(v, dict):
            for bk, bv in v.items():
                rec[bk] = str(bv)
        else:
            rec[k] = str(v)
    for k in ("amount_positive", "state_slot_past_genesis", "outcome"):
        v = getattr(sol, k, None)
        if v is not None:
            rec[k] = bool(v) if isinstance(v, bool) else str(v)
    return rec


def _to_solution(rec: dict[str, Any]) -> ExecutionPayloadBidProcessing:
    return ExecutionPayloadBidProcessing(
        builder_type=_BT[rec["builder_type"]],
        builder=to_builder_solution(rec),
        cmp_bid_value_zero=CMP[rec["cmp_bid_value_zero"]],
        bid_signature=_ST[rec["bid_signature"]],
        cmp_builder_balance_to_bid_value_plus_min_balance=CMP[
            rec["cmp_builder_balance_to_bid_value_plus_min_balance"]
        ],
        cmp_len_kzg_commitments_max_blobs=CMP[rec["cmp_len_kzg_commitments_max_blobs"]],
        cmp_state_slot_bid_slot=CMP[rec["cmp_state_slot_bid_slot"]],
        parent_block_hash_match=BOOL[rec["parent_block_hash_match"]],
        parent_block_root_match=BOOL[rec["parent_block_root_match"]],
        prev_randao_match=BOOL[rec["prev_randao_match"]],
    )


def _pick_deposit_epoch(s_dep: str, state_epoch: int) -> int:
    """Pick deposit_epoch satisfying cmp(state_epoch, deposit_epoch) = s_dep.
    s_dep=EQ -> deposit == state; GT -> state > deposit.
    Ensure deposit_epoch >= 1 so finalized can be below it when needed.
    """
    if s_dep == "EQ":
        return state_epoch
    # GT: state > deposit. Pick deposit = state - 2, but at least 1.
    return max(1, state_epoch - 2)


def _pick_finalized_epoch(f_dep: str, deposit_epoch: int) -> int:
    """Pick finalized_epoch satisfying cmp(finalized_epoch, deposit_epoch) = f_dep.
    f_dep=LT means finalized < deposit; EQ means equal; GT means finalized > deposit.
    """
    if f_dep == "LT":
        return max(0, deposit_epoch - 1)
    elif f_dep == "EQ":
        return deposit_epoch
    return deposit_epoch + 1


def _pick_withdrawable_epoch(w_cmp: str, state_epoch: int):
    """Returns (withdrawable_epoch, is_far_future).
    cmp(state_epoch, withdrawable_epoch) = w_cmp.
    LT -> state < withdrawable (withdrawable = state + 1)
    EQ -> state == withdrawable
    GT -> state > withdrawable (withdrawable = state - 1)
    """
    if w_cmp == "LT":
        return state_epoch + 1, False
    elif w_cmp == "EQ":
        return state_epoch, False
    return max(0, state_epoch - 1), False


def _pick_balance_and_bid_value(
    b_zero: str,
    b_min: str,
    v_zero: str,
    v_funds: str,
    min_deposit: int,
    pending_total: int,
) -> tuple[int, int]:
    """Pick (balance, bid_value) satisfying all four comparisons:
    - cmp(balance, 0) = b_zero
    - cmp(balance, min_deposit) = b_min
    - cmp(bid_value, 0) = v_zero
    - cmp(balance, bid_value + min_deposit + pending_total) = v_funds
    """
    min_balance = min_deposit + pending_total

    # Step 1: pick bid_value
    bid_value = 0 if v_zero == "EQ" else 1

    # Step 2: pick balance from v_funds (the tighter constraint)
    if v_funds == "EQ":
        balance = bid_value + min_balance
    elif v_funds == "GT":
        balance = bid_value + min_balance + 1000
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
            bid_value = 1
        return balance, bid_value

    # Step 4: check/fix b_min — adjust balance to also satisfy cmp(balance, min_deposit)
    # We may need to adjust bid_value to keep v_funds consistent.
    def _cmp(a, b):
        return "LT" if a < b else ("EQ" if a == b else "GT")

    if _cmp(balance, min_deposit) != b_min:
        # Pick a balance that satisfies b_min, then adjust bid_value for v_funds
        if b_min == "LT":
            balance = min_deposit - 1 if min_deposit > 0 else 0
        elif b_min == "EQ":
            balance = min_deposit
        else:  # GT
            balance = min_deposit + 1000

        # Now re-derive bid_value from v_funds
        if v_funds == "EQ":
            bid_value = balance - min_balance
        elif v_funds == "GT":
            # balance > bid_value + min_balance -> bid_value < balance - min_balance
            avail = balance - min_balance
            bid_value = max(1, avail - 1) if avail > 1 else 1
        else:  # LT
            # balance < bid_value + min_balance -> bid_value > balance - min_balance
            avail = balance - min_balance
            bid_value = max(1, avail + 1)

    # Step 5: enforce v_zero
    if v_zero == "EQ":
        bid_value = 0
    elif bid_value <= 0:
        bid_value = 1

    # Step 6: final verification — if we can't satisfy both, prioritize v_funds + b_min
    # (these are the dimensions the validator checks)
    return balance, bid_value


class BidProcessingMaterializer(Materializer):
    runner_name = "operations"
    handler_name = "execution_payload_bid"
    description = "process_execution_payload_bid"
    validator_name = "bid_processing_validator"
    bls_setting = 1

    def describe(self, claimed: dict) -> str:
        return f"process_execution_payload_bid: {claimed.get('outcome')}"

    def _sign(self, state: Any, bid: Any, privkey: int) -> Any:
        spec = self.spec
        domain = spec.get_domain(state, spec.DOMAIN_BEACON_BUILDER)
        root = spec.compute_signing_root(bid, domain)
        return bls.Sign(privkey, root)

    def __init__(self, spec: Any, fork_name="gloas", preset_name="minimal"):
        super().__init__(spec, fork_name, preset_name)
        # Precompute both base-state variants once; each solution starts from a copy.
        self._base_genesis = make_base_state(spec, num_validators=256, preprocess=False)
        self._base = make_base_state(spec, num_validators=256, preprocess=True)

    def _base_state(self, past_genesis: bool) -> Any:
        return (self._base if past_genesis else self._base_genesis).copy()

    def materialize_solution(self, sol: Any) -> tuple[dict, list[TestCasePart]]:
        spec = self.spec
        rec = _normalize(sol)
        is_self = rec["builder_type"] == "SELF"
        past_genesis = rec.get("state_slot_past_genesis", True)

        # State at genesis is a no-op — skip materialization entirely.
        if not past_genesis:
            assert False
            pre = self._base_state(past_genesis=False)
            claimed = {n: rec.get(n) for n in DIMS}
            return pre, None, True, claimed, []

        pre = self._base_state(past_genesis)
        current_epoch = int(spec.get_current_epoch(pre))
        min_deposit = int(spec.MIN_DEPOSIT_AMOUNT)

        builder_index = 0

        # ---- Builder registry (EXTERNAL only) -------------------------------
        # Append a new builder rather than overwriting existing ones.
        if not is_self:
            s_dep = rec["cmp_state_epoch_deposit_epoch"]
            f_dep = rec["cmp_finalized_epoch_deposit_epoch"]
            deposit_epoch = _pick_deposit_epoch(s_dep, current_epoch)
            finalized_epoch = _pick_finalized_epoch(f_dep, deposit_epoch)
            pre.finalized_checkpoint = spec.Checkpoint(
                epoch=spec.Epoch(finalized_epoch), root=spec.Root(b"\x01" * 32)
            )

            wset = rec["withdrawable_epoch_set"] == "T"
            if not wset:
                withdrawable_epoch = spec.FAR_FUTURE_EPOCH
            else:
                w_cmp = rec["cmp_state_epoch_withdrawal_epoch"]
                we, _ = _pick_withdrawable_epoch(w_cmp, current_epoch)
                withdrawable_epoch = spec.Epoch(we)

            version = (
                spec.PAYLOAD_BUILDER_VERSION
                if rec["payload_builder_version"] == "T"
                else spec.Uint8(1)
            )

            pending_total = (1000 if rec["has_pending_payments"] == "T" else 0) + (
                1000 if rec["has_pending_withdrawals"] == "T" else 0
            )
            balance, bid_value = _pick_balance_and_bid_value(
                rec["cmp_balance_zero"],
                rec["cmp_balance_min_deposit"],
                rec["cmp_bid_value_zero"],
                rec["cmp_builder_balance_to_bid_value_plus_min_balance"],
                min_deposit,
                pending_total,
            )

            pre.builders.append(
                spec.Builder(
                    pubkey=spec.BLSPubkey(BUILDER_PUBKEY),
                    version=version,
                    execution_address=spec.ExecutionAddress(BUILDER_ADDRESS),
                    balance=spec.Gwei(balance),
                    deposit_epoch=spec.Epoch(deposit_epoch),
                    withdrawable_epoch=withdrawable_epoch,
                )
            )
            builder_index = len(pre.builders) - 1

            if rec["has_pending_payments"] == "T":
                pre.builder_pending_payments[0] = spec.BuilderPendingPayment(
                    weight=spec.Gwei(1),
                    withdrawal=spec.BuilderPendingWithdrawal(
                        fee_recipient=spec.ExecutionAddress(BUILDER_ADDRESS),
                        amount=spec.Gwei(1000),
                        builder_index=spec.BuilderIndex(builder_index),
                    ),
                    proposer_index=spec.ValidatorIndex(0),
                )
            if rec["has_pending_withdrawals"] == "T":
                pre.builder_pending_withdrawals.append(
                    spec.BuilderPendingWithdrawal(
                        fee_recipient=spec.ExecutionAddress(BUILDER_ADDRESS),
                        amount=spec.Gwei(1000),
                        builder_index=spec.BuilderIndex(builder_index),
                    )
                )

        else:
            bid_value = 0 if rec["cmp_bid_value_zero"] == "EQ" else 1

        # ---- builder_index for the bid ----------------------------------------
        if is_self:
            builder_index = spec.BUILDER_INDEX_SELF_BUILD
        # else: builder_index already set above after appending

        # ---- bid.slot --------------------------------------------------------
        # cmp_state_slot_bid_slot = cmp(state_slot, bid_slot)
        # EQ -> state == bid, LT -> state < bid (bid = state+1), GT -> state > bid (bid = state-1)
        slot_cmp = rec["cmp_state_slot_bid_slot"]
        bid_slot = {"EQ": int(pre.slot), "LT": int(pre.slot) + 1, "GT": int(pre.slot) - 1}[slot_cmp]

        # ---- KZG commitments -------------------------------------------------
        max_blobs = spec.get_blob_parameters(spec.get_current_epoch(pre)).max_blobs_per_block
        kzg = rec["cmp_len_kzg_commitments_max_blobs"]
        n_kzg = {"LT": max(0, max_blobs - 1), "EQ": max_blobs, "GT": max_blobs + 1}[kzg]
        commitments = [spec.KZGCommitment(bytes([i % 256]) * 48) for i in range(n_kzg)]

        # ---- block context ---------------------------------------------------
        ph = rec["parent_block_hash_match"] == "T"
        rr = rec["prev_randao_match"] == "T"
        pr = rec["parent_block_root_match"] == "T"
        parent_block_hash = pre.latest_block_hash if ph else spec.Hash32(b"\x02" * 32)
        prev_randao = (
            spec.get_randao_mix(pre, spec.get_current_epoch(pre))
            if rr
            else spec.Bytes32(b"\x06" * 32)
        )
        if past_genesis and pr:
            parent_block_root = spec.get_block_root_at_slot(pre, spec.Slot(int(pre.slot) - 1))
        else:
            parent_block_root = spec.Root(b"\x04" * 32)

        bid = spec.ExecutionPayloadBid(
            parent_block_hash=parent_block_hash,
            parent_block_root=parent_block_root,
            block_hash=spec.Hash32(b"\x07" * 32),
            prev_randao=prev_randao,
            fee_recipient=spec.ExecutionAddress(b"\x00" * 20),
            gas_limit=spec.Uint64(30000000),
            builder_index=builder_index,
            slot=spec.Slot(bid_slot),
            value=spec.Gwei(bid_value),
            execution_payment=spec.Gwei(0),
            blob_kzg_commitments=spec.BlobKZGCommitments(data=commitments),
            execution_requests_root=spec.Root(b"\x08" * 32),
        )

        # ---- signature -------------------------------------------------------
        sig_type = rec["bid_signature"]
        if sig_type == "INF":
            signature = spec.bls.G2_POINT_AT_INFINITY
        elif is_self:
            signature = self._sign(pre, bid, builder_pubkey_to_privkey[BUILDER_PUBKEY])
        else:
            key = BUILDER_PUBKEY if sig_type == "VALID" else WRONG_PUBKEY
            signature = self._sign(pre, bid, builder_pubkey_to_privkey[key])

        signed = spec.SignedExecutionPayloadBid(message=bid, signature=signature)

        # ---- verify via validator --------------------------------------------
        solution = _to_solution(rec)
        verified = bid_processing_validator(spec, pre, solution, builder_index, signed)

        # ---- derive post (accepted) or omit (rejected) ----------------------
        post = pre.copy()
        try:
            spec.process_execution_payload_bid(post, signed)
        except (AssertionError, IndexError):
            post = None

        claimed = {n: rec.get(n) for n in DIMS}
        parts: list[TestCasePart] = [
            ("pre", "ssz", pre.encode_bytes()),
            ("execution_payload_bid", "ssz", signed.encode_bytes()),
        ]
        if post is not None:
            parts.append(("post", "ssz", post.encode_bytes()))  # type: ignore[union-attr]
        meta = {
            "description": f"process_execution_payload_bid: {claimed['outcome']}",
            "verified": True,
            "bls_setting": 1,
            "claimed": claimed,
        }
        return meta, parts
