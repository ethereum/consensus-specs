from __future__ import annotations

from os import path

import pytest

from eth_consensus_specs.test.helpers.constants import ELECTRA, MINIMAL
from tests.generators.compliance_runners.gen_base.pytest_support import (
    add_comptests_pytest_options,
    configure_generator_context,
    get_comptests_output_dir,
    parametrize_test_groups,
)

# The compliance generator relies on generator-mode decorators being resolved at
# import time, so set the context before importing the generator module.
configure_generator_context()

from .instantiators.test_case import enumerate_test_groups, prepare_bls  # noqa: E402

DEFAULT_FORKS = [ELECTRA]
DEFAULT_PRESETS = [MINIMAL]


def pytest_addoption(parser):
    add_comptests_pytest_options(parser)


def pytest_generate_tests(metafunc):
    parametrize_test_groups(
        metafunc,
        default_forks=DEFAULT_FORKS,
        default_presets=DEFAULT_PRESETS,
        enumerate_groups=enumerate_test_groups,
        base_dir=path.dirname(__file__),
    )


@pytest.fixture(scope="session", autouse=True)
def _prepare_bls():
    prepare_bls()


@pytest.fixture
def comptests_output_dir(request) -> str:
    return get_comptests_output_dir(request)
