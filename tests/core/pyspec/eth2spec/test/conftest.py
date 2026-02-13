import sys

import pytest

from eth2spec.test import context
from eth2spec.test.helpers.constants import ALL_PHASES, ALLOWED_TEST_RUNNER_FORKS
from eth2spec.utils import bls as bls_utils

# We import pytest only when it's present, i.e. when we are running tests.
# The test-cases themselves can be generated without installing pytest.


def module_exists(module_name):
    try:
        __import__(module_name)
    except ImportError:
        return False
    else:
        return True


def fixture(*args, **kwargs):
    if module_exists("pytest"):
        return pytest.fixture(*args, **kwargs)
    else:

        def ignore():
            pass

        return ignore


def pytest_addoption(parser):
    parser.addoption(
        "--preset",
        action="store",
        type=str,
        default="minimal",
        help="preset: make the pyspec use the specified preset",
    )
    parser.addoption(
        "--fork",
        action="append",
        type=str,
        help=(
            "fork: make the pyspec only run with the specified phase."
            " To run multiple phases, e.g., --fork=phase0 --fork=altair"
        ),
    )
    parser.addoption(
        "--disable-bls",
        action="store_true",
        default=False,
        help="bls-default: make tests that are not dependent on BLS run without BLS",
    )
    parser.addoption(
        "--bls-type",
        action="store",
        type=str,
        default="fastest",
        choices=["py_ecc", "milagro", "arkworks", "fastest"],
        help=(
            "bls-type: use specified BLS implementation;"
            "fastest: use milagro for signatures and arkworks for everything else (e.g. KZG)"
        ),
    )


def _validate_fork_name(forks):
    for fork in forks:
        if fork not in set(ALLOWED_TEST_RUNNER_FORKS):
            raise ValueError(
                f'The given --fork argument "{fork}" is not an available fork.'
                f" The available forks: {ALLOWED_TEST_RUNNER_FORKS}"
            )


@fixture(autouse=True)
def preset(request):
    preset_value = request.config.getoption("--preset")
    context.DEFAULT_TEST_PRESET = preset_value
    # The eth2spec package is built inside tests/core/pyspec/, causing it to be
    # imported under two paths: "eth2spec.test.context" and
    # "tests.core.pyspec.eth2spec.test.context". Python treats these as separate
    # modules with independent module-level variables.
    alt_context = sys.modules.get("tests.core.pyspec.eth2spec.test.context")
    if alt_context is not None:
        alt_context.DEFAULT_TEST_PRESET = preset_value


@fixture(autouse=True)
def run_phases(request):
    forks = request.config.getoption("--fork", default=None)
    if forks:
        forks = [fork.lower() for fork in forks]
        _validate_fork_name(forks)
        context.DEFAULT_PYTEST_FORKS = set(forks)
    else:
        context.DEFAULT_PYTEST_FORKS = ALL_PHASES


@fixture(autouse=True)
def bls_default(request):
    disable_bls = request.config.getoption("--disable-bls")
    if disable_bls:
        context.DEFAULT_BLS_ACTIVE = False


@fixture(autouse=True)
def bls_type(request):
    bls_type = request.config.getoption("--bls-type")
    if bls_type == "py_ecc":
        bls_utils.use_py_ecc()
    elif bls_type == "milagro":
        bls_utils.use_milagro()
    elif bls_type == "arkworks":
        bls_utils.use_arkworks()
    elif bls_type == "fastest":
        bls_utils.use_fastest()
    else:
        raise Exception(f"unrecognized bls type: {bls_type}")


pytest_plugins = ["tests.infra.pytest_plugins.yield_generator"]
