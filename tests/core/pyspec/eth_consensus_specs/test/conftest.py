import os
import sys

import pytest

from eth_consensus_specs.test import context
from eth_consensus_specs.test.helpers.constants import ALL_PHASES, ALLOWED_TEST_RUNNER_FORKS
from eth_consensus_specs.test.helpers.specs import spec_targets
from eth_consensus_specs.utils import bls as bls_utils
from eth_consensus_specs.utils.ckzg_utils import apply_ckzg_to_spec, load_trusted_setup

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
        "--kzg-type",
        action="store",
        type=str,
        default="ckzg",
        choices=["spec", "ckzg"],
        help="kzg-type: use specified KZG implementation (default: ckzg)",
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
    # The eth_consensus_specs package is built inside tests/core/pyspec/, causing it to be
    # imported under two paths: "eth_consensus_specs.test.context" and
    # "tests.core.pyspec.eth_consensus_specs.test.context". Python treats these as separate
    # modules with independent module-level variables.
    alt_context = sys.modules.get("tests.core.pyspec.eth_consensus_specs.test.context")
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


def _apply_ckzg():
    """
    Patch all spec modules to use ckzg for KZG functions.
    """
    repo_root = os.path.join(os.path.dirname(__file__), "..", "..", "..", "..", "..")
    ts_path = os.path.join(
        repo_root, "presets", "mainnet", "trusted_setups", "trusted_setup_4096.json"
    )
    ts = load_trusted_setup(ts_path)

    for preset_specs in spec_targets.values():
        for spec in preset_specs.values():
            apply_ckzg_to_spec(spec, ts)


@pytest.fixture(scope="session", autouse=True)
def kzg_type(request):
    kzg_type = request.config.getoption("--kzg-type")
    if kzg_type == "ckzg":
        _apply_ckzg()
