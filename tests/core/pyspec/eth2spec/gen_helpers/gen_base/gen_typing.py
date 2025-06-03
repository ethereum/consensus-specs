from collections.abc import Callable, Iterable
from dataclasses import dataclass
from pathlib import Path
from typing import (
    Any,
    NewType,
)

# Elements: name, out_kind, data
#
# out_kind is the type of data:
#  - "meta" for generic data to collect into a meta data dict
#  - "cfg" for a spec config dictionary
#  - "data" for generic
#  - "ssz" for SSZ encoded bytes
TestCasePart = NewType("TestCasePart", tuple[str, str, Any])


@dataclass
class TestCase:
    fork_name: str
    preset_name: str
    runner_name: str
    handler_name: str
    suite_name: str
    case_name: str
    case_fn: Callable[[], Iterable[TestCasePart]]
    dir: Path | None = None

    def get_identifier(self):
        """Return the human readable identifier."""
        return "::".join(
            [
                self.preset_name,
                self.fork_name,
                self.runner_name,
                self.handler_name,
                self.suite_name,
                self.case_name,
            ]
        )

    def set_output_dir(self, output_dir: str) -> None:
        """Compute and store the output directory on the instance."""
        self.dir = (
            Path(output_dir)
            / self.preset_name
            / self.fork_name
            / self.runner_name
            / self.handler_name
            / self.suite_name
            / self.case_name
        )
