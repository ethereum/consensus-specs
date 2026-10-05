"""Materialize Gloas ``process_effective_balance_updates`` epoch vectors."""

from __future__ import annotations

from typing import Any, TYPE_CHECKING

from eth_consensus_specs.test.helpers.genesis import create_genesis_state
from tests.generators.compliance_runners.state_transition.materializer import Materializer

if TYPE_CHECKING:
    from tests.generators.compliance_runners.gen_base.gen_typing import TestCasePart


_DIMS = (
    "credential_type",
    "downward_trigger",
    "upward_trigger",
    "rounded_vs_cap",
    "balance_aligned",
    "outcome",
)
_GENESIS_VALIDATOR_COUNT = 64


class EffectiveBalanceUpdatesBodyMaterializer(Materializer):
    runner_name = "epoch_processing"
    handler_name = "effective_balance_updates"

    def _base_state(self) -> Any:
        state = create_genesis_state(
            self.spec,
            validator_balances=[self.spec.MAX_EFFECTIVE_BALANCE] * _GENESIS_VALIDATOR_COUNT,
            activation_threshold=self.spec.MAX_EFFECTIVE_BALANCE,
        )
        # Genesis construction needs a larger active set for the Gloas PTC
        # window. The processor under test reads only these lists, so retain a
        # single validator to isolate the loop-body behaviour.
        source_index = self.rng.randrange(len(state.validators))
        validator = state.validators[source_index]
        balance = state.balances[source_index]
        state.validators = type(state.validators)()
        state.validators.append(validator)
        state.balances = type(state.balances)()
        state.balances.append(balance)

        for index in range(len(state.randao_mixes)):
            state.randao_mixes[index] = self.spec.Bytes32(
                self.rng.getrandbits(256).to_bytes(32, "big")
            )
        for index in range(len(state.state_roots)):
            state.state_roots[index] = self.spec.Bytes32(
                self.rng.getrandbits(256).to_bytes(32, "big")
            )
            state.block_roots[index] = self.spec.Bytes32(
                self.rng.getrandbits(256).to_bytes(32, "big")
            )
        for index in range(len(state.slashings)):
            state.slashings[index] = self.spec.Gwei(self.rng.getrandbits(64))
        return state

    def materialize_solution(self, solution: Any) -> tuple[dict, list[TestCasePart]]:
        spec = self.spec
        pre = self._base_state()
        validator = pre.validators[0]
        effective_balance = int(solution.effective_balance)
        balance = int(solution.balance)
        prefix = (
            spec.COMPOUNDING_WITHDRAWAL_PREFIX
            if solution.credential_type == "COMPOUNDING"
            else self.rng.choice((spec.BLS_WITHDRAWAL_PREFIX, spec.ETH1_ADDRESS_WITHDRAWAL_PREFIX))
        )
        credential_tail = self.rng.getrandbits(31 * 8).to_bytes(31, "big")
        validator.withdrawal_credentials = spec.Bytes32(prefix + credential_tail)

        validator.effective_balance = spec.Gwei(effective_balance)
        pre.balances[0] = spec.Gwei(balance)
        post = pre.copy()
        spec.process_effective_balance_updates(post)

        claimed = {name: getattr(solution, name) for name in _DIMS}
        meta = {
            "description": f"process_effective_balance_updates: {claimed['outcome']}",
            "claimed": claimed,
        }
        return meta, [("pre", "ssz", pre.encode_bytes()), ("post", "ssz", post.encode_bytes())]
