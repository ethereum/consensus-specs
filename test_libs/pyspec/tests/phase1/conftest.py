import pytest

from eth2spec.phase1 import spec
from preset_loader import loader

from tests.phase1 import helpers as helpers

from tests.phase0.conftest import (
    pytest_addoption,
    deposit_data_leaves,
)

# This is redfined so that the constants are re-applied
@pytest.fixture(autouse=True)
def config(request):
    request.function.__globals__['spec'] = spec
    request.function.__globals__['helpers'] = helpers
    config_name = request.config.getoption("--config")
    presets = loader.load_presets('../../configs/', config_name)
    spec.apply_constants_preset(presets)

@pytest.fixture
def num_validators(config):
    return spec.SLOTS_PER_EPOCH * 8

#This is redefined so that the BeaconState is the new SSZ Object
@pytest.fixture
def state(num_validators, deposit_data_leaves):
    return helpers.create_genesis_state(num_validators, deposit_data_leaves)
