import sys

import pytest

from eth_consensus_specs.test import context
from eth_consensus_specs.test.helpers.constants import ALL_PHASES, ALLOWED_TEST_RUNNER_FORKS
from eth_consensus_specs.utils.kzg import load_trusted_setup


def pytest_addoption(parser):
    parser.addoption(
        "--preset",
        action="append",
        type=str,
        default=None,
        help="preset: make the pyspec use the specified preset. Can be repeated, e.g., --preset=minimal --preset=mainnet",
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
        "--coverage",
        action="store_true",
        default=False,
        help="coverage: enable code coverage tracking",
    )


def _validate_fork_name(forks):
    for fork in forks:
        if fork not in set(ALLOWED_TEST_RUNNER_FORKS):
            raise ValueError(
                f'The given --fork argument "{fork}" is not an available fork.'
                f" The available forks: {ALLOWED_TEST_RUNNER_FORKS}"
            )


def pytest_generate_tests(metafunc):
    if "preset" in metafunc.fixturenames:
        presets = metafunc.config.getoption("--preset")
        if presets is None:
            if metafunc.config.getoption("--reftests", default=False):
                presets = ["minimal", "mainnet", "general"]
            else:
                presets = ["minimal"]
        metafunc.parametrize("preset", presets, indirect=True)


@pytest.fixture(autouse=True)
def preset(request):
    preset_value = request.param
    manifest_preset = getattr(getattr(request.function, "manifest", None), "preset_name", None)

    if preset_value == "general" and manifest_preset != "general":
        pytest.skip("not a general test")

    if preset_value != "general" and manifest_preset == "general":
        pytest.skip("general-only test")

    # "general" tests are preset-independent; use "minimal" for spec loading
    # while keeping the callspec as "general" for correct output paths.
    spec_preset = "minimal" if preset_value == "general" else preset_value
    context.DEFAULT_TEST_PRESET = spec_preset
    # The eth2spec package is built inside tests/core/pyspec/, causing it to be
    # imported under two paths: "eth2spec.test.context" and
    # "tests.core.pyspec.eth2spec.test.context". Python treats these as separate
    # modules with independent module-level variables.
    alt_context = sys.modules.get("tests.core.pyspec.eth_consensus_specs.test.context")
    if alt_context is not None:
        alt_context.DEFAULT_TEST_PRESET = spec_preset


@pytest.fixture(autouse=True)
def run_phases(request):
    forks = request.config.getoption("--fork", default=None)
    if forks:
        forks = [fork.lower() for fork in forks]
        _validate_fork_name(forks)
        context.DEFAULT_PYTEST_FORKS = set(forks)
    elif not context.is_generator:
        context.DEFAULT_PYTEST_FORKS = ALL_PHASES


@pytest.fixture(scope="session", autouse=True)
def trusted_setup():
    load_trusted_setup()


pytest_plugins = ["eth_consensus_specs.test.pytest_plugins.yield_generator"]
