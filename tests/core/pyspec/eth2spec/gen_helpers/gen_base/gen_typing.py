from enum import Enum, auto
from typing import (
    Any,
    Callable,
    Iterable,
    NewType,
    Tuple,
)
from dataclasses import dataclass
from pathlib import Path

# Elements: name, out_kind, data
#
# out_kind is the type of data:
#  - "meta" for generic data to collect into a meta data dict
#  - "cfg" for a spec config dictionary
#  - "data" for generic
#  - "ssz" for SSZ encoded bytes
TestCasePart = NewType("TestCasePart", Tuple[str, str, Any])


@dataclass
class TestCase(object):
    fork_name: str
    preset_name: str
    runner_name: str
    handler_name: str
    suite_name: str
    case_name: str
    case_fn: Callable[[], Iterable[TestCasePart]]

    def get_case_dir(self, output_dir: str) -> Path:
        """Return the output directory for this test case."""
        return (
            Path(output_dir)
            / self.preset_name
            / self.fork_name
            / self.runner_name
            / self.handler_name
            / self.suite_name
            / self.case_name
        )


@dataclass
class TestProvider(object):
    # Prepares the context for the provider as a whole, as opposed to per-test-case changes.
    prepare: Callable[[], None]
    # Retrieves an iterable of cases, called after prepare()
    make_cases: Callable[[], Iterable[TestCase]]


@dataclass
class TestCaseParams:
    test_case: TestCase
    case_dir: Path


class Result(Enum):
    COMPLETED = auto()
    SKIPPED = auto()