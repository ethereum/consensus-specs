from eth2spec.phase0 import spec as spec_phase0
from eth2spec.phase0 import spec as spec_phase1

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
    from preset_loader import loader
    presets = loader.load_presets('../../configs/', config_name)
    spec_phase0.apply_constants_preset(presets)
    spec_phase1.apply_constants_preset(presets)
