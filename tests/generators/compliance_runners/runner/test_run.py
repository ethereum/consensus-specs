"""Pytest entry point for replaying generated vectors."""

import pytest

from . import fork_choice, state_transition
from .discovery import gather_tests, select_tests


def pytest_generate_tests(metafunc):
    if "test_info" not in metafunc.fixturenames:
        return
    roots = metafunc.config.getoption("--test-dir")
    if not roots:
        raise pytest.UsageError("--test-dir is required when replaying compliance vectors")
    cases = select_tests(
        list(gather_tests(roots, kind=metafunc.config.getoption("--kind"))),
        start=metafunc.config.getoption("--start"),
        limit=metafunc.config.getoption("--limit"),
    )
    if not cases:
        raise pytest.UsageError("No matching compliance vectors selected")
    metafunc.parametrize("test_info", cases, ids=[case.id for case in cases])


def test_run_case(test_info):
    replay = state_transition if test_info.kind == "state_transition" else fork_choice
    replay.run_test(test_info)
