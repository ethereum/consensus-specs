"""Materialize canonical Gloas ``process_attestation`` gate cases."""

from __future__ import annotations

from typing import Any, TYPE_CHECKING

from eth_consensus_specs.test.helpers.attestations import get_valid_attestation, sign_attestation
from eth_consensus_specs.test.helpers.genesis import create_genesis_state
from eth_consensus_specs.test.helpers.state import transition_to
from tests.generators.compliance_runners.state_transition.aspects_helpers.byte_witness import (
    distinct_bytes,
)
from tests.generators.compliance_runners.state_transition.materializer import Materializer
from tests.generators.compliance_runners.state_transition.validation_helpers import bls_enabled

from .target import TARGET

if TYPE_CHECKING:
    from tests.generators.compliance_runners.gen_base.gen_typing import TestCasePart

EPOCHS_PAST_GENESIS = 10


class AttestationMaterializer(Materializer):
    runner_name = "operations"
    handler_name = "attestation"

    def _base_state(self) -> Any:
        state = create_genesis_state(
            self.spec,
            validator_balances=[self.spec.MAX_EFFECTIVE_BALANCE] * 64,
            activation_threshold=self.spec.MAX_EFFECTIVE_BALANCE,
        )
        state.slot = self.spec.Slot(
            self.rng.randrange(2, EPOCHS_PAST_GENESIS + 1) * self.spec.SLOTS_PER_EPOCH
            + self.rng.randrange(1, self.spec.SLOTS_PER_EPOCH)
        )
        return state

    def materialize_solution(self, sol: Any) -> tuple[dict, list[TestCasePart]]:
        spec, pre = self.spec, self._base_state()
        same_slot = sol.attestation_is_same_slot
        if same_slot:
            pre = create_genesis_state(
                spec,
                validator_balances=[spec.MAX_EFFECTIVE_BALANCE] * 64,
                activation_threshold=spec.MAX_EFFECTIVE_BALANCE,
            )
            transition_to(spec, pre, spec.Slot(spec.MIN_ATTESTATION_INCLUSION_DELAY))
        current = int(spec.get_current_epoch(pre))
        target_current = sol.target_is_current
        target_matches_slot = sol.target_epoch_matches_slot
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
        participant = self.rng.choice(committee)
        attestation = get_valid_attestation(
            spec,
            pre,
            slot=slot,
            index=0,
            signed=False,
            filter_participant_set=lambda _: {participant},
        )
        data = attestation.data
        if not sol.target_epoch_in_window:
            data.target.epoch = spec.Epoch(current + 1)
        elif not target_matches_slot:
            data.target.epoch = spec.Epoch(current if target_current else current - 1)
        if not sol.inclusion_delay_ok:
            data.slot = pre.slot
            if sol.target_epoch_matches_slot:
                data.target.epoch = spec.compute_epoch_at_slot(pre.slot)
        if not sol.index_valid:
            data.index = spec.CommitteeIndex(2)
        if not sol.committee_indices_valid:
            invalid = int(spec.get_committee_count_per_slot(pre, data.target.epoch))
            attestation.committee_bits[0] = False
            attestation.committee_bits[invalid] = True
        if not sol.committee_nonempty:
            for i in range(len(attestation.aggregation_bits)):
                attestation.aggregation_bits[i] = False
        if not sol.aggregation_length_valid:
            # Add an unused bit rather than removing one. A short bitfield can
            # make the preceding committee-attester access fail, changing this
            # intended length-only failure into an earlier failure.
            aggregation_bits = list(attestation.aggregation_bits) + [False]
            attestation.aggregation_bits = spec.AggregationBits(data=aggregation_bits)
        # These are pre-state properties. Materialize them independently of
        # whether a later gate permits the handler to consume the attestation.
        if same_slot and not sol.sets_new_participation_flag:
            flags = pre.current_epoch_participation[participant]
            for flag in range(len(spec.PARTICIPATION_FLAG_WEIGHTS)):
                flags = spec.add_flag(flags, flag)
            pre.current_epoch_participation[participant] = flags
        if same_slot and sol.pending_payment_amount_positive:
            payment_index = int(spec.SLOTS_PER_EPOCH) + slot % int(spec.SLOTS_PER_EPOCH)
            fee_recipient, _ = distinct_bytes(self.rng, 20)
            pre.builder_pending_payments[payment_index] = spec.BuilderPendingPayment(
                weight=spec.Gwei(self.rng.randrange(1001)),
                withdrawal=spec.BuilderPendingWithdrawal(
                    fee_recipient=spec.ExecutionAddress(fee_recipient),
                    amount=spec.Gwei(self.rng.randrange(1, 1001)),
                    builder_index=spec.BuilderIndex(self.rng.randrange(64)),
                ),
                proposer_index=spec.ValidatorIndex(self.rng.randrange(len(pre.validators))),
            )
        if (
            sol.signature_valid
            and sol.committee_indices_valid
            and sol.committee_nonempty
            and sol.aggregation_length_valid
        ):
            with bls_enabled():
                sign_attestation(spec, pre, attestation)
        post = pre.copy()
        parent_slot = pre.latest_block_header.slot
        try:
            with bls_enabled():
                spec.process_attestation(post, attestation, parent_slot)
        except (AssertionError, IndexError):
            post = None
        claimed = self.claimed_record(TARGET, sol)
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


MATERIALIZER = AttestationMaterializer
