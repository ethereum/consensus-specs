from __future__ import annotations

from typing import Any, TYPE_CHECKING

from eth_consensus_specs.test.helpers.genesis import create_genesis_state
from eth_consensus_specs.test.helpers.gloas.state import initialize_ptc_window
from tests.generators.compliance_runners.state_transition.materializer import Materializer

if TYPE_CHECKING:
    from tests.generators.compliance_runners.gen_base.gen_typing import TestCasePart

_DIMS = [
    "epoch_position",
    "validator_count",
    "validator_balance",
    "validator_activity",
]


class PtcWindowMaterializer(Materializer):
    runner_name = "epoch_processing"
    handler_name = "ptc_window"

    def materialize_solution(self, sol: Any) -> tuple[dict, list[TestCasePart]]:
        s = self.spec
        validator_count = 64 if str(sol.validator_count) == "MINIMUM" else 128
        balance_profile = str(sol.validator_balance)
        if balance_profile == "MINIMUM_BALANCE":
            validator_balances = [s.EFFECTIVE_BALANCE_INCREMENT] * validator_count
            activation_threshold = s.EFFECTIVE_BALANCE_INCREMENT
        elif balance_profile == "MIXED_BALANCE":
            lower_balance = s.MAX_EFFECTIVE_BALANCE - s.EFFECTIVE_BALANCE_INCREMENT
            # Keep balance distribution independent of SOME_INACTIVE's every-
            # fourth-validator selection: each activity group gets both tiers.
            validator_balances = [
                s.MAX_EFFECTIVE_BALANCE if i % 8 < 4 else lower_balance
                for i in range(validator_count)
            ]
            activation_threshold = lower_balance
        else:  # MAXIMUM_BALANCE
            validator_balances = [s.MAX_EFFECTIVE_BALANCE] * validator_count
            activation_threshold = s.MAX_EFFECTIVE_BALANCE
        pre = create_genesis_state(
            s,
            validator_balances=validator_balances,
            activation_threshold=activation_threshold,
        )
        if str(sol.validator_activity) == "SOME_INACTIVE":
            for i in range(0, len(pre.validators), 4):
                validator = pre.validators[i]
                validator.activation_eligibility_epoch = s.FAR_FUTURE_EPOCH
                validator.activation_epoch = s.FAR_FUTURE_EPOCH
            pre.genesis_validators_root = s.hash_tree_root(pre.validators)
            pre.ptc_window = initialize_ptc_window(s, pre)
        target = (1 if str(sol.epoch_position) == "GENESIS_END" else 2) * s.SLOTS_PER_EPOCH - 1
        s.process_slots(pre, s.Slot(target))
        post = pre.copy()
        s.process_ptc_window(post)
        claimed = {
            n: (bool(v) if isinstance(v := getattr(sol, n), bool) else str(v)) for n in _DIMS
        }
        meta = {"description": "process_ptc_window", "claimed": claimed}
        parts = [("pre", "ssz", pre.encode_bytes()), ("post", "ssz", post.encode_bytes())]
        return meta, parts
