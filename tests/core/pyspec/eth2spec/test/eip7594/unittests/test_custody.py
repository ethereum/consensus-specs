from eth2spec.test.context import (
    expect_assertion_error,
    spec_test,
    single_phase,
    with_eip7594_and_later,
)


def run_get_custody_columns(spec, peer_count, custody_subnet_count):
    assignments = [spec.get_custody_columns(node_id, custody_subnet_count) for node_id in range(peer_count)]

    subnet_per_column = spec.NUMBER_OF_COLUMNS // spec.config.DATA_COLUMN_SIDECAR_SUBNET_COUNT
    for assignment in assignments:
        assert len(assignment) == custody_subnet_count * subnet_per_column


@with_eip7594_and_later
@spec_test
@single_phase
def test_get_custody_columns_peers_within_number_of_columns(spec):
    peer_count = 10
    custody_subnet_count = spec.CUSTODY_REQUIREMENT
    assert spec.NUMBER_OF_COLUMNS > peer_count
    run_get_custody_columns(spec, peer_count, custody_subnet_count)


@with_eip7594_and_later
@spec_test
@single_phase
def test_get_custody_columns_peers_more_than_number_of_columns(spec):
    peer_count = 200
    custody_subnet_count = spec.CUSTODY_REQUIREMENT
    assert spec.NUMBER_OF_COLUMNS < peer_count
    run_get_custody_columns(spec, peer_count, custody_subnet_count)


@with_eip7594_and_later
@spec_test
@single_phase
def test_get_custody_columns_maximum_subnets(spec):
    peer_count = 10
    custody_subnet_count = spec.config.DATA_COLUMN_SIDECAR_SUBNET_COUNT
    run_get_custody_columns(spec, peer_count, custody_subnet_count)


@with_eip7594_and_later
@spec_test
@single_phase
def test_get_custody_columns_custody_size_more_than_number_of_columns(spec):
    node_id = 1
    custody_subnet_count = spec.config.DATA_COLUMN_SIDECAR_SUBNET_COUNT + 1
    expect_assertion_error(lambda: spec.get_custody_columns(node_id, custody_subnet_count))
