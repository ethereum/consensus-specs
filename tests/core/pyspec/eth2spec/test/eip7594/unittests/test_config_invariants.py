from eth2spec.test.context import (
    single_phase,
    spec_test,
    with_eip7594_and_later,
)


@with_eip7594_and_later
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
    assert spec.config.MAX_CELLS_IN_EXTENDED_MATRIX == spec.MAX_BLOBS_PER_BLOCK * spec.config.NUMBER_OF_COLUMNS


@with_eip7594_and_later
@spec_test
@single_phase
def test_polynomical_commitments_sampling(spec):
    assert spec.FIELD_ELEMENTS_PER_EXT_BLOB == 2 * spec.FIELD_ELEMENTS_PER_BLOB
