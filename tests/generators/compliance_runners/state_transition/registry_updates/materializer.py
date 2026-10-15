"""Materialize ``process_registry_updates`` epoch vectors."""

from __future__ import annotations

from typing import Any, TYPE_CHECKING

from eth_consensus_specs.test.helpers.genesis import create_genesis_state
from tests.generators.compliance_runners.state_transition.materializer import Materializer

from .target import TARGET

if TYPE_CHECKING:
    from tests.generators.compliance_runners.gen_base.gen_typing import TestCasePart


class RegistryUpdatesMaterializer(Materializer):
    runner_name = "epoch_processing"
    handler_name = "registry_updates"

    def materialize_solution(self, solution: Any) -> tuple[dict, list[TestCasePart]]:
        spec = self.spec
        pre = create_genesis_state(
            spec,
            validator_balances=[spec.MAX_EFFECTIVE_BALANCE] * 64,
            activation_threshold=spec.MAX_EFFECTIVE_BALANCE,
        )
        pre.slot = spec.Slot(3 * int(spec.SLOTS_PER_EPOCH) - 1)
        pre.finalized_checkpoint = type(pre.finalized_checkpoint)(
            epoch=spec.GENESIS_EPOCH, root=pre.finalized_checkpoint.root
        )
        requested = {
            name: bool(getattr(solution, name))
            for name in (
                "queues_validator",
                "ejects_validator",
                "activates_validator",
                "leaves_validator_unchanged",
            )
        }
        has_validators = bool(solution.has_validators)
        if has_validators and not requested["leaves_validator_unchanged"]:
            active_branch = next(name for name, value in requested.items() if value)
            for index, validator in enumerate(pre.validators):
                if active_branch == "queues_validator":
                    validator.activation_eligibility_epoch = spec.FAR_FUTURE_EPOCH
                    validator.activation_epoch = spec.FAR_FUTURE_EPOCH
                    validator.exit_epoch = spec.FAR_FUTURE_EPOCH
                elif active_branch == "ejects_validator":
                    validator.activation_epoch = spec.GENESIS_EPOCH
                    validator.exit_epoch = spec.FAR_FUTURE_EPOCH
                    validator.effective_balance = spec.Gwei(spec.config.EJECTION_BALANCE)
                    pre.balances[index] = spec.Gwei(spec.config.EJECTION_BALANCE)
                elif active_branch == "activates_validator":
                    validator.activation_eligibility_epoch = spec.GENESIS_EPOCH
                    validator.activation_epoch = spec.FAR_FUTURE_EPOCH
                    validator.exit_epoch = spec.FAR_FUTURE_EPOCH
        if not has_validators:
            pre.validators = type(pre.validators)()
            pre.balances = type(pre.balances)()
        enabled_branches = [name for name, enabled in requested.items() if enabled]
        validator_indices = self.rng.sample(range(len(pre.validators)), len(enabled_branches))
        for name, index in zip(enabled_branches, validator_indices, strict=True):
            validator = pre.validators[index]
            if name == "queues_validator":
                validator.activation_eligibility_epoch = spec.FAR_FUTURE_EPOCH
                validator.activation_epoch = spec.FAR_FUTURE_EPOCH
            elif name == "ejects_validator":
                validator.activation_epoch = spec.GENESIS_EPOCH
                validator.exit_epoch = spec.FAR_FUTURE_EPOCH
                validator.effective_balance = spec.Gwei(spec.config.EJECTION_BALANCE)
                pre.balances[index] = spec.Gwei(spec.config.EJECTION_BALANCE)
            elif name == "activates_validator":
                validator.activation_eligibility_epoch = spec.GENESIS_EPOCH
                validator.activation_epoch = spec.FAR_FUTURE_EPOCH
                validator.exit_epoch = spec.FAR_FUTURE_EPOCH
            else:
                validator.activation_eligibility_epoch = spec.GENESIS_EPOCH
                validator.activation_epoch = spec.GENESIS_EPOCH
                validator.exit_epoch = spec.FAR_FUTURE_EPOCH
                validator.effective_balance = spec.MAX_EFFECTIVE_BALANCE
        post = pre.copy()
        spec.process_registry_updates(post)
        claimed = self.claimed_record(TARGET, solution)
        return {"description": "process_registry_updates", "claimed": claimed}, [
            ("pre", "ssz", pre.encode_bytes()),
            ("post", "ssz", post.encode_bytes()),
        ]


MATERIALIZER = RegistryUpdatesMaterializer
