from eth2spec.test.context import spec_test, with_whisk_and_later
from eth2spec.test.context import single_phase


# Note: remove once whisk is rebased on top of deneb
def is_power_of_two(value: int) -> bool:
    """
    Check if ``value`` is a power of two integer.
    """
    return (value > 0) and (value & (value - 1) == 0)


@with_whisk_and_later
@spec_test
@single_phase
def test_curdleproof(spec):
    assert is_power_of_two(spec.CURDLEPROOFS_N_BLINDERS + spec.WHISK_VALIDATORS_PER_SHUFFLE)
