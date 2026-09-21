"""Materialize Gloas ``process_participation_flag_updates`` epoch vectors."""

from __future__ import annotations

from typing import Any, TYPE_CHECKING

from eth_consensus_specs.test.helpers.genesis import create_genesis_state
from tests.generators.compliance_runners.state_transition.materializer import Materializer

if TYPE_CHECKING:
    from tests.generators.compliance_runners.gen_base.gen_typing import TestCasePart


class ParticipationFlagUpdatesMaterializer(Materializer):
    runner_name = "epoch_processing"
    handler_name = "participation_flag_updates"

    def materialize_solution(self, solution: Any) -> tuple[dict, list[TestCasePart]]:
        spec = self.spec
        minimum_validator_count = int(spec.config.MIN_GENESIS_ACTIVE_VALIDATOR_COUNT)
        validator_count = (
            minimum_validator_count + 1
            if bool(getattr(solution, "validator_set_is_larger", True))
            else minimum_validator_count
        )
        pre = create_genesis_state(
            spec,
            validator_balances=[spec.MAX_EFFECTIVE_BALANCE] * validator_count,
            activation_threshold=spec.MAX_EFFECTIVE_BALANCE,
        )
        flag = spec.ParticipationFlags(1)
        zero = spec.ParticipationFlags(0)
        previous_has_flags = bool(getattr(solution, "previous_has_flags", True))
        current_has_flags = bool(getattr(solution, "current_has_flags", True))
        previous = type(pre.previous_epoch_participation)()
        current = type(pre.current_epoch_participation)()
        for index in range(validator_count):
            previous.append(flag if previous_has_flags and index == 0 else zero)
            current.append(flag if current_has_flags and index == 0 else zero)
        pre.previous_epoch_participation = previous
        pre.current_epoch_participation = current

        post = pre.copy()
        spec.process_participation_flag_updates(post)
        claimed = {
            name: bool(getattr(solution, name))
            for name in (
                "validator_set_is_larger",
                "previous_has_flags",
                "current_has_flags",
            )
            if hasattr(solution, name)
        }
        meta = {
            "description": "process_participation_flag_updates",
            "claimed": claimed,
        }
        return meta, [("pre", "ssz", pre.encode_bytes()), ("post", "ssz", post.encode_bytes())]


MATERIALIZER = ParticipationFlagUpdatesMaterializer
