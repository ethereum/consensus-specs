from eth2spec.test.context import (
    single_phase,
    spec_test,
    with_electra_and_later,
)


@with_electra_and_later
@spec_test
@single_phase
def test_withdrawals(spec):
    assert spec.MAX_PARTIAL_WITHDRAWALS_PER_PAYLOAD < spec.MAX_WITHDRAWALS_PER_PAYLOAD
