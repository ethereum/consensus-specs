import random

from eth2spec.test.context import (
    single_phase,
    spec_test,
    with_fulu_and_later,
)


def _run_get_custody_columns(spec, rng, node_id=None, custody_group_count=None):
    if node_id is None:
        node_id = rng.randint(0, 2**256 - 1)

    if custody_group_count is None:
        custody_group_count = rng.randint(0, spec.config.NUMBER_OF_CUSTODY_GROUPS)

    columns_per_group = spec.config.NUMBER_OF_COLUMNS // spec.config.NUMBER_OF_CUSTODY_GROUPS
    groups = spec.get_custody_groups(node_id, custody_group_count)
    yield 'node_id', 'meta', node_id
    yield 'custody_group_count', 'meta', int(custody_group_count)

    result = []
    for group in groups:
        group_columns = spec.compute_columns_for_custody_group(group)
        assert len(group_columns) == columns_per_group
        result.extend(group_columns)

    assert len(result) == len(set(result))
    assert len(result) == custody_group_count * columns_per_group
    assert all(i < spec.config.NUMBER_OF_COLUMNS for i in result)
    python_list_result = [int(i) for i in result]

    yield 'result', 'meta', python_list_result


@with_fulu_and_later
@spec_test
@single_phase
def test_get_custody_columns__min_node_id_min_custody_group_count(spec):
    rng = random.Random(1111)
    yield from _run_get_custody_columns(spec, rng, node_id=0, custody_group_count=0)


@with_fulu_and_later
@spec_test
@single_phase
def test_get_custody_columns__min_node_id_max_custody_group_count(spec):
    rng = random.Random(1111)
    yield from _run_get_custody_columns(
        spec, rng, node_id=0,
        custody_group_count=spec.config.NUMBER_OF_CUSTODY_GROUPS)


@with_fulu_and_later
@spec_test
@single_phase
def test_get_custody_columns__max_node_id_min_custody_group_count(spec):
    rng = random.Random(1111)
    yield from _run_get_custody_columns(spec, rng, node_id=2**256 - 1, custody_group_count=0)


@with_fulu_and_later
@spec_test
@single_phase
def test_get_custody_columns__max_node_id_max_custody_group_count(spec):
    rng = random.Random(1111)
    yield from _run_get_custody_columns(
        spec, rng, node_id=2**256 - 1,
        custody_group_count=spec.config.NUMBER_OF_CUSTODY_GROUPS,
    )


@with_fulu_and_later
@spec_test
@single_phase
def test_get_custody_columns__max_node_id_max_custody_group_count_minus_1(spec):
    rng = random.Random(1111)
    yield from _run_get_custody_columns(
        spec, rng, node_id=2**256 - 2,
        custody_group_count=spec.config.NUMBER_OF_CUSTODY_GROUPS,
    )


@with_fulu_and_later
@spec_test
@single_phase
def test_get_custody_columns__short_node_id(spec):
    rng = random.Random(1111)
    yield from _run_get_custody_columns(spec, rng, node_id=1048576, custody_group_count=1)


@with_fulu_and_later
@spec_test
@single_phase
def test_get_custody_columns__1(spec):
    rng = random.Random(1111)
    yield from _run_get_custody_columns(spec, rng)


@with_fulu_and_later
@spec_test
@single_phase
def test_get_custody_columns__2(spec):
    rng = random.Random(2222)
    yield from _run_get_custody_columns(spec, rng)


@with_fulu_and_later
@spec_test
@single_phase
def test_get_custody_columns__3(spec):
    rng = random.Random(3333)
    yield from _run_get_custody_columns(spec, rng)
