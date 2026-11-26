"""Materialize Gloas ``process_effective_balance_updates`` epoch vectors."""

from __future__ import annotations

from typing import Any, TYPE_CHECKING

from eth_consensus_specs.test.helpers.epoch_processing import run_epoch_processing_to
from eth_consensus_specs.test.helpers.genesis import create_genesis_state
from tests.generators.compliance_runners.state_transition.materializer import Materializer

from .cases import constants, representatives
from .target import COMPARISONS, TARGET

if TYPE_CHECKING:
    from tests.generators.compliance_runners.gen_base.gen_typing import TestCasePart


_BACKGROUND_VALIDATOR_COUNT = 64


class EffectiveBalanceUpdatesBodyMaterializer(Materializer):
    runner_name = "epoch_processing"
    handler_name = "effective_balance_updates"

    def materialize_solution(self, solution: Any) -> tuple[dict, list[TestCasePart]]:
        spec = self.spec
        key = tuple(sorted((f.name, getattr(solution, f.name)) for f in TARGET.factors))
        _, effective_balance, balance = representatives(constants(spec), COMPARISONS)[key]
        # The observer samples index zero. Keep the other validators and their committees intact.
        pre = create_genesis_state(
            spec,
            validator_balances=[effective_balance]
            + [spec.MAX_EFFECTIVE_BALANCE] * _BACKGROUND_VALIDATOR_COUNT,
            activation_threshold=spec.MIN_ACTIVATION_BALANCE,
        )
        validator = pre.validators[0]
        prefix = (
            spec.COMPOUNDING_WITHDRAWAL_PREFIX
            if solution.credential_type == "COMPOUNDING"
            else self.rng.choice((spec.BLS_WITHDRAWAL_PREFIX, spec.ETH1_ADDRESS_WITHDRAWAL_PREFIX))
        )
        if prefix != spec.BLS_WITHDRAWAL_PREFIX:
            address = self.rng.getrandbits(160).to_bytes(20, "big")
            validator.withdrawal_credentials = spec.Bytes32(prefix + bytes(11) + address)
        pre.genesis_validators_root = spec.hash_tree_root(pre.validators)
        spec.process_slots(pre, spec.Slot(spec.SLOTS_PER_EPOCH - 1))
        pre.balances[0] = spec.Gwei(balance)
        run_epoch_processing_to(spec, pre, "process_effective_balance_updates")
        post = pre.copy()
        spec.process_effective_balance_updates(post)

        claimed = self.claimed_record(TARGET, solution)
        meta = {
            "description": f"process_effective_balance_updates: {claimed['outcome']}",
            "claimed": claimed,
        }
        return meta, [("pre", "ssz", pre.encode_bytes()), ("post", "ssz", post.encode_bytes())]


MATERIALIZER = EffectiveBalanceUpdatesBodyMaterializer
