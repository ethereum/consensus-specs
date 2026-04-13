import random

from eth_consensus_specs.test.context import (
    single_phase,
    spec_test,
    with_fulu_and_later,
)


def _run_compute_columns_for_custody_group(spec, rng, custody_group=None):
    if custody_group is None:
        custody_group = rng.randint(0, spec.config.NUMBER_OF_CUSTODY_GROUPS - 1)

    result = spec.compute_columns_for_custody_group(custody_group)
    yield "custody_group", "meta", custody_group

    assert len(result) == len(set(result))
    assert len(result) == spec.NUMBER_OF_COLUMNS // spec.config.NUMBER_OF_CUSTODY_GROUPS
    assert all(i < spec.NUMBER_OF_COLUMNS for i in result)
    python_list_result = [int(i) for i in result]

    yield "result", "meta", python_list_result


@with_fulu_and_later
@spec_test
@single_phase
def test_compute_columns_for_custody_group__min_custody_group(spec):
    rng = random.Random(1111)
    yield from _run_compute_columns_for_custody_group(spec, rng, custody_group=0)


@with_fulu_and_later
@spec_test
@single_phase
def test_compute_columns_for_custody_group__max_custody_group(spec):
    rng = random.Random(1111)
    yield from _run_compute_columns_for_custody_group(
        spec, rng, custody_group=spec.config.NUMBER_OF_CUSTODY_GROUPS - 1
    )


@with_fulu_and_later
@spec_test
@single_phase
def test_compute_columns_for_custody_group__1(spec):
    rng = random.Random(1111)
    yield from _run_compute_columns_for_custody_group(spec, rng)


@with_fulu_and_later
@spec_test
@single_phase
def test_compute_columns_for_custody_group__2(spec):
    rng = random.Random(2222)
    yield from _run_compute_columns_for_custody_group(spec, rng)


@with_fulu_and_later
@spec_test
@single_phase
def test_compute_columns_for_custody_group__3(spec):
    rng = random.Random(3333)
    yield from _run_compute_columns_for_custody_group(spec, rng)
