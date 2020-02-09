from eth2spec.config import config_util
from eth2spec.test.context import reload_specs


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
        "--config", action="store", default="minimal", help="config: make the pyspec use the specified configuration"
    )


@fixture(autouse=True)
def config(request):
    config_name = request.config.getoption("--config")
    config_util.prepare_config('../../../configs/', config_name)
    # now that the presets are loaded, reload the specs to apply them
    reload_specs()
