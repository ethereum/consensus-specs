from eth2spec.test.context import (
    single_phase,
    spec_test,
    with_presets,
    with_fulu_and_later,
)
from eth2spec.test.context import spec_state_test
from eth2spec.test.helpers.constants import (
    MAINNET,
)


@with_fulu_and_later
@spec_test
@single_phase
def test_invariants(spec):
    assert spec.FIELD_ELEMENTS_PER_BLOB % spec.FIELD_ELEMENTS_PER_CELL == 0
    assert spec.FIELD_ELEMENTS_PER_EXT_BLOB % spec.config.NUMBER_OF_COLUMNS == 0
    assert spec.config.SAMPLES_PER_SLOT <= spec.config.NUMBER_OF_COLUMNS
    assert spec.config.CUSTODY_REQUIREMENT <= spec.config.DATA_COLUMN_SIDECAR_SUBNET_COUNT
    assert spec.config.DATA_COLUMN_SIDECAR_SUBNET_COUNT <= spec.config.NUMBER_OF_COLUMNS
    assert spec.config.NUMBER_OF_COLUMNS % spec.config.DATA_COLUMN_SIDECAR_SUBNET_COUNT == 0
    assert spec.config.MAX_REQUEST_DATA_COLUMN_SIDECARS == (
        spec.config.MAX_REQUEST_BLOCKS_DENEB * spec.config.NUMBER_OF_COLUMNS
    )


@with_fulu_and_later
@spec_test
@single_phase
def test_polynomial_commitments_sampling(spec):
    assert spec.FIELD_ELEMENTS_PER_EXT_BLOB == 2 * spec.FIELD_ELEMENTS_PER_BLOB


@with_fulu_and_later
@spec_test
@single_phase
def test_networking(spec):
    assert spec.get_max_blobs_per_block(364032 + 1) <= spec.MAX_BLOB_COMMITMENTS_PER_BLOCK


@with_fulu_and_later
@spec_state_test
@with_presets([MAINNET], reason="to have fork epoch number")
def test_get_max_blobs(spec, state):
    # Check that before Deneb fork there is no blob count
    try:
        spec.get_max_blobs_per_block(spec.config.DENEB_FORK_EPOCH - 1)
    except AssertionError:
        pass
    # Check that after Deneb fork, blob count is equal to MAX_BLOBS_PER_BLOCK (6)
    assert spec.config.MAX_BLOBS_PER_BLOCK == spec.get_max_blobs_per_block(
        spec.config.DENEB_FORK_EPOCH
    )
    # Check that until Electra fork, blob count is still MAX_BLOBS_PER_BLOCK (6)
    assert spec.config.MAX_BLOBS_PER_BLOCK == spec.get_max_blobs_per_block(
        spec.config.ELECTRA_FORK_EPOCH - 1
    )
    # Check that after Electra fork, blob count goes to MAX_BLOBS_PER_BLOCK_ELECTRA (9)
    assert spec.config.MAX_BLOBS_PER_BLOCK_ELECTRA == spec.get_max_blobs_per_block(
        spec.config.ELECTRA_FORK_EPOCH
    )
