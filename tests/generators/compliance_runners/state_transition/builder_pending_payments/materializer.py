"""Build epoch-entry states from bids whose execution payloads were missed."""

from __future__ import annotations

from functools import cached_property
from typing import TYPE_CHECKING

from eth_consensus_specs.test.helpers.attestations import get_valid_attestations_for_block_at_slot
from eth_consensus_specs.test.helpers.block import build_empty_block
from eth_consensus_specs.test.helpers.epoch_processing import run_epoch_processing_to
from eth_consensus_specs.test.helpers.genesis import create_genesis_state
from eth_consensus_specs.test.helpers.keys import builder_privkeys
from eth_consensus_specs.utils import bls
from tests.generators.compliance_runners.state_transition.materializer import Materializer
from tests.generators.compliance_runners.state_transition.materializer.common import (
    finalize_genesis_builders,
)
from tests.generators.compliance_runners.state_transition.validation_helpers import bls_enabled

from .target import TARGET

if TYPE_CHECKING:
    from tests.generators.compliance_runners.gen_base.gen_typing import TestCasePart


class BuilderPendingPaymentsMaterializer(Materializer):
    runner_name = "epoch_processing"
    handler_name = "builder_pending_payments"

    @cached_property
    def _active_state(self):
        spec = self.spec
        balance = spec.MAX_EFFECTIVE_BALANCE
        # Both presets get a whole number of attesters at the 60% quorum:
        # 12 of 20 per minimal slot and 3 of 5 per mainnet slot.
        state = create_genesis_state(spec, [balance] * 160, balance, builder_count=2)
        return finalize_genesis_builders(spec, state)

    @cached_property
    def _quorum_attesters(self):
        spec = self.spec
        quorum = spec.get_builder_payment_quorum_threshold(self._active_state)
        attesters, remainder = divmod(int(quorum), int(spec.MAX_EFFECTIVE_BALANCE))
        assert remainder == 0
        return attesters

    def _append_attestation(self, state, block, slot, count):
        spec = self.spec
        committee_count = spec.get_committee_count_per_slot(state, spec.compute_epoch_at_slot(slot))
        participants = [
            index
            for committee in range(committee_count)
            for index in spec.get_beacon_committee(state, slot, committee)
        ]
        assert len(participants) >= count
        selected = set(participants[:count])
        for attestation in get_valid_attestations_for_block_at_slot(
            spec,
            state,
            slot,
            participation_fn=lambda _, __, members: selected.intersection(members),
            payload_index=0,
        ):
            block.body.attestations.append(attestation)

    def _process_block(self, state, *, paid, attestations=()):
        spec = self.spec
        with bls_enabled():
            block = build_empty_block(spec, state)
            for slot, count in attestations:
                if count:
                    self._append_attestation(state, block, slot, count)
            if paid:
                bid = block.body.signed_execution_payload_bid.message
                # Descendants extend the beacon block with this payload missing.
                bid.block_hash = spec.Hash32(state.slot.to_bytes(32, "little"))
                bid.builder_index = spec.BuilderIndex(state.slot % len(state.builders))
                bid.fee_recipient = spec.ExecutionAddress(
                    spec.sha256(state.slot.to_bytes(8, "little"))[12:]
                )
                bid.value = spec.Gwei(state.slot + self.seed % 1_000)
                domain = spec.get_domain(state, spec.DOMAIN_BEACON_BUILDER)
                signature = bls.Sign(
                    builder_privkeys[bid.builder_index], spec.compute_signing_root(bid, domain)
                )
                block.body.signed_execution_payload_bid = spec.SignedExecutionPayloadBid(
                    message=bid, signature=signature
                )
            spec.process_block(state, block)

    @staticmethod
    def _payment_offsets(payment_count):
        # Sparse occupancies exercise scanning past gaps and preserving ring offsets.
        if payment_count == 1:
            return (1,)
        if payment_count == 3:
            return (0, 2, 5)
        return range(payment_count)

    def _include_bids(self, state, bids):
        """Include bids at the selected offsets and attest in the next block."""
        spec = self.spec
        first_slot = state.slot
        parent_attesters = 0
        for offset, count in bids:
            if offset:
                spec.process_slots(state, first_slot + offset)
            self._process_block(
                state, paid=True, attestations=((state.latest_block_header.slot, parent_attesters),)
            )
            parent_attesters = count
        if parent_attesters:
            parent_slot = state.slot
            spec.process_slots(state, parent_slot + 1)
            self._process_block(state, paid=False, attestations=((parent_slot, parent_attesters),))

    @cached_property
    def _epoch_starts(self):
        return {(): self._active_state}

    def _epoch_start_after(self, bids_by_epoch):
        if bids_by_epoch not in self._epoch_starts:
            spec = self.spec
            state = self._epoch_start_after(bids_by_epoch[:-1]).copy()
            next_epoch = spec.get_current_epoch(state) + 1
            self._include_bids(state, bids_by_epoch[-1])
            spec.process_slots(state, spec.compute_start_slot_at_epoch(next_epoch))
            self._epoch_starts[bids_by_epoch] = state
        return self._epoch_starts[bids_by_epoch]

    @cached_property
    def _last_slot_states(self):
        return {}

    def _state_at_last_slot(self, withdrawal_count, previous_count, retained_count):
        key = (withdrawal_count, previous_count, retained_count)
        if key not in self._last_slot_states:
            spec = self.spec
            # Quorum payments from two epochs ago enter the withdrawal queue at
            # the preceding boundary. Empty-parent blocks leave them queued.
            older_bids = tuple((i, self._quorum_attesters) for i in range(withdrawal_count))
            previous_bids = tuple((i, 0) for i in self._payment_offsets(previous_count))
            state = self._epoch_start_after((older_bids, previous_bids)).copy()
            slots = spec.SLOTS_PER_EPOCH
            last_slot = state.slot + slots - 1
            # Keep an above-quorum payment in the section that will rotate.
            self._include_bids(
                state,
                (
                    (offset, self._quorum_attesters + 1 if i == 0 else 0)
                    for i, offset in enumerate(self._payment_offsets(retained_count))
                    if offset < slots - 1
                ),
            )
            spec.process_slots(state, last_slot)
            self._last_slot_states[key] = state
        return self._last_slot_states[key].copy()

    def _previous_epoch_attesters(self, sol, payment_count):
        if not payment_count:
            return ()
        quorum = self._quorum_attesters
        counts_by_relation = {"LT": quorum - 1, "EQ": quorum, "GT": quorum + 1}
        relation = sol.target_weight_to_quorum
        counts = [counts_by_relation[relation]]
        if sol.mixed_quorum_relations:
            counts.extend((quorum, quorum + 1))
        else:
            qualifiers = {"ZERO": 0, "ONE": 1, "MANY": 2}[sol.qualifying_payment_count]
            # Use the target's qualifying weight again to avoid introducing
            # both EQ and GT when other payments are below quorum.
            qualifying_weight = max(counts[0], quorum)
            counts.extend([qualifying_weight] * (qualifiers - int(relation != "LT")))
        last_attested_offset = len(counts) - 1
        counts.extend([0] * (payment_count - len(counts)))
        if payment_count == self.spec.SLOTS_PER_EPOCH and last_attested_offset > 0:
            # Keep the first bid's quorum relation and qualify the final slot as well.
            counts[-1], counts[last_attested_offset] = counts[last_attested_offset], 0
        return tuple(counts)

    def materialize_solution(self, sol) -> tuple[dict, list[TestCasePart]]:
        spec = self.spec
        slots = int(spec.SLOTS_PER_EPOCH)
        occupancy = {"EMPTY": 0, "SINGLE": 1, "MULTIPLE": 3, "FULL": slots}
        withdrawal_count = {"ZERO": 0, "ONE": 1, "MANY": 2}[sol.preexisting_withdrawals_occupancy]
        previous_count = occupancy[sol.previous_epoch_occupancy]
        retained_count = occupancy[sol.next_epoch_payments_occupancy]
        pre = self._state_at_last_slot(withdrawal_count, previous_count, retained_count)
        # Previous-epoch attestations are still valid here. Including them in
        # the final block shares the preceding history between quorum cases.
        previous_start = spec.compute_start_slot_at_epoch(spec.get_previous_epoch(pre))
        attestations = tuple(
            (previous_start + offset, count)
            for offset, count in zip(
                self._payment_offsets(previous_count),
                self._previous_epoch_attesters(sol, previous_count),
                strict=True,
            )
            if count
        )
        if attestations or retained_count == slots:
            self._process_block(pre, paid=retained_count == slots, attestations=attestations)
        run_epoch_processing_to(spec, pre, "process_builder_pending_payments")

        post = pre.copy()
        spec.process_builder_pending_payments(post)
        claimed = self.claimed_record(TARGET, sol)
        meta = {"description": "process_builder_pending_payments", "claimed": claimed}
        parts = [("pre", "ssz", pre.encode_bytes()), ("post", "ssz", post.encode_bytes())]
        return meta, parts


MATERIALIZER = BuilderPendingPaymentsMaterializer
