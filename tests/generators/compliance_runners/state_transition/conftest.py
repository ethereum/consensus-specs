from __future__ import annotations

from pathlib import Path

import pytest
from tests.generators.compliance_runners.state_transition.catalog import HANDLERS

from tests.generators.compliance_runners.state_transition.run import PROFILES


def pytest_addoption(parser):
    parser.addoption(
        "--comptests-output",
        type=Path,
        default=None,
        help="Output directory for generated compliance tests",
    )
    parser.addoption(
        "--handler",
        choices=(*HANDLERS, "all"),
        default="all",
        help="State-transition handler to generate",
    )
    parser.addoption(
        "--profile",
        choices=PROFILES,
        default="standard",
        help="State-transition coverage profile",
    )


@pytest.fixture
def comptests_output(request) -> Path | None:
    return request.config.getoption("--comptests-output")


def pytest_generate_tests(metafunc):
    if "handler" not in metafunc.fixturenames:
        return

    selected_handler = metafunc.config.getoption("--handler")
    handlers = HANDLERS if selected_handler == "all" else (selected_handler,)
    metafunc.parametrize("handler", handlers, ids=handlers)


@pytest.fixture
def profile(request) -> str:
    return request.config.getoption("--profile")
