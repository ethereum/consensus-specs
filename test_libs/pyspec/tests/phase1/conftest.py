import pytest

from eth2spec.phase1 import spec as _spec
from preset_loader import loader

from tests.phase1 import helpers as _helpers

from tests.phase0.conftest import (
    pytest_addoption,
    deposit_data_leaves,
)

# This is redfined so that the constants are re-applied
@pytest.fixture(autouse=True)
def config(request):
    config_name = request.config.getoption("--config")
    presets = loader.load_presets('../../configs/', config_name)
    _spec.apply_constants_preset(presets)

@pytest.fixture
def num_validators(config):
    return _spec.SLOTS_PER_EPOCH * 8

#This is redefined so that the BeaconState is the new SSZ Object
@pytest.fixture
def state(num_validators, deposit_data_leaves):
    return _helpers.create_genesis_state(num_validators, deposit_data_leaves)

@pytest.fixture
def spec():
    return _spec

@pytest.fixture
def helpers():
    return _helpers
