from eth_consensus_specs.test.context import (
    single_phase,
    spec_test,
    with_gloas_and_later,
)


@with_gloas_and_later
@spec_test
@single_phase
def test_increase_within_limit(spec):
    assert spec.is_gas_limit_target_compatible(60_000_000, 60_000_100, 60_000_100)


@with_gloas_and_later
@spec_test
@single_phase
def test_increase_exceeding_limit(spec):
    # max_gas_limit_difference = 60_000_000 // 1024 - 1 = 58_592
    assert spec.is_gas_limit_target_compatible(60_000_000, 60_058_592, 100_000_000)


@with_gloas_and_later
@spec_test
@single_phase
def test_increase_exceeding_limit_off_by_one_fails(spec):
    # gas_limit one above max_gas_limit (= 60_058_592) must fail (off by one)
    assert not spec.is_gas_limit_target_compatible(60_000_000, 60_058_593, 100_000_000)


@with_gloas_and_later
@spec_test
@single_phase
def test_decrease_within_limit(spec):
    assert spec.is_gas_limit_target_compatible(60_000_000, 59_999_990, 59_999_990)


@with_gloas_and_later
@spec_test
@single_phase
def test_decrease_exceeding_limit(spec):
    # max_gas_limit_difference = 60_000_000 // 1024 - 1 = 58_592
    assert spec.is_gas_limit_target_compatible(60_000_000, 59_941_408, 30_000_000)


@with_gloas_and_later
@spec_test
@single_phase
def test_target_equals_parent(spec):
    assert spec.is_gas_limit_target_compatible(60_000_000, 60_000_000, 60_000_000)


@with_gloas_and_later
@spec_test
@single_phase
def test_parent_gas_limit_underflows(spec):
    # parent_gas_limit // 1024 = 0; guard clamps to max(0, 1) - 1 = 0 (no underflow)
    assert spec.is_gas_limit_target_compatible(1023, 1023, 60_000_000)
