import pytest

from build.phase0 import spec

from tests.phase0.helpers import (
    create_genesis_state,
)


DEFAULT_CONFIG = {}  # no change

MINIMAL_CONFIG = {
    "SHARD_COUNT": 8,
    "MIN_ATTESTATION_INCLUSION_DELAY": 2,
    "TARGET_COMMITTEE_SIZE": 4,
    "SLOTS_PER_EPOCH": 8,
    "SLOTS_PER_HISTORICAL_ROOT": 64,
    "LATEST_RANDAO_MIXES_LENGTH": 64,
    "LATEST_ACTIVE_INDEX_ROOTS_LENGTH": 64,
    "LATEST_SLASHED_EXIT_LENGTH": 64,
}


def overwrite_spec_config(config):
    for field in config:
        setattr(spec, field, config[field])
        if field == "LATEST_RANDAO_MIXES_LENGTH":
            spec.BeaconState.fields['latest_randao_mixes'][1] = config[field]
        elif field == "SHARD_COUNT":
            spec.BeaconState.fields['latest_crosslinks'][1] = config[field]
        elif field == "SLOTS_PER_HISTORICAL_ROOT":
            spec.BeaconState.fields['latest_block_roots'][1] = config[field]
            spec.BeaconState.fields['latest_state_roots'][1] = config[field]
            spec.HistoricalBatch.fields['block_roots'][1] = config[field]
            spec.HistoricalBatch.fields['state_roots'][1] = config[field]
        elif field == "LATEST_ACTIVE_INDEX_ROOTS_LENGTH":
            spec.BeaconState.fields['latest_active_index_roots'][1] = config[field]
        elif field == "LATEST_SLASHED_EXIT_LENGTH":
            spec.BeaconState.fields['latest_slashed_balances'][1] = config[field]


@pytest.fixture(
    params=[
        pytest.param(MINIMAL_CONFIG, marks=pytest.mark.minimal_config),
        DEFAULT_CONFIG,
    ]
)
def config(request):
    return request.param


@pytest.fixture(autouse=True)
def overwrite_config(config):
    overwrite_spec_config(config)


@pytest.fixture
def num_validators():
    return 100


@pytest.fixture
def deposit_data_leaves():
    return list()


@pytest.fixture
def state(num_validators, deposit_data_leaves):
    return create_genesis_state(num_validators, deposit_data_leaves)
