from pathlib import Path
from typing import (
    Any,
    Callable,
    Dict,
    Iterable,
    List,
    NewType,
    Tuple,
    Union,
)
from dataclasses import dataclass

# Elements: name, out_kind, data
#
# out_kind is the type of data:
#  - "data" for generic
#  - "ssz" for SSZ encoded bytes
#  - "meta" for generic data to collect into a meta data dict.
#  - "root" for SSZ hash tree root
TestCasePart = NewType("TestCasePart", Tuple[str, str, Any, bytes])


# A map to trace the overlapping SSZ object output
# key: str -> (file_path: Path, count: int)
SSZLookup = NewType("SSZLookup", Dict[str, List[Union[Path, int]]])


@dataclass
class TestCase(object):
    fork_name: str
    runner_name: str
    handler_name: str
    suite_name: str
    case_name: str
    case_fn: Callable[[], Iterable[TestCasePart]]


@dataclass
class TestProvider(object):
    # Prepares the context with a configuration, loaded from the given config path.
    # fn(config path) => chosen config name
    prepare: Callable[[str], str]
    # Retrieves an iterable of cases, called after prepare()
    make_cases: Callable[[], Iterable[TestCase]]
