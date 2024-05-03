import random

from eth2spec.test.context import (
    single_phase,
    spec_test,
    with_eip7594_and_later,
)


def _run_get_custody_columns(spec, rng, node_id=None, custody_subnet_count=None):
    if node_id is None:
        node_id = rng.randint(0, 2**256 - 1)

    if custody_subnet_count is None:
        custody_subnet_count = rng.randint(0, spec.config.DATA_COLUMN_SIDECAR_SUBNET_COUNT)

    result = spec.get_custody_columns(node_id, custody_subnet_count)
    yield 'node_id', 'meta', hex(node_id)
    yield 'custody_subnet_count', 'meta', custody_subnet_count

    assert len(result) == len(set(result))
    assert len(result) == (
        custody_subnet_count * spec.config.NUMBER_OF_COLUMNS // spec.config.DATA_COLUMN_SIDECAR_SUBNET_COUNT
    )
    assert all(i < spec.config.NUMBER_OF_COLUMNS for i in result)
    python_list_result = [int(i) for i in result]

    yield 'result', 'meta', python_list_result


@with_eip7594_and_later
@spec_test
@single_phase
def test_get_custody_columns__min_node_id_min_custody_subnet_count(spec):
    rng = random.Random(1111)
    yield from _run_get_custody_columns(spec, rng, node_id=0, custody_subnet_count=0)


@with_eip7594_and_later
@spec_test
@single_phase
def test_get_custody_columns__min_node_id_max_custody_subnet_count(spec):
    rng = random.Random(1111)
    yield from _run_get_custody_columns(
        spec, rng, node_id=0,
        custody_subnet_count=spec.config.DATA_COLUMN_SIDECAR_SUBNET_COUNT)


@with_eip7594_and_later
@spec_test
@single_phase
def test_get_custody_columns__max_node_id_min_custody_subnet_count(spec):
    rng = random.Random(1111)
    yield from _run_get_custody_columns(spec, rng, node_id=2**256 - 1, custody_subnet_count=0)


@with_eip7594_and_later
@spec_test
@single_phase
def test_get_custody_columns__max_node_id_max_custody_subnet_count(spec):
    rng = random.Random(1111)
    yield from _run_get_custody_columns(
        spec, rng, node_id=2**256 - 1,
        custody_subnet_count=spec.config.DATA_COLUMN_SIDECAR_SUBNET_COUNT,
    )


@with_eip7594_and_later
@spec_test
@single_phase
def test_get_custody_columns__1(spec):
    rng = random.Random(1111)
    yield from _run_get_custody_columns(spec, rng)


@with_eip7594_and_later
@spec_test
@single_phase
def test_get_custody_columns__2(spec):
    rng = random.Random(2222)
    yield from _run_get_custody_columns(spec, rng)


@with_eip7594_and_later
@spec_test
@single_phase
def test_get_custody_columns__3(spec):
    rng = random.Random(3333)
    yield from _run_get_custody_columns(spec, rng)
