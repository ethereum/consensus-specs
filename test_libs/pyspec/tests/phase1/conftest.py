import pytest

from eth2spec.phase1 import spec
from preset_loader import loader

from tests.phase0 import helpers as phase1_helpers
from tests.phase1 import helpers as helpers

from tests.phase0.conftest import (
    deposit_data_leaves,
)


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
    phase1_helpers.spec = spec
    request.function.__globals__['spec'] = spec
    request.function.__globals__['helpers'] = helpers


@pytest.fixture
def num_validators(config):
    return spec.SLOTS_PER_EPOCH * 8


@pytest.fixture
def state(num_validators, deposit_data_leaves):  # noqa: F811
    return helpers.create_genesis_state(num_validators, deposit_data_leaves)
