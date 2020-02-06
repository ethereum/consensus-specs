from eth2spec.test.context import (
    with_all_phases_except,
    expect_assertion_error,
    spec_state_test,
    always_bls,
)
from eth2spec.test.helpers.attestations import (
    get_valid_attestation,
    sign_attestation,
)

from eth2spec.utils.ssz.ssz_typing import Bitlist


def run_attestation_processing(spec, state, attestation, valid=True):
    """
    Run ``process_attestation``, yielding:
      - pre-state ('pre')
      - attestation ('attestation')
      - post-state ('post').
    If ``valid == False``, run expecting ``AssertionError``
    """
    # yield pre-state
    yield 'pre', state

    yield 'attestation', attestation

    # If the attestation is invalid, processing is aborted, and there is no post-state.
    if not valid:
        expect_assertion_error(lambda: spec.process_attestation(state, attestation))
        yield 'post', None
        return

    current_epoch_count = len(state.current_epoch_attestations)
    previous_epoch_count = len(state.previous_epoch_attestations)

    # process attestation
    spec.process_attestation(state, attestation)

    # Make sure the attestation has been processed
    if attestation.data.target.epoch == spec.get_current_epoch(state):
        assert len(state.current_epoch_attestations) == current_epoch_count + 1
    else:
        assert len(state.previous_epoch_attestations) == previous_epoch_count + 1

    # yield post-state
    yield 'post', state


@with_all_phases_except(['phase0'])
@spec_state_test
@always_bls
def test_success_empty_custody_bits_blocks(spec, state):
    attestation = get_valid_attestation(spec, state)
    attestation.custody_bits_blocks = []
    sign_attestation(spec, state, attestation)

    state.slot += spec.MIN_ATTESTATION_INCLUSION_DELAY

    yield from run_attestation_processing(spec, state, attestation)


@with_all_phases_except(['phase0'])
@spec_state_test
@always_bls
def test_fail_custody_bits_blocks_incorrect_slot(spec, state):
    attestation = get_valid_attestation(spec, state)
    committee = spec.get_beacon_committee(
        state,
        attestation.data.slot,
        attestation.data.index,
    )
    bitlist = Bitlist[spec.MAX_VALIDATORS_PER_COMMITTEE]([0 for _ in range(len(committee))])
    bitlist[0] = 1
    attestation.custody_bits_blocks = [bitlist]
    sign_attestation(spec, state, attestation)

    state.slot += spec.MIN_ATTESTATION_INCLUSION_DELAY + 1

    yield from run_attestation_processing(spec, state, attestation)