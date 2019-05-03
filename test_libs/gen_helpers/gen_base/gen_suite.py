from typing import Iterable

from eth_utils import to_dict
from gen_base.gen_typing import TestCase


@to_dict
def render_suite(*,
                 title: str, summary: str,
                 forks_timeline: str, forks: Iterable[str],
                 config: str,
                 runner: str,
                 handler: str,
                 test_cases: Iterable[TestCase]):
    yield "title", title
    yield "summary", summary
    yield "forks_timeline", forks_timeline,
    yield "forks", forks
    yield "config", config
    yield "runner", runner
    yield "handler", handler
    yield "test_cases", test_cases
