"""Materialize ``process_proposer_lookahead`` vectors."""

from __future__ import annotations

from typing import Any, TYPE_CHECKING

from eth_consensus_specs.test.helpers.genesis import create_genesis_state
from tests.generators.compliance_runners.state_transition.materializer import Materializer

from .target import CANDIDATES
from .witness import distinct_proposer_balances

if TYPE_CHECKING:
    from tests.generators.compliance_runners.gen_base.gen_typing import TestCasePart


class ProposerLookaheadMaterializer(Materializer):
    runner_name = "epoch_processing"
    handler_name = "proposer_lookahead"

    def materialize_solution(self, solution: Any) -> tuple[dict, list[TestCasePart]]:
        spec = self.spec
        slots = int(spec.SLOTS_PER_EPOCH)
        repeat = getattr(solution, "new_proposers_repeat", None)
        bucket = getattr(solution, "fewer_candidates_than_slots", "GT_FAR")
        active_candidates = {
            "LT_FAR": max(1, slots - 2),
            "LT_1": slots - 1,
            "EQ": slots,
            "GT_1": slots + 1,
            "GT_FAR": slots + 2,
        }[bucket]
        if CANDIDATES["fewer_candidates_than_slots"].abstract(active_candidates - slots) != bucket:
            raise ValueError(f"cannot realize candidate-count bucket {bucket!r} for {slots} slots")
        if repeat is False and active_candidates < slots:
            raise ValueError(
                "a no-repeat proposer list is impossible with fewer candidates than slots"
            )
        validator_count = max(64, active_candidates + 1)
        pre = create_genesis_state(
            spec,
            validator_balances=[spec.MAX_EFFECTIVE_BALANCE] * validator_count,
            activation_threshold=spec.MAX_EFFECTIVE_BALANCE,
        )
        slashed_active = bool(getattr(solution, "has_slashed_active_validator", False))
        old_slashed = bool(getattr(solution, "old_lookahead_contains_slashed", False))
        candidate_indices = set(self.rng.sample(range(len(pre.validators)), active_candidates))
        remaining_indices = [
            index for index in range(len(pre.validators)) if index not in candidate_indices
        ]
        slashed_active_index = self.rng.choice(remaining_indices) if slashed_active else None
        old_slashed_index = None
        if old_slashed:
            old_slashed_index = slashed_active_index
            if old_slashed_index is None:
                old_slashed_index = self.rng.choice(remaining_indices)
        for index, validator in enumerate(pre.validators):
            validator.slashed = index in {slashed_active_index, old_slashed_index}
            if index not in candidate_indices and index != slashed_active_index:
                validator.activation_epoch = spec.FAR_FUTURE_EPOCH
        if bool(getattr(solution, "new_proposers_repeat", False)):
            # Concentrate all effective balance in one of the candidate
            # validators so proposer selection deterministically repeats it.
            repeated_index = self.rng.choice(sorted(candidate_indices))
            for index in candidate_indices:
                pre.validators[index].effective_balance = spec.Gwei(
                    spec.MAX_EFFECTIVE_BALANCE if index == repeated_index else 0
                )
        pre.slot = spec.Slot((int(spec.GENESIS_EPOCH) + 1) * slots - 1)
        epoch = int(spec.get_current_epoch(pre)) + int(spec.MIN_SEED_LOOKAHEAD) + 1
        if repeat is False:
            # Fix the candidate count and solve draw acceptance thresholds.
            # This also realizes exact-size mainnet pools, where random search
            # for a distinct proposer list has an extremely low success rate.
            mix_index = (
                epoch + int(spec.EPOCHS_PER_HISTORICAL_VECTOR) - int(spec.MIN_SEED_LOOKAHEAD) - 1
            ) % len(pre.randao_mixes)
            indices = sorted(candidate_indices)
            for attempt in range(16):
                if attempt:
                    pre.randao_mixes[mix_index] = spec.Bytes32(
                        self.rng.getrandbits(256).to_bytes(32, "big")
                    )
                balances = distinct_proposer_balances(spec, pre, spec.Epoch(epoch), indices)
                if balances is not None:
                    for index, balance in zip(indices, balances, strict=True):
                        pre.validators[index].effective_balance = spec.Gwei(balance)
                        pre.validators[index].withdrawal_credentials = spec.Bytes32(
                            spec.COMPOUNDING_WITHDRAWAL_PREFIX
                            + bytes(pre.validators[index].withdrawal_credentials)[1:]
                        )
                        pre.balances[index] = spec.Gwei(balance)
                    break
            else:
                raise RuntimeError(
                    "could not realize distinct proposers within the witness search limit"
                )
        new = list(spec.get_beacon_proposer_indices(pre, spec.Epoch(epoch)))
        if repeat is False and len(set(new)) != len(new):
            raise RuntimeError("distinct-proposer witness did not match spec selection")
        old = list(pre.proposer_lookahead)
        split = len(old) - slots
        old[split:] = (
            new
            if bool(getattr(solution, "new_epoch_repeats_old_tail", True))
            else [spec.ValidatorIndex((int(index) + 1) % len(pre.validators)) for index in new]
        )
        if not old_slashed:
            # The genesis lookahead predates the requested slashing. Remove
            # references to that validator without changing the tail relation.
            for position, proposer_index in enumerate(old):
                if pre.validators[proposer_index].slashed:
                    replacement = next(
                        index
                        for index, validator in enumerate(pre.validators)
                        if not validator.slashed
                        and (position < split or index != int(new[position - split]))
                    )
                    old[position] = spec.ValidatorIndex(replacement)
        if old_slashed:
            assert old_slashed_index is not None
            old[0] = spec.ValidatorIndex(old_slashed_index)
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
