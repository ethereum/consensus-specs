from __future__ import annotations

from typing import Any

from eth_consensus_specs.test.helpers.genesis import create_genesis_state
from tests.generators.compliance_runners.gen_base.gen_typing import TestCasePart
from tests.generators.compliance_runners.state_transition.materializer import Materializer

_DIMS = [
    "epoch_position",
    "validator_count",
]


class PtcWindowMaterializer(Materializer):
    runner_name = "epoch_processing"
    handler_name = "ptc_window"

    def materialize_solution(self, sol: Any) -> tuple[dict, list[TestCasePart]]:
        s = self.spec
        validator_count = 64 if str(sol.validator_count) == "MINIMUM" else 128
        pre = create_genesis_state(
            s,
            validator_balances=[s.MAX_EFFECTIVE_BALANCE] * validator_count,
            activation_threshold=s.MAX_EFFECTIVE_BALANCE,
        )
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
