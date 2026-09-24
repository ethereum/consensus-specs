"""Materialize ``process_justification_and_finalization`` epoch vectors."""

from __future__ import annotations

from typing import Any, TYPE_CHECKING

from eth_consensus_specs.test.helpers.genesis import create_genesis_state
from tests.generators.compliance_runners.state_transition.materializer import Materializer

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
        reached = bool(getattr(solution, "past_initial_epochs", True))
        rule = int(getattr(solution, "finalization_path", 0))
        epoch = int(spec.GENESIS_EPOCH) + (2 if reached else 1)
        if rule in (1, 2):
            epoch = int(spec.GENESIS_EPOCH) + (3 if rule == 1 else 2)
            previous_epoch = epoch - (3 if rule == 1 else 2)
            pre.previous_justified_checkpoint = type(pre.previous_justified_checkpoint)(
                epoch=previous_epoch, root=pre.previous_justified_checkpoint.root
            )
            pre.current_justified_checkpoint = type(pre.current_justified_checkpoint)(
                epoch=epoch, root=pre.current_justified_checkpoint.root
            )
        elif rule in (3, 4):
            epoch = int(spec.GENESIS_EPOCH) + (2 if rule == 3 else 3)
            current_epoch = epoch - (2 if rule == 3 else 1)
            pre.current_justified_checkpoint = type(pre.current_justified_checkpoint)(
                epoch=current_epoch, root=pre.current_justified_checkpoint.root
            )
            pre.previous_justified_checkpoint = type(pre.previous_justified_checkpoint)(
                epoch=epoch, root=pre.previous_justified_checkpoint.root
            )
        # Epoch processing runs at the last slot of the epoch.
        pre.slot = spec.Slot((epoch + 1) * int(spec.SLOTS_PER_EPOCH) - 1)
        previous = bool(getattr(solution, "previous_epoch_supermajority", True))
        current = bool(getattr(solution, "current_epoch_supermajority", True))
        threshold_count = (2 * len(pre.validators) + 2) // 3
        for i in range(len(pre.validators)):
            pre.previous_epoch_participation[i] = spec.ParticipationFlags(
                (1 << int(spec.TIMELY_TARGET_FLAG_INDEX)) if previous and i < threshold_count else 0
            )
            pre.current_epoch_participation[i] = spec.ParticipationFlags(
                (1 << int(spec.TIMELY_TARGET_FLAG_INDEX)) if current and i < threshold_count else 0
            )
        bits = type(pre.justification_bits)()
        required = {1: (0, 1), 2: (0,), 3: (0,), 4: ()}.get(rule, ())
        for i in range(4):
            bits[i] = i in required
        pre.justification_bits = bits
        post = pre.copy()
        spec.process_justification_and_finalization(post)
        claimed = {str(k): v for k, v in vars(solution).items() if not str(k).startswith("_")}
        return {"description": "process_justification_and_finalization", "claimed": claimed}, [
            ("pre", "ssz", pre.encode_bytes()),
            ("post", "ssz", post.encode_bytes()),
        ]


MATERIALIZER = JustificationAndFinalizationMaterializer
