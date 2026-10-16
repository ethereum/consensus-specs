"""Realize complete TARGET witnesses as signed execution-payload-bid vectors."""

from __future__ import annotations

from typing import Any, TYPE_CHECKING

from eth_consensus_specs.test.helpers.keys import builder_pubkey_to_privkey, builder_pubkeys
from eth_consensus_specs.utils import bls
from tests.generators.compliance_runners.state_transition.aspects_helpers.byte_witness import (
    distinct_bytes,
)
from tests.generators.compliance_runners.state_transition.aspects_helpers.entity_reference import (
    distinct_indices,
)
from tests.generators.compliance_runners.state_transition.materializer import Materializer
from tests.generators.compliance_runners.state_transition.materializer.common import (
    make_base_state,
)

from .target import TARGET

if TYPE_CHECKING:
    from random import Random

    from tests.generators.compliance_runners.gen_base.gen_typing import TestCasePart


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


class BidProcessingMaterializer(Materializer):
    runner_name = "operations"
    handler_name = "execution_payload_bid"

    def _sign(self, state: Any, bid: Any, privkey: int) -> Any:
        spec = self.spec
        domain = spec.get_domain(state, spec.DOMAIN_BEACON_BUILDER)
        root = spec.compute_signing_root(bid, domain)
        return bls.Sign(privkey, root)

    def __init__(self, spec: Any, fork_name="gloas", preset_name="minimal", seed: int = 0):
        super().__init__(spec, fork_name, preset_name, seed)
        # Generated witnesses are always past genesis.
        self._base = make_base_state(spec, num_validators=256, preprocess=True)

    def _base_state(self) -> Any:
        return self._base.copy()

    def materialize_solution(self, sol: Any) -> tuple[dict, list[TestCasePart]]:
        spec = self.spec
        rec = vars(sol)
        is_self = rec["builder_type"] == "SELF"
        past_genesis = rec.get("state_slot_past_genesis", True)

        # State at genesis is a no-op — skip materialization entirely.
        if not past_genesis:
            raise AssertionError("State slot should be past genesis")

        pre = self._base_state()
        current_epoch = int(spec.get_current_epoch(pre))
        min_deposit = int(spec.MIN_DEPOSIT_AMOUNT)
        builder_key_index, wrong_key_index = distinct_indices(self.rng, len(builder_pubkeys), 2)
        builder_pubkey = builder_pubkeys[builder_key_index]
        wrong_pubkey = builder_pubkeys[wrong_key_index]
        builder_address, _ = distinct_bytes(self.rng, 20)

        builder_index = 0

        # ---- Builder registry (EXTERNAL only) -------------------------------
        # Append a new builder rather than overwriting existing ones.
        if not is_self:
            s_dep = rec["cmp_state_epoch_deposit_epoch"]
            f_dep = rec["cmp_finalized_epoch_deposit_epoch"]
            deposit_epoch = _pick_deposit_epoch(s_dep, current_epoch, self.rng)
            finalized_epoch = _pick_finalized_epoch(f_dep, deposit_epoch, self.rng)
            finalized_root, _ = distinct_bytes(self.rng, 32)
            pre.finalized_checkpoint = spec.Checkpoint(
                epoch=spec.Epoch(finalized_epoch), root=spec.Root(finalized_root)
            )

            wset = rec["withdrawable_epoch_set"] is True
            if not wset:
                withdrawable_epoch = spec.FAR_FUTURE_EPOCH
            else:
                w_cmp = rec["cmp_state_epoch_withdrawal_epoch"]
                we = _pick_withdrawable_epoch(w_cmp, current_epoch, self.rng)
                withdrawable_epoch = spec.Epoch(we)

            version = (
                spec.PAYLOAD_BUILDER_VERSION
                if rec["payload_builder_version"] is True
                else spec.Uint8(1)
            )

            pending_payment_amount = (
                self.rng.randrange(1, 1001) if rec["has_pending_payments"] is True else 0
            )
            pending_withdrawal_amount = (
                self.rng.randrange(1, 1001) if rec["has_pending_withdrawals"] is True else 0
            )
            pending_total = pending_payment_amount + pending_withdrawal_amount
            balance, bid_value = _pick_balance_and_bid_value(
                rec["cmp_balance_zero"],
                rec["cmp_balance_min_deposit"],
                rec["cmp_bid_value_zero"],
                rec["cmp_builder_balance_to_bid_value_plus_min_balance"],
                min_deposit,
                pending_total,
                self.rng,
            )

            pre.builders.append(
                spec.Builder(
                    pubkey=spec.BLSPubkey(builder_pubkey),
                    version=version,
                    execution_address=spec.ExecutionAddress(builder_address),
                    balance=spec.Gwei(balance),
                    deposit_epoch=spec.Epoch(deposit_epoch),
                    withdrawable_epoch=withdrawable_epoch,
                )
            )
            builder_index = len(pre.builders) - 1

            if rec["has_pending_payments"] is True:
                payment_index = self.rng.randrange(len(pre.builder_pending_payments))
                pre.builder_pending_payments[payment_index] = spec.BuilderPendingPayment(
                    weight=spec.Gwei(self.rng.randrange(1, 1001)),
                    withdrawal=spec.BuilderPendingWithdrawal(
                        fee_recipient=spec.ExecutionAddress(builder_address),
                        amount=spec.Gwei(pending_payment_amount),
                        builder_index=spec.BuilderIndex(builder_index),
                    ),
                    proposer_index=spec.ValidatorIndex(self.rng.randrange(len(pre.validators))),
                )
            if rec["has_pending_withdrawals"] is True:
                pre.builder_pending_withdrawals.append(
                    spec.BuilderPendingWithdrawal(
                        fee_recipient=spec.ExecutionAddress(builder_address),
                        amount=spec.Gwei(pending_withdrawal_amount),
                        builder_index=spec.BuilderIndex(builder_index),
                    )
                )

        else:
            bid_value = 0 if rec["cmp_bid_value_zero"] == "EQ" else self.rng.randrange(1, 1001)

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
        commitments = [
            spec.KZGCommitment(self.rng.getrandbits(48 * 8).to_bytes(48, "big"))
            for _ in range(n_kzg)
        ]

        # ---- block context ---------------------------------------------------
        ph = rec["parent_block_hash_match"] is True
        rr = rec["prev_randao_match"] is True
        pr = rec["parent_block_root_match"] is True

        def mutate(value: bytes) -> bytes:
            result = bytearray(value)
            result[self.rng.randrange(len(result))] ^= self.rng.randrange(1, 256)
            return bytes(result)

        parent_block_hash = (
            pre.latest_block_hash if ph else spec.Hash32(mutate(bytes(pre.latest_block_hash)))
        )
        prev_randao = (
            spec.get_randao_mix(pre, spec.get_current_epoch(pre))
            if rr
            else spec.Bytes32(mutate(bytes(spec.get_randao_mix(pre, spec.get_current_epoch(pre)))))
        )
        if past_genesis and pr:
            parent_block_root = spec.get_block_root_at_slot(pre, spec.Slot(int(pre.slot) - 1))
        else:
            expected_parent_root = spec.get_block_root_at_slot(pre, spec.Slot(int(pre.slot) - 1))
            parent_block_root = spec.Root(mutate(bytes(expected_parent_root)))

        bid = spec.ExecutionPayloadBid(
            parent_block_hash=parent_block_hash,
            parent_block_root=parent_block_root,
            # The legacy coverage scope fixes this unprojected gate to pass.
            block_hash=spec.Hash32(mutate(bytes(parent_block_hash))),
            prev_randao=prev_randao,
            fee_recipient=spec.ExecutionAddress(distinct_bytes(self.rng, 20)[0]),
            gas_limit=spec.Uint64(30000000),
            builder_index=builder_index,
            slot=spec.Slot(bid_slot),
            value=spec.Gwei(bid_value),
            execution_payment=spec.Gwei(0),
            blob_kzg_commitments=spec.BlobKZGCommitments(data=commitments),
            execution_requests_root=spec.Root(distinct_bytes(self.rng, 32)[0]),
        )

        # ---- signature -------------------------------------------------------
        sig_type = rec["bid_signature"]
        if sig_type == "INF":
            signature = spec.bls.G2_POINT_AT_INFINITY
        elif is_self:
            signature = self._sign(pre, bid, builder_pubkey_to_privkey[builder_pubkey])
        else:
            key = builder_pubkey if sig_type == "VALID" else wrong_pubkey
            signature = self._sign(pre, bid, builder_pubkey_to_privkey[key])

        signed = spec.SignedExecutionPayloadBid(message=bid, signature=signature)

        # ---- derive post (accepted) or omit (rejected) ----------------------
        post = pre.copy()
        try:
            spec.process_execution_payload_bid(post, signed)
        except (AssertionError, IndexError):
            post = None

        claimed = self.claimed_record(TARGET, sol)
        parts: list[TestCasePart] = [
            ("pre", "ssz", pre.encode_bytes()),
            ("execution_payload_bid", "ssz", signed.encode_bytes()),
        ]
        if post is not None:
            parts.append(("post", "ssz", post.encode_bytes()))  # type: ignore[union-attr]
        meta = {
            "description": f"process_execution_payload_bid: {claimed['outcome']}",
            "bls_setting": 1,
            "claimed": claimed,
        }
        return meta, parts


MATERIALIZER = BidProcessingMaterializer
