import pytest

from eth2spec.phase0 import spec as _spec
from preset_loader import loader

from tests.phase0 import helpers as _helpers


def pytest_addoption(parser):
    parser.addoption(
        "--config", action="store", default="minimal", help="config: make the pyspec use the specified configuration"
    )

@pytest.fixture(autouse=True)
def config(request):
    config_name = request.config.getoption("--config")
    presets = loader.load_presets('../../configs/', config_name)
    _spec.apply_constants_preset(presets)

@pytest.fixture
def num_validators(config):
    return _spec.SLOTS_PER_EPOCH * 8

@pytest.fixture
def deposit_data_leaves():
    return list()

@pytest.fixture
def state(num_validators, deposit_data_leaves):
    return _helpers.create_genesis_state(num_validators, deposit_data_leaves)

@pytest.fixture
def spec():
    return _spec

@pytest.fixture
def helpers():
    return _helpers

