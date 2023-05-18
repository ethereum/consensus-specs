from eth2spec.test.context import (
    spec_state_test,
    with_altair_and_later,
)
from eth2spec.test.helpers.attestations import (
    run_attestation_processing,
    get_valid_attestation,
)
from eth2spec.test.helpers.state import (
    next_slots,
)
from eth2spec.test.helpers.block import build_empty_block


@with_altair_and_later
@spec_state_test
def test_slashed_proposer_rewarded_for_attestation_inclusion(spec, state):
    attestation = get_valid_attestation(spec, state, signed=True)
    next_slots(spec, state, spec.MIN_ATTESTATION_INCLUSION_DELAY)

    # Process block header as proposer index is read from the state since EIP-6988
    block = build_empty_block(spec, state)
    spec.process_block_header(state, block)

    # Slash proposer
    state.validators[block.proposer_index].slashed = True
    pre_state_proposer_balance = state.balances[block.proposer_index]

    yield from run_attestation_processing(spec, state, attestation)

    # Check proposer gets rewarded
    assert state.balances[block.proposer_index] > pre_state_proposer_balance
