from __future__ import annotations

import shutil
from typing import Any, TYPE_CHECKING

from eth_consensus_specs.test.helpers.genesis import create_genesis_state
from eth_consensus_specs.test.utils.dumper import Dumper
from tests.generators.compliance_runners.gen_base.gen_typing import TestCase, TestCaseResult
from tests.generators.compliance_runners.gen_base.output import dump_test_case_result

if TYPE_CHECKING:
    from pathlib import Path

_DIMS = [
    "epoch_position",
    "old_sections_distinguishable",
    "tail_epoch_to_current",
    "retained_sections_shifted",
    "new_tail_recomputed",
    "state_effected",
    "outcome",
]


class PtcWindowMaterializer:
    def __init__(self, spec: Any):
        self.spec = spec

    def materialize_solution(self, sol: Any):
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
        return pre, post, claimed

    def materialize_reps(self, output_dir: Path, reps: list[Any]):
        if output_dir.exists():
            shutil.rmtree(output_dir)
        output_dir.mkdir(parents=True)
        dumper = Dumper()
        for i, sol in enumerate(reps):
            pre, post, claimed = self.materialize_solution(sol)
            case = f"case_{i:04d}"
            tc = TestCase(
                fork_name="gloas",
                preset_name="minimal",
                runner_name="epoch_processing",
                handler_name="ptc_window",
                suite_name="main",
                case_name=case,
            )
            tc.set_output_dir(str(output_dir))
            dump_test_case_result(
                TestCaseResult(
                    test_case=tc,
                    meta={"description": "process_ptc_window"},
                    case_parts=[
                        ("pre", "ssz", pre.encode_bytes()),
                        ("post", "ssz", post.encode_bytes()),
                    ],
                ),
                dumper,
            )
            dumper.dump_data(tc.dir, "dimensions", {"case": case, "claimed": claimed})
        return len(reps)
