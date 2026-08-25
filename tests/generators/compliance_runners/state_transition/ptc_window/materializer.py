from __future__ import annotations

from typing import Any

from eth_consensus_specs.test.helpers.genesis import create_genesis_state
from tests.generators.compliance_runners.gen_base.gen_typing import TestCasePart
from tests.generators.compliance_runners.state_transition.materializer import Materializer

_DIMS = [
    "epoch_position",
    "old_sections_distinguishable",
    "tail_epoch_to_current",
    "retained_sections_shifted",
    "new_tail_recomputed",
    "state_effected",
    "outcome",
]


class PtcWindowMaterializer(Materializer):
    runner_name = "epoch_processing"
    handler_name = "ptc_window"

    def materialize_solution(self, sol: Any) -> tuple[dict, list[TestCasePart]]:
        s = self.spec
        pre = create_genesis_state(
            s,
            validator_balances=[s.MAX_EFFECTIVE_BALANCE] * 64,
            activation_threshold=s.MAX_EFFECTIVE_BALANCE,
        )
        target = (1 if str(sol.epoch_position) == "GENESIS_END" else 2) * s.SLOTS_PER_EPOCH - 1
        s.process_slots(pre, s.Slot(target))
        spe = int(s.SLOTS_PER_EPOCH)
        sections = [list(pre.ptc_window[i : i + spe]) for i in range(0, len(pre.ptc_window), spe)]
        assert len({tuple(section) for section in sections}) == len(sections)
        post = pre.copy()
        s.process_ptc_window(post)
        claimed = {
            n: (bool(v) if isinstance(v := getattr(sol, n), bool) else str(v)) for n in _DIMS
        }
        meta = {"description": "process_ptc_window", "claimed": claimed}
        parts = [("pre", "ssz", pre.encode_bytes()), ("post", "ssz", post.encode_bytes())]
        return meta, parts
