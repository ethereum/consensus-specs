"""Realize complete TARGET witnesses as signed execution-payload-bid vectors."""

from __future__ import annotations

from typing import Any, TYPE_CHECKING

from eth_consensus_specs.test.helpers.keys import builder_pubkey_to_privkey, builder_pubkeys
from eth_consensus_specs.utils import bls
from tests.generators.compliance_runners.state_transition.aspects_helpers.byte_witness import (
    distinct_bytes,
)
from tests.generators.compliance_runners.state_transition.materializer import (
    ConcretizingMaterializer,
)
from tests.generators.compliance_runners.state_transition.materializer.common import (
    make_base_state,
)

from .concretization import STRATEGY
from .target import TARGET

if TYPE_CHECKING:
    from tests.generators.compliance_runners.gen_base.gen_typing import TestCasePart


class BidProcessingMaterializer(ConcretizingMaterializer):
    runner_name = "operations"
    handler_name = "execution_payload_bid"
    strategy = STRATEGY

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

    def materialize_concrete_attributes(
        self, sol: Any, attributes: dict[str, Any]
    ) -> tuple[dict, list[TestCasePart]]:
        spec = self.spec
        rec = vars(sol)
        is_self = attributes["is_self"]
        past_genesis = attributes["past_genesis"]

        # State at genesis is a no-op — skip materialization entirely.
        if not past_genesis:
            raise AssertionError("State slot should be past genesis")

        pre = self._base_state()
        current_epoch = attributes["current_epoch"]
        if current_epoch != int(spec.get_current_epoch(pre)):
            raise ValueError("bid concretization state epoch does not match the base state")
        builder_key_index = attributes["builder_key_index"]
        wrong_key_index = attributes["wrong_key_index"]
        builder_pubkey = builder_pubkeys[builder_key_index]
        wrong_pubkey = builder_pubkeys[wrong_key_index]
        builder_address = attributes["builder_address"]

        builder_index = 0

        # ---- Builder registry (EXTERNAL only) -------------------------------
        # Append a new builder rather than overwriting existing ones.
        if not is_self:
            deposit_epoch = attributes["deposit_epoch"]
            finalized_epoch = attributes["finalized_epoch"]
            finalized_root = attributes["finalized_root"]
            pre.finalized_checkpoint = spec.Checkpoint(
                epoch=spec.Epoch(finalized_epoch), root=spec.Root(finalized_root)
            )

            wset = rec["withdrawable_epoch_set"] is True
            if not wset:
                withdrawable_epoch = spec.FAR_FUTURE_EPOCH
            else:
                withdrawable_epoch = spec.Epoch(attributes["withdrawable_epoch"])

            version = (
                spec.PAYLOAD_BUILDER_VERSION
                if rec["payload_builder_version"] is True
                else spec.Uint8(1)
            )

            pending_payment_amount = attributes["pending_payment_amount"]
            pending_withdrawal_amount = attributes["pending_withdrawal_amount"]
            balance = attributes["balance"]
            bid_value = attributes["bid_value"]

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
            bid_value = attributes["bid_value"]

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
