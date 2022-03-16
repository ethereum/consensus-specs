from eth2spec.test.helpers.execution_payload import (
    build_empty_execution_payload,
)

from eth2spec.test.context import spec_state_test, expect_assertion_error, with_capella_and_later

def run_bls_to_execution_change_processing(spec, state, address_change, valid=True):
    """
    Run ``process_bls_to_execution_change``, yielding:
      - pre-state ('pre')
      - address-change ('address_change')
      - post-state ('post').
    If ``valid == False``, run expecting ``AssertionError``
    """
    # yield pre-state
    yield 'pre', state

    yield 'address_change', address_change

    # If the address_change is invalid, processing is aborted, and there is no post-state.
    if not valid:
        expect_assertion_error(lambda: spec.process_bls_to_execution_change(state, attestation))
        yield 'post', None
        return

    # process address change
    spec.process_bls_to_execution_change(state, attestation)

    # Make sure the address change has been processed
    assert state.withdrawal_credentials[:1] == ETH1_ADDRESS_WITHDRAWAL_PREFIX
    assert state.withdrawal_credentials[1:12] == b'\x00' * 11
    assert state.withdrawal_credentials[12:] == address_change.to_execution_address

    # yield post-state
    yield 'post', state


@with_capella_and_later
@spec_state_test
def test_success(spec, state):
    address_change = spec.BLSToExecutionChange(
        validator_index=0,
        from_bls_pubkey=TEST,
        to_execution_address=b'\x42' * 20,
    )

    yield from run_bls_to_execution_change_processing(spec, state, address_change)
