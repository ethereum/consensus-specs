"""Shared helpers for materializing state-transition test vectors."""

from __future__ import annotations

import shutil
from typing import Any, TYPE_CHECKING

from eth_consensus_specs.test.utils.dumper import Dumper
from tests.generators.compliance_runners.gen_base.gen_typing import (
    TestCase,
    TestCasePart,
    TestCaseResult,
)
from tests.generators.compliance_runners.gen_base.output import dump_test_case_result

if TYPE_CHECKING:
    from pathlib import Path


SUITE_NAME = "main"


class Materializer:
    spec: Any
    fork_name: str
    preset_name: str
    runner_name: str
    handler_name: str

    def __init__(
        self,
        spec: Any,
        fork_name: str = "gloas",
        preset_name: str = "minimal",
    ) -> None:
        self.spec = spec
        self.fork_name = fork_name
        self.preset_name = preset_name

    def materialize_solution(self, solution: Any) -> tuple[dict, list[TestCasePart]]:
        raise NotImplementedError("Subclasses must implement this method")

    def write_case(self, dumper: Dumper, output_dir: Path, index: int, solution: Any) -> None:
        meta, parts = self.materialize_solution(solution)
        claimed = meta.pop("claimed")
        test_case = TestCase(
            fork_name=self.fork_name,
            preset_name=self.preset_name,
            runner_name=self.runner_name,
            handler_name=self.handler_name,
            suite_name=SUITE_NAME,
            case_name=f"case_{index:04d}",
        )
        test_case.set_output_dir(str(output_dir))
        result = TestCaseResult(test_case=test_case, meta=meta, case_parts=parts)
        dump_test_case_result(result, dumper)
        dumper.dump_data(
            result.test_case.dir,
            "dimensions",
            {"case": result.test_case.case_name, "claimed": claimed},
        )

    def materialize_reps(
        self,
        output_dir: Path,
        representatives: list[Any],
        *,
        case_offset: int = 0,
        clean: bool = True,
    ) -> int:
        """Write representatives into a reference-test directory."""
        suite_dir = (
            output_dir
            / self.preset_name
            / self.fork_name
            / self.runner_name
            / self.handler_name
            / SUITE_NAME
        )
        if clean and suite_dir.exists():
            shutil.rmtree(suite_dir)
        dumper = Dumper()
        for index, solution in enumerate(representatives):
            self.write_case(dumper, output_dir, case_offset + index, solution)
        print(f"Generated {len(representatives)} test cases in {output_dir}")
        return len(representatives)
