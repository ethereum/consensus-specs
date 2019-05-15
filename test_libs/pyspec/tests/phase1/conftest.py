import pytest

from eth2spec.phase1 import spec
from preset_loader import loader

from tests.phase0.helpers import (
    create_genesis_state,
)

from tests.phase0.conftest import (
    pytest_addoption,
    num_validators,
    deposit_data_leaves,
)

# This is redfined so that the constants are re-applied
@pytest.fixture(autouse=True)
def config(request):
    config_name = request.config.getoption("--config")
    presets = loader.load_presets('../../configs/', config_name)
    spec.apply_constants_preset(presets)

#This is redefined so that the BeaconState is the new SSZ Object
@pytest.fixture
def state(num_validators, deposit_data_leaves):
    return create_genesis_state(num_validators, deposit_data_leaves)
