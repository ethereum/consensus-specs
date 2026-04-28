import pytest

from eth_consensus_specs.utils import bls


def pytest_addoption(parser):
    parser.addoption(
        "--test-dir",
        action="store",
        default=None,
        help="Directory containing generated compliance tests to validate.",
    )
    parser.addoption(
        "--start",
        type=int,
        default=None,
        help="Start index (0-based) into the generated test list.",
    )
    parser.addoption(
        "--limit",
        type=int,
        default=None,
        help="Limit number of generated tests to validate.",
    )


@pytest.fixture(scope="session", autouse=True)
def _disable_bls():
    bls.bls_active = False
