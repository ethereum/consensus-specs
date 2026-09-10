"""Shared helpers for materializing state-transition test vectors."""

from __future__ import annotations

import hashlib
import json
import random
import shutil
from enum import Enum
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
    test_provider: str
    rng: random.Random

    def __init__(
        self,
        spec: Any,
        fork_name: str = "gloas",
        preset_name: str = "minimal",
        seed: int = 0,
    ) -> None:
        self.spec = spec
        self.fork_name = fork_name
        self.preset_name = preset_name
        self.seed = seed

    @classmethod
    def _solution_identity(cls, value: Any) -> Any:
        """Return a canonical, JSON-compatible identity for a model solution.

        Solutions are normally ``SimpleNamespace`` instances created from a
        coverage record, but this also supports nested containers used by
        materializers directly. The identity excludes the generated case
        number so reordering representatives cannot change materialization.
        """
        if value is None or isinstance(value, (bool, int, float, str)):
            return value
        if isinstance(value, Enum):
            return value.name
        if isinstance(value, bytes):
            return {"bytes": value.hex()}
        if isinstance(value, dict):
            return {
                str(key): cls._solution_identity(item)
                for key, item in sorted(value.items(), key=lambda pair: str(pair[0]))
            }
        if isinstance(value, (list, tuple)):
            return [cls._solution_identity(item) for item in value]
        if isinstance(value, set):
            return sorted(
                (cls._solution_identity(item) for item in value),
                key=lambda item: json.dumps(item, sort_keys=True, separators=(",", ":")),
            )
        if hasattr(value, "__dict__"):
            return {
                str(key): cls._solution_identity(item)
                for key, item in sorted(vars(value).items())
                if not key.startswith("_")
            }
        raise TypeError(f"Cannot derive a stable identity for solution value: {value!r}")

    def _rng_for_solution(self, solution: Any) -> random.Random:
        """Return an RNG keyed by the semantic model solution.

        The seed deliberately excludes the emitted ``case_####`` name so
        providers may add, remove, or reorder representatives safely.
        """
        solution_identity = json.dumps(
            self._solution_identity(solution), sort_keys=True, separators=(",", ":")
        )
        identity = ":".join(
            (
                str(self.seed),
                self.preset_name,
                self.fork_name,
                self.runner_name,
                self.handler_name,
                self.test_provider,
                solution_identity,
            )
        )
        derived_seed = int.from_bytes(hashlib.sha256(identity.encode()).digest()[:16], "big")
        return random.Random(derived_seed)

    def materialize_solution(self, solution: Any) -> tuple[dict, list[TestCasePart]]:
        raise NotImplementedError("Subclasses must implement this method")

    def write_case(self, dumper: Dumper, output_dir: Path, index: int, solution: Any) -> None:
        case_name = f"case_{index:04d}"
        self.rng = self._rng_for_solution(solution)
        meta, parts = self.materialize_solution(solution)
        claimed = meta.pop("claimed")
        test_case = TestCase(
            fork_name=self.fork_name,
            preset_name=self.preset_name,
            runner_name=self.runner_name,
            handler_name=self.handler_name,
            suite_name=SUITE_NAME,
            case_name=case_name,
        )
        test_case.set_output_dir(str(output_dir))
        result = TestCaseResult(test_case=test_case, meta=meta, case_parts=parts)
        dump_test_case_result(result, dumper)
        dimensions = {
            "case": result.test_case.case_name,
            "test_provider": self.test_provider,
            "claimed": claimed,
        }
        dimensions["seed"] = self.seed
        dumper.dump_data(
            result.test_case.dir,
            "dimensions",
            dimensions,
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
