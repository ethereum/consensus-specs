"""Materialize canonical Gloas ``process_attestation`` gate cases."""

from __future__ import annotations

from functools import cached_property
from typing import Any, TYPE_CHECKING

from eth_consensus_specs.test.helpers.attestations import (
    get_valid_attestation,
    next_epoch_with_attestations,
    sign_attestation,
)
from eth_consensus_specs.test.helpers.block import build_empty_block
from eth_consensus_specs.test.helpers.genesis import create_genesis_state
from eth_consensus_specs.test.helpers.keys import builder_privkeys
from eth_consensus_specs.utils import bls
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

    @cached_property
    def _genesis_state(self) -> Any:
        return create_genesis_state(
            self.spec,
            validator_balances=[self.spec.MAX_EFFECTIVE_BALANCE] * 64,
            activation_threshold=self.spec.MAX_EFFECTIVE_BALANCE,
        )

    @cached_property
    def _finalized_state(self) -> Any:
        spec = self.spec
        state = self._genesis_state
        with bls_enabled():
            # The first two epoch transitions skip justification. The next
            # two justify consecutive checkpoints and finalize past genesis.
            for _ in range(4):
                _, _, state = next_epoch_with_attestations(
                    spec, state, fill_cur_epoch=True, fill_prev_epoch=False
                )
        assert state.finalized_checkpoint.epoch > spec.GENESIS_EPOCH
        return state

    def materialize_solution(self, sol: Any) -> tuple[dict, list[TestCasePart]]:
        spec = self.spec
        same_slot = sol.attestation_is_same_slot
        target_current = sol.target_is_current
        target_matches_slot = sol.target_epoch_matches_slot
        if same_slot:
            pre = self._finalized_state.copy()
            # The finality history already includes a block at its last slot.
            slot = pre.slot + 1
            spec.process_slots(pre, slot)
            with bls_enabled():
                block = build_empty_block(spec, pre)
                if sol.pending_payment_amount_positive:
                    bid = block.body.signed_execution_payload_bid.message.copy()
                    bid.builder_index = spec.BuilderIndex(self.rng.randrange(len(pre.builders)))
                    bid.value = spec.Gwei(self.rng.randrange(1, 1001))
                    bid.fee_recipient = spec.ExecutionAddress(distinct_bytes(self.rng, 20)[0])
                    domain = spec.get_domain(pre, spec.DOMAIN_BEACON_BUILDER)
                    block.body.signed_execution_payload_bid = spec.SignedExecutionPayloadBid(
                        message=bid,
                        signature=bls.Sign(
                            builder_privkeys[bid.builder_index],
                            spec.compute_signing_root(bid, domain),
                        ),
                    )
                spec.process_block(pre, block)
            spec.process_slots(pre, slot + spec.MIN_ATTESTATION_INCLUSION_DELAY)
        else:
            pre = self._genesis_state.copy()
            pre.slot = spec.Slot(
                self.rng.randrange(2, EPOCHS_PAST_GENESIS + 1) * spec.SLOTS_PER_EPOCH
                + self.rng.randrange(1, spec.SLOTS_PER_EPOCH)
            )
            # For a mismatch, take the slot from the opposite epoch so the
            # declared target epoch remains current or previous as requested.
            slot_target_current = target_current if target_matches_slot else not target_current
            slot = (
                pre.slot - 1
                if slot_target_current
                else spec.compute_start_slot_at_epoch(spec.get_current_epoch(pre)) - 1
            )
        current = int(spec.get_current_epoch(pre))
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
        parent_slot = pre.latest_block_header.slot
        if same_slot and not sol.sets_new_participation_flag:
            # Process a valid copy first so participation and payment weight
            # reflect the same prior attestation.
            previous = attestation.copy()
            with bls_enabled():
                sign_attestation(spec, pre, previous)
                spec.process_attestation(pre, previous, parent_slot)
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
        if (
            sol.signature_valid
            and sol.committee_indices_valid
            and sol.committee_nonempty
            and sol.aggregation_length_valid
        ):
            with bls_enabled():
                sign_attestation(spec, pre, attestation)
        post = pre.copy()
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
