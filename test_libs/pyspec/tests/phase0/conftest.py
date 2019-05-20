import pytest

from eth2spec.phase0 import spec
from preset_loader import loader

from tests.phase0 import helpers
from tests.phase0 import test_finality

def pytest_addoption(parser):
    parser.addoption(
        "--config", action="store", default="minimal", help="config: make the pyspec use the specified configuration"
    )

@pytest.fixture(autouse=True)
def config(request):
    config_name = request.config.getoption("--config")
    presets = loader.load_presets('../../configs/', config_name)
    spec.apply_constants_preset(presets)
    helpers.spec = spec
    request.function.__globals__['spec'] = spec
    request.function.__globals__['helpers'] = helpers

@pytest.fixture
def num_validators(config):
    return spec.SLOTS_PER_EPOCH * 8

@pytest.fixture
def deposit_data_leaves():
    return list()

@pytest.fixture
def state(num_validators, deposit_data_leaves):
    return helpers.create_genesis_state(num_validators, deposit_data_leaves)
