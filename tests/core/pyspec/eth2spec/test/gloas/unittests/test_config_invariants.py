from eth2spec.test.context import (
    single_phase,
    spec_test,
    with_gloas_and_later,
)


def make_bid(spec, value):
    """Helper to create an ExecutionPayloadBid with a given value."""
    kzg_list = spec.List[spec.KZGCommitment, spec.MAX_BLOB_COMMITMENTS_PER_BLOCK]()
    return spec.ExecutionPayloadBid(
        slot=spec.Slot(0),
        value=spec.Gwei(value),
        blob_kzg_commitments_root=kzg_list.hash_tree_root(),
    )


def min_increase(spec, current_value):
    """Compute ceil(current_value * MIN_BID_INCREASE_PERCENT / 100)."""
    quotient = current_value // 100
    remainder = current_value % 100
    result = quotient * spec.MIN_BID_INCREASE_PERCENT
    result += (remainder * spec.MIN_BID_INCREASE_PERCENT + 99) // 100
    return result


@with_gloas_and_later
@spec_test
@single_phase
def test_is_higher_value_bid__lower(spec):
    """Lower new bid should return False."""
    current_bid = make_bid(spec, 100)

    assert spec.is_higher_value_bid(current_bid, make_bid(spec, 99)) is False


@with_gloas_and_later
@spec_test
@single_phase
def test_is_higher_value_bid__100(spec):
    """current=100: test at and below threshold."""
    current_value = 100
    current_bid = make_bid(spec, current_value)
    threshold = min_increase(spec, current_value)

    # One below threshold should fail
    assert (
        spec.is_higher_value_bid(current_bid, make_bid(spec, current_value + threshold - 1))
        is False
    )
    # At threshold should pass
    assert spec.is_higher_value_bid(current_bid, make_bid(spec, current_value + threshold)) is True


@with_gloas_and_later
@spec_test
@single_phase
def test_is_higher_value_bid__ceil_101(spec):
    """current=101: test ceiling behavior."""
    current_value = 101
    current_bid = make_bid(spec, current_value)
    threshold = min_increase(spec, current_value)

    # One below threshold should fail
    assert (
        spec.is_higher_value_bid(current_bid, make_bid(spec, current_value + threshold - 1))
        is False
    )
    # At threshold should pass
    assert spec.is_higher_value_bid(current_bid, make_bid(spec, current_value + threshold)) is True


@with_gloas_and_later
@spec_test
@single_phase
def test_is_higher_value_bid__ceil_150(spec):
    """current=150: test ceiling behavior."""
    current_value = 150
    current_bid = make_bid(spec, current_value)
    threshold = min_increase(spec, current_value)

    # One below threshold should fail
    assert (
        spec.is_higher_value_bid(current_bid, make_bid(spec, current_value + threshold - 1))
        is False
    )
    # At threshold should pass
    assert spec.is_higher_value_bid(current_bid, make_bid(spec, current_value + threshold)) is True


@with_gloas_and_later
@spec_test
@single_phase
def test_is_higher_value_bid__ceil_33(spec):
    """current=33: test ceiling behavior."""
    current_value = 33
    current_bid = make_bid(spec, current_value)
    threshold = min_increase(spec, current_value)

    # One below threshold should fail
    assert (
        spec.is_higher_value_bid(current_bid, make_bid(spec, current_value + threshold - 1))
        is False
    )
    # At threshold should pass
    assert spec.is_higher_value_bid(current_bid, make_bid(spec, current_value + threshold)) is True


@with_gloas_and_later
@spec_test
@single_phase
def test_is_higher_value_bid__ceil_34(spec):
    """current=34: test ceiling behavior."""
    current_value = 34
    current_bid = make_bid(spec, current_value)
    threshold = min_increase(spec, current_value)

    # One below threshold should fail
    assert (
        spec.is_higher_value_bid(current_bid, make_bid(spec, current_value + threshold - 1))
        is False
    )
    # At threshold should pass
    assert spec.is_higher_value_bid(current_bid, make_bid(spec, current_value + threshold)) is True


@with_gloas_and_later
@spec_test
@single_phase
def test_is_higher_value_bid__large_values(spec):
    """Test with large values to ensure no overflow."""
    current_value = 10**18
    current_bid = make_bid(spec, current_value)
    threshold = min_increase(spec, current_value)

    # One below threshold should fail
    assert (
        spec.is_higher_value_bid(current_bid, make_bid(spec, current_value + threshold - 1))
        is False
    )
    # At threshold should pass
    assert spec.is_higher_value_bid(current_bid, make_bid(spec, current_value + threshold)) is True


@with_gloas_and_later
@spec_test
@single_phase
def test_is_higher_value_bid__ceil_prime_97(spec):
    """current=97 (prime): test ceiling behavior."""
    current_value = 97
    current_bid = make_bid(spec, current_value)
    threshold = min_increase(spec, current_value)

    # One below threshold should fail
    assert (
        spec.is_higher_value_bid(current_bid, make_bid(spec, current_value + threshold - 1))
        is False
    )
    # At threshold should pass
    assert spec.is_higher_value_bid(current_bid, make_bid(spec, current_value + threshold)) is True


@with_gloas_and_later
@spec_test
@single_phase
def test_is_higher_value_bid__ceil_1(spec):
    """current=1: test ceiling behavior with small value."""
    current_value = 1
    current_bid = make_bid(spec, current_value)
    threshold = min_increase(spec, current_value)

    # One below threshold should fail
    assert (
        spec.is_higher_value_bid(current_bid, make_bid(spec, current_value + threshold - 1))
        is False
    )
    # At threshold should pass
    assert spec.is_higher_value_bid(current_bid, make_bid(spec, current_value + threshold)) is True


@with_gloas_and_later
@spec_test
@single_phase
def test_is_higher_value_bid__ceil_999(spec):
    """current=999: test ceiling behavior."""
    current_value = 999
    current_bid = make_bid(spec, current_value)
    threshold = min_increase(spec, current_value)

    # One below threshold should fail
    assert (
        spec.is_higher_value_bid(current_bid, make_bid(spec, current_value + threshold - 1))
        is False
    )
    # At threshold should pass
    assert spec.is_higher_value_bid(current_bid, make_bid(spec, current_value + threshold)) is True
