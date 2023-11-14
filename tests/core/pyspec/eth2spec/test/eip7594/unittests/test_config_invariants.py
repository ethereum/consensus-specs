from eth2spec.test.context import (
    spec_test,
    single_phase,
    with_eip7594_and_later,
)


@with_eip7594_and_later
@spec_test
@single_phase
def test_invariants(spec):
    assert spec.FIELD_ELEMENTS_PER_BLOB % spec.FIELD_ELEMENTS_PER_CELL == 0
    assert spec.FIELD_ELEMENTS_PER_BLOB * 2 % spec.NUMBER_OF_COLUMNS == 0
    assert spec.SAMPLES_PER_SLOT <= spec.NUMBER_OF_COLUMNS
    assert spec.CUSTODY_REQUIREMENT <= spec.NUMBER_OF_COLUMNS
    assert spec.DATA_COLUMN_SIDECAR_SUBNET_COUNT <= spec.NUMBER_OF_COLUMNS
    assert spec.NUMBER_OF_COLUMNS % spec.DATA_COLUMN_SIDECAR_SUBNET_COUNT == 0
