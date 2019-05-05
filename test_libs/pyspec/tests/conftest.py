import pytest

from eth2spec.phase0 import spec
from preset_loader import loader


def pytest_addoption(parser):
    parser.addoption(
        "--config", action="store", default="minimal", help="config: make the pyspec use the specified configuration"
    )


@pytest.fixture(autouse=True)
def config(request):
    config_name = request.config.getoption("--config")
    presets = loader.load_presets('../../configs/', config_name)
    spec.apply_constants_preset(presets)
