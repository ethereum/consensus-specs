from eth2spec.test.context import (
    spec_test,
    single_phase,
    with_eip7594_and_later,
)


@with_eip7594_and_later
@spec_test
@single_phase
def test_compute_subnet_for_data_column_sidecar(spec):
    subnet_results = []
    for column_index in range(spec.DATA_COLUMN_SIDECAR_SUBNET_COUNT):
        subnet_results.append(spec.compute_subnet_for_data_column_sidecar(column_index))
    # no duplicates
    assert len(subnet_results) == len(set(subnet_results))
    # next one should be duplicate
    next_subnet = spec.compute_subnet_for_data_column_sidecar(spec.DATA_COLUMN_SIDECAR_SUBNET_COUNT)
    assert next_subnet == subnet_results[0]
