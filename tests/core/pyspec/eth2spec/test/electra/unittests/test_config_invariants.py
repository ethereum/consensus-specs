from eth2spec.test.context import (
    single_phase,
    spec_test,
    with_electra_and_later,
)


@with_electra_and_later
@spec_test
@single_phase
def test_processing_pending_partial_withdrawals(spec):
    assert spec.MAX_PENDING_PARTIALS_PER_WITHDRAWALS_SWEEP < spec.MAX_WITHDRAWALS_PER_PAYLOAD
