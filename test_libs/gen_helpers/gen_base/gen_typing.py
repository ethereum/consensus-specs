from typing import (
    Any,
    Callable,
    Iterable,
    NewType,
    Tuple,
)
from dataclasses import dataclass

# Elements: name, out_kind, data
#
# out_kind is the type of data:
#  - "data" for generic
#  - "ssz" for SSZ encoded bytes
#  - "meta" for generic data to collect into a meta data dict.
TestCasePart = NewType("TestCasePart", Tuple[str, str, Any])


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
