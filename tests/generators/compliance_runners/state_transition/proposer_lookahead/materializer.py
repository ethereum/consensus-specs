"""Materialize ``process_proposer_lookahead`` vectors."""

from __future__ import annotations

from typing import Any, TYPE_CHECKING

from eth_consensus_specs.test.helpers.genesis import create_genesis_state
from tests.generators.compliance_runners.state_transition.materializer import Materializer

if TYPE_CHECKING:
    from tests.generators.compliance_runners.gen_base.gen_typing import TestCasePart


class ProposerLookaheadMaterializer(Materializer):
    runner_name = "epoch_processing"
    handler_name = "proposer_lookahead"

    def materialize_solution(self, solution: Any) -> tuple[dict, list[TestCasePart]]:
        spec = self.spec
        slots = int(spec.SLOTS_PER_EPOCH)
        repeat = getattr(solution, "new_proposers_repeat", None)
        validator_count = max(64, slots * 64) if repeat is False else 64
        pre = create_genesis_state(
            spec,
            validator_balances=[spec.MAX_EFFECTIVE_BALANCE] * validator_count,
            activation_threshold=spec.MAX_EFFECTIVE_BALANCE,
        )
        fewer = bool(getattr(solution, "fewer_candidates_than_slots", False))
        slashed_active = bool(getattr(solution, "has_slashed_active_validator", False))
        old_slashed = bool(getattr(solution, "old_lookahead_contains_slashed", False))
        active_candidates = (
            max(1, slots - 1) if fewer else len(pre.validators) - int(slashed_active or old_slashed)
        )
        for i, validator in enumerate(pre.validators):
            validator.slashed = slashed_active and i == active_candidates
            if i >= active_candidates + int(slashed_active):
                validator.activation_epoch = spec.FAR_FUTURE_EPOCH
        if bool(getattr(solution, "new_proposers_repeat", False)):
            # Concentrate all effective balance in one of the candidate
            # validators so proposer selection deterministically repeats it.
            for i in range(active_candidates):
                pre.validators[i].effective_balance = spec.Gwei(
                    spec.MAX_EFFECTIVE_BALANCE if i == 0 else 0
                )
        if old_slashed:
            pre.validators[-1].slashed = True
        pre.slot = spec.Slot((int(spec.GENESIS_EPOCH) + 1) * slots - 1)
        epoch = int(spec.get_current_epoch(pre)) + int(spec.MIN_SEED_LOOKAHEAD) + 1
        new = list(spec.get_beacon_proposer_indices(pre, spec.Epoch(epoch)))
        if repeat is False and fewer:
            raise ValueError(
                "a no-repeat proposer list is impossible with fewer candidates than slots"
            )
        if repeat is False and not fewer:
            # Proposer selection is randomized by the RANDAO mix. A uniform
            # validator set can repeat by chance, so search deterministic
            # mixes until this vector realizes the requested no-repeat case.
            mix_index = (
                epoch + int(spec.EPOCHS_PER_HISTORICAL_VECTOR) - int(spec.MIN_SEED_LOOKAHEAD) - 1
            ) % len(pre.randao_mixes)
            found = False
            for candidate in range(256):
                pre.randao_mixes[mix_index] = spec.Bytes32(candidate.to_bytes(32, "little"))
                new = list(spec.get_beacon_proposer_indices(pre, spec.Epoch(epoch)))
                if len(set(new)) == len(new):
                    found = True
                    break
            if not found:
                raise RuntimeError(
                    "could not materialize a no-repeat proposer list after 256 RANDAO mixes"
                )
        old = list(pre.proposer_lookahead)
        split = len(old) - slots
        old[split:] = (
            new
            if bool(getattr(solution, "new_epoch_repeats_old_tail", True))
            else [spec.ValidatorIndex((int(index) + 1) % len(pre.validators)) for index in new]
        )
        if old_slashed:
            old[0] = spec.ValidatorIndex(len(pre.validators) - 1)
        for index, proposer_index in enumerate(old):
            pre.proposer_lookahead[index] = proposer_index
        post = pre.copy()
        spec.process_proposer_lookahead(post)
        claimed = {str(k): v for k, v in vars(solution).items() if not str(k).startswith("_")}
        return {"description": "process_proposer_lookahead", "claimed": claimed}, [
            ("pre", "ssz", pre.encode_bytes()),
            ("post", "ssz", post.encode_bytes()),
        ]


MATERIALIZER = ProposerLookaheadMaterializer
