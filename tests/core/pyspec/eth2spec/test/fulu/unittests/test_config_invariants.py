from eth2spec.test.context import (
    single_phase,
    spec_test,
    spec_state_test,
    with_presets,
    with_fulu_and_later,
    expect_assertion_error,
)
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
@with_presets([MAINNET], reason="to have fork epoch number")
def test_blob_schedule(spec):
    for entry in spec.config.BLOB_SCHEDULE:
        # Check that all epochs are post-Deneb
        assert entry["EPOCH"] >= spec.config.DENEB_FORK_EPOCH
        # Check that all blob counts are less than the limit
        assert entry["MAX_BLOBS_PER_BLOCK"] <= spec.MAX_BLOB_COMMITMENTS_PER_BLOCK


@with_fulu_and_later
@spec_test
@single_phase
@with_presets([MAINNET], reason="to have fork epoch number")
def test_get_max_blobs(spec):
    # Check that before Deneb fork there is no blob count
    assert 0 == spec.get_max_blobs_per_block(spec.config.DENEB_FORK_EPOCH - 1)
    # Check that at the Deneb fork, blob count is equal to MAX_BLOBS_PER_BLOCK
    assert spec.config.MAX_BLOBS_PER_BLOCK == spec.get_max_blobs_per_block(
        spec.config.DENEB_FORK_EPOCH
    )
    # Check that until Electra fork, blob count is still MAX_BLOBS_PER_BLOCK
    assert spec.config.MAX_BLOBS_PER_BLOCK == spec.get_max_blobs_per_block(
        spec.config.ELECTRA_FORK_EPOCH - 1
    )
    # Check that at the Electra fork, blob count goes to MAX_BLOBS_PER_BLOCK_ELECTRA
    assert spec.config.MAX_BLOBS_PER_BLOCK_ELECTRA == spec.get_max_blobs_per_block(
        spec.config.ELECTRA_FORK_EPOCH
    )
