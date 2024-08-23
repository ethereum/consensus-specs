from eth2spec.test.context import (
    expect_assertion_error,
    spec_test,
    single_phase,
    with_eip7594_and_later,
)
from eth2spec.utils.ssz.ssz_typing import uint8


def run_get_custody_columns(spec, peer_count, custody_subnet_count):
    assignments = [spec.get_custody_columns(node_id, custody_subnet_count) for node_id in range(peer_count)]

    columns_per_subnet = spec.config.NUMBER_OF_COLUMNS // spec.config.DATA_COLUMN_SIDECAR_SUBNET_COUNT
    for assignment in assignments:
        assert len(assignment) == custody_subnet_count * columns_per_subnet
        assert len(assignment) == len(set(assignment))


@with_eip7594_and_later
@spec_test
@single_phase
def test_get_custody_columns_peers_within_number_of_columns(spec):
    peer_count = 10
    custody_subnet_count = spec.config.CUSTODY_REQUIREMENT
    assert spec.config.NUMBER_OF_COLUMNS > peer_count
    run_get_custody_columns(spec, peer_count, custody_subnet_count)


@with_eip7594_and_later
@spec_test
@single_phase
def test_get_custody_columns_peers_more_than_number_of_columns(spec):
    peer_count = 200
    custody_subnet_count = spec.config.CUSTODY_REQUIREMENT
    assert spec.config.NUMBER_OF_COLUMNS < peer_count
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


@with_eip7594_and_later
@spec_test
@single_phase
def test_custody_subnet_count_int_bitlength(custody_subnet_count):
    assert uint8(custody_subnet_count) == custody_subnet_count
