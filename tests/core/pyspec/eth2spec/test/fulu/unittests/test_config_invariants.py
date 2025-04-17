from eth2spec.test.context import (
    single_phase,
    spec_test,
    with_fulu_and_later,
)

from eth2spec.test.helpers.constants import (
    MAINNET,
    MINIMAL,
)
from eth2spec.test.context import with_presets
from eth2spec.test.context import spec_state_test, with_phases, FULU


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
    assert spec.config.MAX_BLOBS_PER_BLOCK_FULU <= spec.MAX_BLOB_COMMITMENTS_PER_BLOCK


@with_fulu_and_later
@spec_state_test
def test_get_max_blobs(spec, state):
    max_blobs = spec.get_max_blobs_per_block(269568 + 1)
    assert max_blobs == 6
    max_blobs = spec.get_max_blobs_per_block(364032 + 1)
    assert max_blobs == 9
