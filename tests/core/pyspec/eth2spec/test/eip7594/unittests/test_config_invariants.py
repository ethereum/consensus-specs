from eth2spec.test.context import (
    single_phase,
    spec_test,
    with_eip7594_and_later,
)
from eth2spec.utils.ssz.ssz_typing import uint8


@with_eip7594_and_later
@spec_test
@single_phase
def test_invariants(spec):
    assert spec.FIELD_ELEMENTS_PER_BLOB % spec.FIELD_ELEMENTS_PER_CELL == 0
    assert spec.FIELD_ELEMENTS_PER_EXT_BLOB % spec.config.NUMBER_OF_COLUMNS == 0
    assert spec.config.SAMPLES_PER_SLOT <= spec.config.NUMBER_OF_COLUMNS
    assert spec.config.NUMBER_OF_COLUMNS == uint8(spec.config.NUMBER_OF_COLUMNS)  # ENR field is uint8
    assert spec.config.CUSTODY_REQUIREMENT <= spec.config.DATA_COLUMN_SIDECAR_SUBNET_COUNT
    assert spec.config.DATA_COLUMN_SIDECAR_SUBNET_COUNT <= spec.config.NUMBER_OF_COLUMNS
    assert spec.config.NUMBER_OF_COLUMNS % int(spec.config.DATA_COLUMN_SIDECAR_SUBNET_COUNT) == 0
    assert spec.config.MAX_REQUEST_DATA_COLUMN_SIDECARS == (
        spec.config.MAX_REQUEST_BLOCKS_DENEB * spec.config.NUMBER_OF_COLUMNS
    )


@with_eip7594_and_later
@spec_test
@single_phase
def test_polynomical_commitments_sampling(spec):
    assert spec.FIELD_ELEMENTS_PER_EXT_BLOB == 2 * spec.FIELD_ELEMENTS_PER_BLOB
