from __future__ import annotations

from os import path

import pytest

from eth_consensus_specs.test import context
from eth_consensus_specs.test.helpers.constants import ELECTRA, MINIMAL

# The compliance generator relies on generator-mode decorators being resolved at
# import time, so set the context before importing the generator module.
context.is_pytest = False
context.is_generator = True

from .instantiators.test_case import enumerate_test_groups, prepare_bls  # noqa: E402

DEFAULT_FORKS = [ELECTRA]
DEFAULT_PRESETS = [MINIMAL]


def pytest_addoption(parser):
    parser.addoption(
        "--comptests-output",
        action="store",
        default="comptests",
        help="Output directory for generated compliance tests",
    )
    parser.addoption(
        "--forks",
        action="append",
        default=[],
        help="Forks to generate compliance tests for. Can be repeated.",
    )
    parser.addoption(
        "--presets",
        action="append",
        default=[],
        help="Presets to generate compliance tests for. Can be repeated.",
    )
    parser.addoption(
        "--fc-gen-debug",
        dest="fc_gen_debug",
        action="store_true",
        default=False,
        help="Enable debug output and extra checks for generated chains",
    )
    parser.addoption(
        "--fc-gen-config",
        dest="fc_gen_config",
        type=str,
        required=False,
        choices=["tiny", "small", "standard"],
        help="Name of test generator configuration: tiny, small or standard",
    )
    parser.addoption(
        "--fc-gen-config-path",
        dest="fc_gen_config_path",
        type=str,
        required=False,
        help="Path to a file with test generator configurations",
    )
    parser.addoption(
        "--fc-gen-seed",
        dest="fc_gen_seed",
        type=int,
        default=None,
        required=False,
        help="Override test seeds (fuzzing mode)",
    )
    parser.addoption(
        "--group-slice-index",
        dest="group_slice_index",
        type=int,
        default=None,
        required=False,
        help="0-based shard index when slicing selected test groups deterministically",
    )
    parser.addoption(
        "--group-slice-count",
        dest="group_slice_count",
        type=int,
        default=None,
        required=False,
        help="Number of deterministic test-group slices to split across",
    )


def _get_config_path(config) -> str:
    config_path = config.getoption("--fc-gen-config-path")
    if config_path is not None:
        return config_path

    config_name = config.getoption("--fc-gen-config")
    if config_name is not None:
        return path.join(path.dirname(__file__), config_name, "test_gen.yaml")

    raise ValueError("Neither fc-gen-config nor fc-gen-config-path specified")


def _validate_group_slice_args(config) -> tuple[int | None, int | None]:
    slice_index = config.getoption("--group-slice-index")
    slice_count = config.getoption("--group-slice-count")

    if slice_index is None and slice_count is None:
        return None, None
    if slice_index is None or slice_count is None:
        raise pytest.UsageError(
            "Both --group-slice-index and --group-slice-count must be specified"
        )
    if slice_count <= 0:
        raise pytest.UsageError("--group-slice-count must be a positive integer")
    if slice_index < 0 or slice_index >= slice_count:
        raise pytest.UsageError("--group-slice-index must be in [0, --group-slice-count)")

    return slice_index, slice_count


def pytest_generate_tests(metafunc):
    if "test_group" not in metafunc.fixturenames:
        return

    forks = metafunc.config.getoption("--forks") or DEFAULT_FORKS
    presets = metafunc.config.getoption("--presets") or DEFAULT_PRESETS
    config_path = _get_config_path(metafunc.config)
    debug = metafunc.config.getoption("--fc-gen-debug")
    seed = metafunc.config.getoption("--fc-gen-seed")
    slice_index, slice_count = _validate_group_slice_args(metafunc.config)

    test_groups = list(enumerate_test_groups(config_path, forks, presets, debug, seed))
    if slice_count is not None:
        test_groups = [
            test_group
            for group_index, test_group in enumerate(test_groups)
            if group_index % slice_count == slice_index
        ]
    metafunc.parametrize(
        "test_group",
        test_groups,
        ids=[test_group.get_identifier() for test_group in test_groups],
    )


@pytest.fixture(scope="session", autouse=True)
def _prepare_bls():
    prepare_bls()


@pytest.fixture
def comptests_output_dir(request) -> str:
    return request.config.getoption("--comptests-output")
