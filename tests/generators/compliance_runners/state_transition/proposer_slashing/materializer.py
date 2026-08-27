"""Materialize aspect-model solutions for Gloas ``process_proposer_slashing``."""

from __future__ import annotations

from typing import Any

from eth_consensus_specs.test.helpers.genesis import create_genesis_state
from eth_consensus_specs.test.helpers.keys import pubkey_to_privkey
from eth_consensus_specs.utils import bls
from tests.generators.compliance_runners.state_transition.materializer import Materializer

from ...gen_base.gen_typing import TestCasePart

EPOCHS_PAST_GENESIS = 10
PROPOSER_INDEX = 1
FOREIGN_INDEX = 0
_DIMS = [
    "slots_match",
    "proposers_match",
    "headers_different",
    "signature_1_valid",
    "signature_2_valid",
    "proposer_slashed",
    "proposer_activated",
    "proposer_withdrawable",
    "proposer_exited",
    "payment_window",
    "payment_proposer_matches",
    "pending_payment_cleared",
    "state_effected",
    "outcome",
]


def _s(sol: Any, name: str) -> str:
    return str(getattr(sol, name))


def _b(sol: Any, name: str) -> bool:
    return bool(getattr(sol, name))


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

    def _sign(self, state: Any, header: Any, valid: bool) -> Any:
        if not valid:
            return self.spec.SignedBeaconBlockHeader(message=header)
        domain = self.spec.get_domain(
            state, self.spec.DOMAIN_BEACON_PROPOSER, self.spec.compute_epoch_at_slot(header.slot)
        )
        signature = bls.Sign(
            pubkey_to_privkey[state.validators[header.proposer_index].pubkey],
            self.spec.compute_signing_root(header, domain),
        )
        return self.spec.SignedBeaconBlockHeader(message=header, signature=signature)

    def materialize_solution(self, sol: Any) -> tuple[dict, list[TestCasePart]]:
        spec, pre = self.spec, self._base_state()
        current = int(spec.get_current_epoch(pre))
        proposer = pre.validators[PROPOSER_INDEX]
        proposer.slashed = _b(sol, "proposer_slashed")
        proposer.activation_epoch = spec.Epoch(0 if _b(sol, "proposer_activated") else current + 1)
        proposer.exit_epoch = spec.Epoch(
            current if _b(sol, "proposer_exited") else spec.FAR_FUTURE_EPOCH
        )
        proposer.withdrawable_epoch = spec.Epoch(
            current if _b(sol, "proposer_withdrawable") else spec.FAR_FUTURE_EPOCH
        )

        window = _s(sol, "payment_window")
        slot_1 = (
            int(pre.slot)
            - int(spec.SLOTS_PER_EPOCH) * {"CURRENT": 0, "PREVIOUS": 1, "OLD": 2}[window]
        )
        slot_2 = slot_1 if _b(sol, "slots_match") else slot_1 + 1
        proposer_2 = PROPOSER_INDEX if _b(sol, "proposers_match") else FOREIGN_INDEX
        root_2 = b"\x22" * 32 if _b(sol, "headers_different") else b"\x11" * 32
        h1 = spec.BeaconBlockHeader(
            slot=spec.Slot(slot_1),
            proposer_index=spec.ValidatorIndex(PROPOSER_INDEX),
            parent_root=b"\x11" * 32,
            state_root=b"\x33" * 32,
            body_root=b"\x44" * 32,
        )
        h2 = spec.BeaconBlockHeader(
            slot=spec.Slot(slot_2),
            proposer_index=spec.ValidatorIndex(proposer_2),
            parent_root=root_2,
            state_root=b"\x33" * 32,
            body_root=b"\x44" * 32,
        )
        slashing = spec.ProposerSlashing(
            signed_header_1=self._sign(pre, h1, _s(sol, "signature_1_valid") == "T"),
            signed_header_2=self._sign(pre, h2, _s(sol, "signature_2_valid") == "T"),
        )
        if window != "OLD":
            index = (int(spec.SLOTS_PER_EPOCH) if window == "CURRENT" else 0) + slot_1 % int(
                spec.SLOTS_PER_EPOCH
            )
            pre.builder_pending_payments[index] = spec.BuilderPendingPayment(
                weight=spec.Gwei(1),
                withdrawal=spec.BuilderPendingWithdrawal(
                    fee_recipient=spec.ExecutionAddress(b"\xaa" * 20),
                    amount=spec.Gwei(1),
                    builder_index=spec.BuilderIndex(0),
                ),
                proposer_index=spec.ValidatorIndex(
                    PROPOSER_INDEX if _s(sol, "payment_proposer_matches") == "T" else FOREIGN_INDEX
                ),
            )
        post = pre.copy()
        try:
            spec.process_proposer_slashing(post, slashing)
        except (AssertionError, IndexError):
            post = None
        claimed = {
            n: (_b(sol, n) if isinstance(getattr(sol, n), bool) else _s(sol, n)) for n in _DIMS
        }
        parts: list[TestCasePart] = [
            ("pre", "ssz", pre.encode_bytes()),
            ("proposer_slashing", "ssz", slashing.encode_bytes()),
        ]
        if post is not None:
            parts.append(("post", "ssz", post.encode_bytes()))
        meta = {"description": f"process_proposer_slashing: {claimed['outcome']}", "bls_setting": 1, "claimed": claimed}
        return meta, parts
