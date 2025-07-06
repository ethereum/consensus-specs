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
    parser.addoption(
        "--disable-spec-cache",
        action="store_true",
        default=False,
        help="disable-spec-cache: disable the spec cache",
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
    context.DEFAULT_TEST_PRESET = request.config.getoption("--preset")


@fixture(autouse=True)
def spec_cache(request):
    disable_spec_cache = request.config.getoption("--disable-spec-cache")
    if disable_spec_cache:
        spec_cache.DISABLED_CACHE = True
    else:
        spec_cache.DISABLED_CACHE = False


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
