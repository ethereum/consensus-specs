from eth2spec.test.context import (
    single_phase,
    spec_test,
    with_eip7594_and_later,
)


@with_eip7594_and_later
@spec_test
@single_phase
def test_polynomical_commitments_sampling(spec):
    assert spec.FIELD_ELEMENTS_PER_EXT_BLOB == 2 * spec.FIELD_ELEMENTS_PER_BLOB
