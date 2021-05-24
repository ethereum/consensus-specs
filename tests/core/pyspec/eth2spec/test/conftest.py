from eth2spec.test import context
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
        import pytest
        return pytest.fixture(*args, **kwargs)
    else:
        def ignore():
            pass
        return ignore


def pytest_addoption(parser):
    parser.addoption(
        "--preset", action="store", type=str, default="minimal",
        help="preset: make the pyspec use the specified preset"
    )
    parser.addoption(
        "--disable-bls", action="store_true", default=False,
        help="bls-default: make tests that are not dependent on BLS run without BLS"
    )
    parser.addoption(
        "--bls-type", action="store", type=str, default="py_ecc", choices=["py_ecc", "milagro"],
        help="bls-type: use 'pyecc' or 'milagro' implementation for BLS"
    )


@fixture(autouse=True)
def preset(request):
    context.DEFAULT_TEST_PRESET = request.config.getoption("--preset")


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
    else:
        raise Exception(f"unrecognized bls type: {bls_type}")
