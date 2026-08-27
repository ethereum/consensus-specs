"""Materialize aspect-model solutions into process_execution_payload_bid cases.

Solves models/coverage_smoke.mzn, reduces the solutions to the declared
obligation cover_each((outcome, self_build)) — the "both branches for the shared
tail" set — and materializes each representative into a concrete
pre / SignedExecutionPayloadBid / post vector, realizing every applicable
coverage dimension of its solution. The immutable solution is serialized to
dimensions.yaml (the contract validation.py checks against).

Spec: specs/gloas/beacon-chain.md process_execution_payload_bid.

Usage:
    uv run python -m tests.generators.compliance_runners.state_transition.execution_payload_bid.materializer
"""
from __future__ import annotations

from typing import Any, TYPE_CHECKING

from eth_consensus_specs.test.helpers.genesis import create_genesis_state
from eth_consensus_specs.test.helpers.keys import builder_pubkey_to_privkey, builder_pubkeys
from eth_consensus_specs.utils import bls
from tests.generators.compliance_runners.state_transition.materializer import Materializer

if TYPE_CHECKING:
    from generators.compliance_runners.gen_base.gen_typing import TestCasePart

BUILDER_PUBKEY = builder_pubkeys[0]  # the referenced builder
WRONG_PUBKEY = builder_pubkeys[1]  # a different signer, for invalid signatures
FINALIZED_EPOCH = 5  # fabricated, with headroom for LT/EQ/GT deposits
EPOCHS_PAST_GENESIS = 10
BIG = 10**10  # comfortable balance headroom above min_balance

# Coverage dimensions serialized to dimensions.yaml (the authoritative solution).
_DIMS = [
    "builder_ref",
    "builder_deposit_to_finalized_epoch",
    "builder_withdrawable_epoch_set",
    "builder_version_valid",
    "builder_has_pending_withdrawal",
    "builder_has_pending_payment",
    "builder_balance_to_min_balance",
    "builder_available_to_bid",
    "builder_signature_valid",
    "self_build_signature_is_infinity",
    "amount_positive",
    "bid_kzg_to_max",
    "bid_slot_to_state",
    "state_slot_past_genesis",
    "bid_parent_block_hash_matches",
    "bid_parent_block_root_matches",
    "bid_prev_randao_matches",
    # derived, recorded for validation convenience
    "builder_active",
    "builder_can_cover_bid",
    "self_build",
    "outcome",
]


def _s(sol: Any, name: str) -> str:
    return str(getattr(sol, name))


def _b(sol: Any, name: str) -> bool:
    return bool(getattr(sol, name))


class ExecutionPayloadBidMaterializer(Materializer):
    runner_name = "operations"
    handler_name = "execution_payload_bid"

    def _sign(self, state: Any, bid: Any, privkey: int) -> Any:
        spec = self.spec
        domain = spec.get_domain(state, spec.DOMAIN_BEACON_BUILDER)
        root = spec.compute_signing_root(bid, domain)
        return bls.Sign(privkey, root)

    def _base_state(self, past_genesis: bool) -> Any:
        spec = self.spec
        state = create_genesis_state(
            spec,
            validator_balances=[spec.MAX_EFFECTIVE_BALANCE] * 256,
            activation_threshold=spec.MAX_EFFECTIVE_BALANCE,
        )
        state.builders = type(state.builders)()
        state.slot = (
            spec.Slot(EPOCHS_PAST_GENESIS * spec.SLOTS_PER_EPOCH) if past_genesis else spec.Slot(0)
        )
        # Fabricate a finalized checkpoint with headroom so deposit vs finalized
        # can be LT/EQ/GT (even at the genesis slot, where it is pathological but
        # spec-accepted — is_active_builder reads finalized_checkpoint, not slot).
        state.finalized_checkpoint = spec.Checkpoint(
            epoch=spec.Epoch(FINALIZED_EPOCH), root=spec.Root(b"\x01" * 32)
        )
        return state

    def materialize_solution(self, sol: Any) -> tuple[dict, list[TestCasePart]]:
        spec = self.spec
        ref = _s(sol, "builder_ref")
        self_build = _b(sol, "self_build")
        past_genesis = _b(sol, "state_slot_past_genesis")

        pre = self._base_state(past_genesis)
        current_epoch = int(spec.get_current_epoch(pre))

        # ---- Builder registry (EXISTING only) -------------------------------
        if ref == "EXISTING":
            pw = _s(sol, "builder_has_pending_withdrawal") == "T"
            pp = _s(sol, "builder_has_pending_payment") == "T"
            pending_total = (1 if pw else 0) + (1 if pp else 0)
            min_balance = int(spec.MIN_DEPOSIT_AMOUNT) + pending_total

            dep = _s(sol, "builder_deposit_to_finalized_epoch")
            deposit_epoch = {
                "LT": FINALIZED_EPOCH - 1,
                "EQ": FINALIZED_EPOCH,
                "GT": FINALIZED_EPOCH + 1,
            }[dep]
            wset = _s(sol, "builder_withdrawable_epoch_set") == "T"
            withdrawable = spec.Epoch(current_epoch) if wset else spec.FAR_FUTURE_EPOCH
            version = (
                spec.PAYLOAD_BUILDER_VERSION
                if _s(sol, "builder_version_valid") == "T"
                else spec.Uint8(1)
            )

            b2min = _s(sol, "builder_balance_to_min_balance")
            balance = {"LT": min_balance - 1, "EQ": min_balance, "GT": min_balance + BIG}[b2min]

            pre.builders.append(
                spec.Builder(
                    pubkey=spec.BLSPubkey(BUILDER_PUBKEY),
                    version=version,
                    execution_address=spec.ExecutionAddress(b"\x22" * 20),
                    balance=spec.Gwei(balance),
                    deposit_epoch=spec.Epoch(deposit_epoch),
                    withdrawable_epoch=withdrawable,
                )
            )
            if pw:
                pre.builder_pending_withdrawals.append(
                    spec.BuilderPendingWithdrawal(
                        fee_recipient=spec.ExecutionAddress(b"\x22" * 20),
                        amount=spec.Gwei(1),
                        builder_index=spec.BuilderIndex(0),
                    )
                )
            if pp:
                pre.builder_pending_payments[0] = spec.BuilderPendingPayment(
                    weight=spec.Gwei(1),
                    withdrawal=spec.BuilderPendingWithdrawal(
                        fee_recipient=spec.ExecutionAddress(b"\x22" * 20),
                        amount=spec.Gwei(1),
                        builder_index=spec.BuilderIndex(0),
                    ),
                    proposer_index=spec.ValidatorIndex(0),
                )
        else:
            min_balance = 0  # unused

        # ---- builder_index ---------------------------------------------------
        if self_build:
            builder_index = spec.BUILDER_INDEX_SELF_BUILD
        elif ref == "NON_EXISTING":
            builder_index = spec.BuilderIndex(len(pre.builders))  # past end -> IndexError
        else:
            builder_index = spec.BuilderIndex(0)

        # ---- bid.value -------------------------------------------------------
        amt_pos = _b(sol, "amount_positive")
        if ref == "EXISTING" and _s(sol, "builder_balance_to_min_balance") in ("EQ", "GT"):
            available = int(pre.builders[0].balance) - min_balance
            if not amt_pos:
                value = 0
            else:
                avail = _s(sol, "builder_available_to_bid")
                value = {"LT": available + 1000, "EQ": available, "GT": available - 1000}[avail]
        else:
            value = 1 if amt_pos else 0

        # ---- bid.slot --------------------------------------------------------
        slot_cmp = _s(sol, "bid_slot_to_state")
        bid_slot = {"EQ": int(pre.slot), "LT": int(pre.slot) - 1, "GT": int(pre.slot) + 1}[slot_cmp]

        # ---- KZG commitments -------------------------------------------------
        max_blobs = spec.get_blob_parameters(spec.get_current_epoch(pre)).max_blobs_per_block
        kzg = _s(sol, "bid_kzg_to_max")
        n_kzg = {"LT": max(0, max_blobs - 1), "EQ": max_blobs, "GT": max_blobs + 1}[kzg]
        commitments = [spec.KZGCommitment(bytes([i % 256]) * 48) for i in range(n_kzg)]

        # ---- block context ---------------------------------------------------
        ph = _b(sol, "bid_parent_block_hash_matches")
        rr = _b(sol, "bid_prev_randao_matches")
        pr = _s(sol, "bid_parent_block_root_matches")
        parent_block_hash = pre.latest_block_hash if ph else spec.Hash32(b"\x02" * 32)
        prev_randao = (
            spec.get_randao_mix(pre, spec.get_current_epoch(pre))
            if rr
            else spec.Bytes32(b"\x06" * 32)
        )
        if pr == "T":
            parent_block_root = spec.get_block_root_at_slot(pre, spec.Slot(int(pre.slot) - 1))
        else:  # F or NA (genesis, not reached) — value unused
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
            value=spec.Gwei(value),
            execution_payment=spec.Gwei(0),
            blob_kzg_commitments=spec.BlobKZGCommitments(data=commitments),
            execution_requests_root=spec.Root(b"\x08" * 32),
        )

        # ---- signature -------------------------------------------------------
        if self_build:
            if _s(sol, "self_build_signature_is_infinity") == "T":
                signature = spec.bls.G2_POINT_AT_INFINITY
            else:
                signature = self._sign(pre, bid, builder_pubkey_to_privkey[BUILDER_PUBKEY])
        elif ref == "NON_EXISTING":
            signature = spec.BLSSignature(b"\x00" * 96)  # never verified (rejected earlier)
        else:  # EXISTING
            key = BUILDER_PUBKEY if _s(sol, "builder_signature_valid") == "T" else WRONG_PUBKEY
            signature = self._sign(pre, bid, builder_pubkey_to_privkey[key])

        signed = spec.SignedExecutionPayloadBid(message=bid, signature=signature)

        # ---- derive post (accepted) or omit (rejected) ----------------------
        post = pre.copy()
        accepted = True
        try:
            spec.process_execution_payload_bid(post, signed)
        except (AssertionError, IndexError):
            accepted = False
            post = None

        claimed = {
            name: (_s(sol, name) if not isinstance(getattr(sol, name), bool) else _b(sol, name))
            for name in _DIMS
        }
        parts: list[TestCasePart] = [
            ("pre", "ssz", pre.encode_bytes()),
            ("execution_payload_bid", "ssz", signed.encode_bytes()),
        ]
        if accepted:
            parts.append(("post", "ssz", post.encode_bytes()))  # type: ignore[union-attr]
        meta = {
            "description": f"process_execution_payload_bid: {claimed['outcome']} "
            f"(self_build={int(bool(claimed['self_build']))})",
            "bls_setting": 1,
            "claimed": claimed,
        }
        return meta, parts
