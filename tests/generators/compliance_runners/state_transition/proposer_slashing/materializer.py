"""Materialize declaration witnesses for Gloas ``process_proposer_slashing``."""

from __future__ import annotations

from typing import Any, TYPE_CHECKING

from eth_consensus_specs.test.helpers.genesis import create_genesis_state
from eth_consensus_specs.test.helpers.keys import pubkey_to_privkey
from eth_consensus_specs.utils import bls
from tests.generators.compliance_runners.state_transition.aspects_helpers.byte_witness import (
    distinct_bytes,
)
from tests.generators.compliance_runners.state_transition.aspects_helpers.entity_reference import (
    distinct_indices,
)
from tests.generators.compliance_runners.state_transition.materializer import Materializer
from tests.generators.compliance_runners.state_transition.validation_helpers import bls_enabled

from .target import TARGET

if TYPE_CHECKING:
    from tests.generators.compliance_runners.gen_base.gen_typing import TestCasePart

EPOCHS_PAST_GENESIS = 10


class ProposerSlashingMaterializer(Materializer):
    runner_name = "operations"
    handler_name = "proposer_slashing"

    def _base_state(self) -> Any:
        state = create_genesis_state(
            self.spec,
            validator_balances=[self.spec.MAX_EFFECTIVE_BALANCE] * 64,
            activation_threshold=self.spec.MAX_EFFECTIVE_BALANCE,
        )
        state.slot = self.spec.Slot(EPOCHS_PAST_GENESIS * self.spec.SLOTS_PER_EPOCH)
        return state

    def _sign(self, state: Any, header: Any, valid: bool, proposer_index: int) -> Any:
        if not valid:
            return self.spec.SignedBeaconBlockHeader(message=header)
        domain = self.spec.get_domain(
            state, self.spec.DOMAIN_BEACON_PROPOSER, self.spec.compute_epoch_at_slot(header.slot)
        )
        with bls_enabled():
            signature = bls.Sign(
                pubkey_to_privkey[state.validators[proposer_index].pubkey],
                self.spec.compute_signing_root(header, domain),
            )
        return self.spec.SignedBeaconBlockHeader(message=header, signature=signature)

    def materialize_solution(self, sol: Any) -> tuple[dict, list[TestCasePart]]:
        spec, pre = self.spec, self._base_state()
        current = int(spec.get_current_epoch(pre))
        proposer_index, foreign_index = distinct_indices(self.rng, len(pre.validators), 2)
        proposer = pre.validators[proposer_index]
        proposer.slashed = not sol.proposer_not_slashed
        proposer.activation_epoch = spec.Epoch(0 if sol.proposer_activated else current + 1)
        proposer.exit_epoch = spec.Epoch(current if sol.exit_initiated else spec.FAR_FUTURE_EPOCH)
        proposer.withdrawable_epoch = spec.Epoch(
            spec.FAR_FUTURE_EPOCH if sol.proposer_not_withdrawable else current
        )

        variant = sol.churn_variant
        if variant == "CARRY_OVERFLOW":
            proposer.withdrawal_credentials = spec.Bytes32(
                spec.COMPOUNDING_WITHDRAWAL_PREFIX + bytes(31)
            )
            proposer.effective_balance = spec.Gwei(int(spec.MAX_EFFECTIVE_BALANCE_ELECTRA))
            pre.balances[proposer_index] = spec.Gwei(int(spec.MAX_EFFECTIVE_BALANCE_ELECTRA))
        activation_epoch = int(spec.compute_activation_exit_epoch(spec.get_current_epoch(pre)))
        if variant == "RESET_FIT":
            pre.earliest_exit_epoch = spec.Epoch(max(0, activation_epoch - 1))
            pre.exit_balance_to_consume = spec.Gwei(0)
        elif variant == "CARRY_FIT":
            pre.earliest_exit_epoch = spec.Epoch(activation_epoch)
            pre.exit_balance_to_consume = proposer.effective_balance
        elif variant == "CARRY_OVERFLOW":
            pre.earliest_exit_epoch = spec.Epoch(activation_epoch + 1)
            pre.exit_balance_to_consume = spec.Gwei(1)

        window = sol.payment_window
        slot_1 = (
            int(pre.slot)
            - int(spec.SLOTS_PER_EPOCH) * {"CURRENT": 0, "PREVIOUS": 1, "OLD": 2}[window]
        )
        slot_2 = slot_1 if sol.slots_match else slot_1 + 1
        proposer_2 = proposer_index if sol.proposers_match else foreign_index
        parent_root, other_parent_root = distinct_bytes(self.rng, 32)
        state_root, _ = distinct_bytes(self.rng, 32)
        body_root, _ = distinct_bytes(self.rng, 32)
        h1 = spec.BeaconBlockHeader(
            slot=spec.Slot(slot_1),
            proposer_index=spec.ValidatorIndex(proposer_index),
            parent_root=parent_root,
            state_root=state_root,
            body_root=body_root,
        )
        h2 = spec.BeaconBlockHeader(
            slot=spec.Slot(slot_2),
            proposer_index=spec.ValidatorIndex(proposer_2),
            parent_root=other_parent_root if sol.headers_different else parent_root,
            state_root=state_root,
            body_root=body_root,
        )
        slashing = spec.ProposerSlashing(
            signed_header_1=self._sign(pre, h1, sol.signature_1_valid, proposer_index),
            signed_header_2=self._sign(pre, h2, sol.signature_2_valid, proposer_index),
        )
        if window != "OLD":
            index = (int(spec.SLOTS_PER_EPOCH) if window == "CURRENT" else 0) + slot_1 % int(
                spec.SLOTS_PER_EPOCH
            )
            payment_address, _ = distinct_bytes(self.rng, 20)
            pre.builder_pending_payments[index] = spec.BuilderPendingPayment(
                weight=spec.Gwei(self.rng.randrange(1, 1_000_000_001)),
                withdrawal=spec.BuilderPendingWithdrawal(
                    fee_recipient=spec.ExecutionAddress(payment_address),
                    amount=spec.Gwei(self.rng.randrange(1, 1_000_000_001)),
                    builder_index=spec.BuilderIndex(self.rng.randrange(64)),
                ),
                proposer_index=spec.ValidatorIndex(
                    proposer_index if sol.payment_proposer_matches else foreign_index
                ),
            )
        post = pre.copy()
        try:
            with bls_enabled():
                spec.process_proposer_slashing(post, slashing)
        except (AssertionError, IndexError):
            post = None
        claimed = self.claimed_record(TARGET, sol)
        parts: list[TestCasePart] = [
            ("pre", "ssz", pre.encode_bytes()),
            ("proposer_slashing", "ssz", slashing.encode_bytes()),
        ]
        if post is not None:
            parts.append(("post", "ssz", post.encode_bytes()))
        meta = {
            "description": f"process_proposer_slashing: {'ACCEPT' if claimed['accepted'] else 'REJECT'}",
            "bls_setting": 1,
            "claimed": claimed,
        }
        return meta, parts


MATERIALIZER = ProposerSlashingMaterializer
