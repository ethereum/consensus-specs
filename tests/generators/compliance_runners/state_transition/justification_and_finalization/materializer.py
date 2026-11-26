"""Materialize ``process_justification_and_finalization`` epoch vectors."""

from __future__ import annotations

from typing import Any, TYPE_CHECKING

from eth_consensus_specs.test.helpers.genesis import create_genesis_state
from tests.generators.compliance_runners.state_transition.materializer import Materializer

from .target import TARGET

if TYPE_CHECKING:
    from tests.generators.compliance_runners.gen_base.gen_typing import TestCasePart


class JustificationAndFinalizationMaterializer(Materializer):
    runner_name = "epoch_processing"
    handler_name = "justification_and_finalization"

    def materialize_solution(self, solution: Any) -> tuple[dict, list[TestCasePart]]:
        spec = self.spec
        pre = create_genesis_state(
            spec,
            validator_balances=[spec.MAX_EFFECTIVE_BALANCE] * 64,
            activation_threshold=spec.MAX_EFFECTIVE_BALANCE,
        )
        reached = solution.past_initial_epochs
        rule = int(solution.finalization_path) if reached else 0
        previous = reached and solution.previous_epoch_supermajority
        carried = rule in (1, 2) and not previous
        setup_rule = rule
        if carried:
            # One epoch earlier, rule 3 leaves three justified bits and rule 4 leaves two.
            setup_rule = 3 if rule == 1 else 4
            previous = setup_rule == 3
        genesis = int(spec.GENESIS_EPOCH)
        epoch = genesis + (8 if rule else 2 if reached else 1)
        pre.slot = spec.Slot((epoch + 1) * int(spec.SLOTS_PER_EPOCH) - 1)
        for i in range(genesis + 1, epoch + 1):
            slot = spec.compute_start_slot_at_epoch(spec.Epoch(i))
            pre.block_roots[slot % spec.SLOTS_PER_HISTORICAL_ROOT] = spec.Root(
                self.rng.getrandbits(256).to_bytes(32, "big")
            )
        required = ()
        if setup_rule:
            previous_age, current_age, required = {
                1: (3, 2, (1, 2)),
                2: (2, 2, (1,)),
                3: (4, 2, (1,)),
                4: (4, 1, (0,)),
            }[setup_rule]
            previous_justified_epoch = spec.Epoch(epoch - previous_age)
            current_justified_epoch = spec.Epoch(epoch - current_age)
            pre.previous_justified_checkpoint = spec.Checkpoint(
                epoch=previous_justified_epoch,
                root=spec.get_block_root(pre, previous_justified_epoch),
            )
            pre.current_justified_checkpoint = spec.Checkpoint(
                epoch=current_justified_epoch,
                root=spec.get_block_root(pre, current_justified_epoch),
            )
        # At the guard, current support makes an accidental justification observable.
        current = not reached or carried or solution.current_epoch_supermajority
        threshold_count = (2 * len(pre.validators) + 2) // 3
        previous_participants = (
            set(self.rng.sample(range(len(pre.validators)), threshold_count)) if previous else set()
        )
        current_participants = (
            set(self.rng.sample(range(len(pre.validators)), threshold_count)) if current else set()
        )
        for i in range(len(pre.validators)):
            pre.previous_epoch_participation[i] = spec.ParticipationFlags(
                (1 << int(spec.TIMELY_TARGET_FLAG_INDEX)) if i in previous_participants else 0
            )
            pre.current_epoch_participation[i] = spec.ParticipationFlags(
                (1 << int(spec.TIMELY_TARGET_FLAG_INDEX)) if i in current_participants else 0
            )
        bits = type(pre.justification_bits)()
        for i in range(4):
            bits[i] = i in required
        pre.justification_bits = bits
        if carried:
            spec.process_slots(pre, pre.slot + spec.SLOTS_PER_EPOCH)
            # Participation rolls over, but the slashed vote no longer counts toward the threshold.
            spec.slash_validator(pre, spec.ValidatorIndex(min(current_participants)))
        # Epoch processing starts after process_slot has cached the final slot's roots.
        spec.process_slot(pre)
        post = pre.copy()
        spec.process_justification_and_finalization(post)
        claimed = self.claimed_record(TARGET, solution)
        return {"description": "process_justification_and_finalization", "claimed": claimed}, [
            ("pre", "ssz", pre.encode_bytes()),
            ("post", "ssz", post.encode_bytes()),
        ]


MATERIALIZER = JustificationAndFinalizationMaterializer
