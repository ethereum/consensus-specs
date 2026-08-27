"""Materialize canonical Gloas ``process_attestation`` gate cases."""

from __future__ import annotations

from typing import Any

from eth_consensus_specs.test.helpers.attestations import get_valid_attestation, sign_attestation
from eth_consensus_specs.test.helpers.genesis import create_genesis_state
from eth_consensus_specs.test.helpers.state import transition_to
from tests.generators.compliance_runners.state_transition.materializer import Materializer

from ...gen_base.gen_typing import TestCasePart

EPOCHS_PAST_GENESIS = 10
_DIMS = [
    "target_epoch_in_window",
    "target_epoch_matches_slot",
    "inclusion_delay_ok",
    "index_valid",
    "committee_indices_valid",
    "committee_nonempty",
    "aggregation_length_valid",
    "signature_valid",
    "target_is_current",
    "attestation_is_same_slot",
    "pending_payment_amount_positive",
    "sets_new_participation_flag",
    "payment_weight_increased",
    "outcome",
]
_GATES = _DIMS[:8]
_REJECTS = {
    "REJECT_TARGET_EPOCH_OUT_OF_WINDOW": 0,
    "REJECT_TARGET_EPOCH_SLOT_MISMATCH": 1,
    "REJECT_INCLUSION_DELAY": 2,
    "REJECT_INDEX": 3,
    "REJECT_COMMITTEE_INDEX": 4,
    "REJECT_COMMITTEE_EMPTY": 5,
    "REJECT_AGGREGATION_LENGTH": 6,
    "REJECT_SIGNATURE": 7,
}


def _b(sol: Any, name: str) -> bool:
    return bool(getattr(sol, name))


class AttestationMaterializer(Materializer):
    runner_name = "operations"
    handler_name = "attestation"

    def _base_state(self) -> Any:
        state = create_genesis_state(
            self.spec,
            validator_balances=[self.spec.MAX_EFFECTIVE_BALANCE] * 64,
            activation_threshold=self.spec.MAX_EFFECTIVE_BALANCE,
        )
        state.slot = self.spec.Slot(EPOCHS_PAST_GENESIS * self.spec.SLOTS_PER_EPOCH + 2)
        return state

    def materialize_solution(self, sol: Any) -> tuple[dict, list[TestCasePart]]:
        spec, pre = self.spec, self._base_state()
        same_slot = _b(sol, "attestation_is_same_slot")
        if same_slot:
            pre = create_genesis_state(
                spec,
                validator_balances=[spec.MAX_EFFECTIVE_BALANCE] * 64,
                activation_threshold=spec.MAX_EFFECTIVE_BALANCE,
            )
            transition_to(spec, pre, spec.Slot(spec.MIN_ATTESTATION_INCLUSION_DELAY))
        current = int(spec.get_current_epoch(pre))
        target_current = _b(sol, "target_is_current")
        target_matches_slot = _b(sol, "target_epoch_matches_slot")
        # For a mismatch, choose a slot from the opposite epoch first. This
        # preserves target_is_current while making the target/slot comparison
        # false; changing only the target epoch would invert that dimension.
        slot_target_current = target_current if target_matches_slot else not target_current
        slot = (
            0
            if same_slot
            else (
                int(pre.slot) - 1
                if slot_target_current
                else int(spec.compute_start_slot_at_epoch(current)) - 1
            )
        )
        committee = spec.get_beacon_committee(pre, spec.Slot(slot), 0)
        attestation = get_valid_attestation(
            spec,
            pre,
            slot=slot,
            index=0,
            signed=False,
            filter_participant_set=lambda _: {committee[0]},
        )
        data = attestation.data
        if not _b(sol, "target_epoch_in_window"):
            data.target.epoch = spec.Epoch(current + 1)
        elif not target_matches_slot:
            data.target.epoch = spec.Epoch(current if target_current else current - 1)
        if not _b(sol, "inclusion_delay_ok"):
            data.slot = pre.slot
            if _b(sol, "target_epoch_matches_slot"):
                data.target.epoch = spec.compute_epoch_at_slot(pre.slot)
        if not _b(sol, "index_valid"):
            data.index = spec.CommitteeIndex(2)
        if not _b(sol, "committee_indices_valid"):
            invalid = int(spec.get_committee_count_per_slot(pre, data.target.epoch))
            attestation.committee_bits[0] = False
            attestation.committee_bits[invalid] = True
        if not _b(sol, "committee_nonempty"):
            for i in range(len(attestation.aggregation_bits)):
                attestation.aggregation_bits[i] = False
        if not _b(sol, "aggregation_length_valid"):
            # Add an unused bit rather than removing one. A short bitfield can
            # make the preceding committee-attester access fail, changing this
            # intended length-only failure into an earlier failure.
            aggregation_bits = list(attestation.aggregation_bits) + [False]
            attestation.aggregation_bits = spec.AggregationBits(data=aggregation_bits)
        # These are pre-state properties. Materialize them independently of
        # whether a later gate permits the handler to consume the attestation.
        if same_slot and not _b(sol, "sets_new_participation_flag"):
            flags = pre.current_epoch_participation[committee[0]]
            for flag in range(len(spec.PARTICIPATION_FLAG_WEIGHTS)):
                flags = spec.add_flag(flags, flag)
            pre.current_epoch_participation[committee[0]] = flags
        if same_slot and _b(sol, "pending_payment_amount_positive"):
            payment_index = int(spec.SLOTS_PER_EPOCH) + slot % int(spec.SLOTS_PER_EPOCH)
            pre.builder_pending_payments[payment_index] = spec.BuilderPendingPayment(
                weight=spec.Gwei(0),
                withdrawal=spec.BuilderPendingWithdrawal(
                    fee_recipient=spec.ExecutionAddress(),
                    amount=spec.Gwei(1),
                    builder_index=spec.BuilderIndex(0),
                ),
            )
        if (
            _b(sol, "signature_valid")
            and _b(sol, "committee_indices_valid")
            and _b(sol, "committee_nonempty")
            and _b(sol, "aggregation_length_valid")
        ):
            sign_attestation(spec, pre, attestation)
        post = pre.copy()
        parent_slot = pre.latest_block_header.slot
        try:
            spec.process_attestation(post, attestation, parent_slot)
        except (AssertionError, IndexError):
            post = None
        claimed = {
            name: (_b(sol, name) if name != "outcome" else str(sol.outcome)) for name in _DIMS
        }
        meta = {
            "description": f"process_attestation: {claimed['outcome']}",
            "bls_setting": 1,
            "parent_slot": int(parent_slot),
            "claimed": claimed,
        }
        parts: list[TestCasePart] = [
            ("pre", "ssz", pre.encode_bytes()),
            ("attestation", "ssz", attestation.encode_bytes()),
        ]
        if post is not None:
            parts.append(("post", "ssz", post.encode_bytes()))
        return meta, parts
