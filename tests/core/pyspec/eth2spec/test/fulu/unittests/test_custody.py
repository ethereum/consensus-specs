from eth2spec.test.context import (
    expect_assertion_error,
    single_phase,
    spec_test,
    with_fulu_and_later,
)


def run_get_custody_columns(spec, peer_count, custody_group_count):
    assignments = [
        spec.get_custody_groups(node_id, custody_group_count) for node_id in range(peer_count)
    ]

    columns_per_group = spec.NUMBER_OF_COLUMNS // spec.config.NUMBER_OF_CUSTODY_GROUPS
    for assignment in assignments:
        columns = []
        for group in assignment:
            group_columns = spec.compute_columns_for_custody_group(group)
            assert len(group_columns) == columns_per_group
            columns.extend(group_columns)

        assert len(columns) == custody_group_count * columns_per_group
        assert len(columns) == len(set(columns))


@with_fulu_and_later
@spec_test
@single_phase
def test_get_custody_columns_peers_within_number_of_columns(spec):
    peer_count = 10
    custody_group_count = spec.config.CUSTODY_REQUIREMENT
    assert spec.NUMBER_OF_COLUMNS > peer_count
    run_get_custody_columns(spec, peer_count, custody_group_count)


@with_fulu_and_later
@spec_test
@single_phase
def test_get_custody_columns_peers_more_than_number_of_columns(spec):
    peer_count = 200
    custody_group_count = spec.config.CUSTODY_REQUIREMENT
    assert spec.NUMBER_OF_COLUMNS < peer_count
    run_get_custody_columns(spec, peer_count, custody_group_count)


@with_fulu_and_later
@spec_test
@single_phase
def test_get_custody_columns_maximum_groups(spec):
    peer_count = 10
    custody_group_count = spec.config.NUMBER_OF_CUSTODY_GROUPS
    run_get_custody_columns(spec, peer_count, custody_group_count)


@with_fulu_and_later
@spec_test
@single_phase
def test_get_custody_columns_custody_size_more_than_number_of_groups(spec):
    node_id = 1
    custody_group_count = spec.config.NUMBER_OF_CUSTODY_GROUPS + 1
    expect_assertion_error(lambda: spec.get_custody_groups(node_id, custody_group_count))


@with_fulu_and_later
@spec_test
@single_phase
def test_compute_columns_for_custody_group_out_of_bound_custody_group(spec):
    expect_assertion_error(
        lambda: spec.compute_columns_for_custody_group(spec.config.NUMBER_OF_CUSTODY_GROUPS)
    )
