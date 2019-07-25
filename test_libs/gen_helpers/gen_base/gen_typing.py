from typing import (
    Any,
    Callable,
    Iterable,
    Dict,
    Tuple,
)
from collections import namedtuple


@dataclass
class TestCasePart(object):
    name: str  # name of the file
    out_kind: str  # type of data ("data" for generic, "ssz" for SSZ encoded bytes)
    data: Any


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
