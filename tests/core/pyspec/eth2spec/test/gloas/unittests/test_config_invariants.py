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
    result = quotient * spec.config.MIN_BID_INCREASE_PERCENT
    result += (remainder * spec.config.MIN_BID_INCREASE_PERCENT + 99) // 100
    return result


def assert_threshold_boundary(spec, current_value):
    """Assert that threshold - 1 fails and threshold passes."""
    current_bid = make_bid(spec, current_value)
    threshold = min_increase(spec, current_value)

    # One below threshold should return false
    new_bid_below_threshold = make_bid(spec, current_value + threshold - 1)
    assert spec.is_higher_value_bid(current_bid, new_bid_below_threshold) is False

    # At threshold should return true
    new_bid_at_threshold = make_bid(spec, current_value + threshold)
    assert spec.is_higher_value_bid(current_bid, new_bid_at_threshold) is True


@with_gloas_and_later
@spec_test
@single_phase
def test_min_bid_increase_percent__greater_than_zero(spec):
    """Check that MIN_BID_INCREASE_PERCENT is a non-zero value."""
    assert spec.config.MIN_BID_INCREASE_PERCENT > 0


@with_gloas_and_later
@spec_test
@single_phase
def test_is_higher_value_bid__ceil_1(spec):
    """current=1: test ceiling behavior with small value."""
    assert_threshold_boundary(spec, 1)


@with_gloas_and_later
@spec_test
@single_phase
def test_is_higher_value_bid__ceil_2(spec):
    """current=2: test ceiling behavior with small value."""
    assert_threshold_boundary(spec, 2)


@with_gloas_and_later
@spec_test
@single_phase
def test_is_higher_value_bid__ceil_prime_97(spec):
    """current=97 (prime): test ceiling behavior."""
    assert_threshold_boundary(spec, 97)


@with_gloas_and_later
@spec_test
@single_phase
def test_is_higher_value_bid__100(spec):
    """current=100: test at and below threshold."""
    assert_threshold_boundary(spec, 100)


@with_gloas_and_later
@spec_test
@single_phase
def test_is_higher_value_bid__ceil_101(spec):
    """current=101: test ceiling behavior."""
    assert_threshold_boundary(spec, 101)


@with_gloas_and_later
@spec_test
@single_phase
def test_is_higher_value_bid__ceil_150(spec):
    """current=150: test ceiling behavior."""
    assert_threshold_boundary(spec, 150)


@with_gloas_and_later
@spec_test
@single_phase
def test_is_higher_value_bid__ceil_999(spec):
    """current=999: test ceiling behavior."""
    assert_threshold_boundary(spec, 999)


@with_gloas_and_later
@spec_test
@single_phase
def test_is_higher_value_bid__large_values(spec):
    """Test with large values to ensure no overflow."""
    assert_threshold_boundary(spec, 10**18)


@with_gloas_and_later
@spec_test
@single_phase
def test_is_higher_value_bid__uint64_max(spec):
    """current=UINT64_MAX: no valid new bid can be higher."""
    current_bid = make_bid(spec, spec.UINT64_MAX)

    # Same value should return false
    new_bid_same = make_bid(spec, spec.UINT64_MAX)
    assert spec.is_higher_value_bid(current_bid, new_bid_same) is False

    # Lower value should return false
    new_bid_lower = make_bid(spec, spec.UINT64_MAX - 1)
    assert spec.is_higher_value_bid(current_bid, new_bid_lower) is False


@with_gloas_and_later
@spec_test
@single_phase
def test_is_higher_value_bid__uint64_max_minus_one(spec):
    """current=UINT64_MAX-1: increase of 1 to UINT64_MAX is insufficient."""
    current_bid = make_bid(spec, spec.UINT64_MAX - 1)

    # Increase of 1 is below the minimum required threshold
    new_bid = make_bid(spec, spec.UINT64_MAX)
    assert spec.is_higher_value_bid(current_bid, new_bid) is False
