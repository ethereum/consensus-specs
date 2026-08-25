from eth_consensus_specs.test.context import (
    spec_state_test,
    with_eip8205_and_later,
    with_presets,
)
from eth_consensus_specs.test.helpers.block import build_empty_block
from eth_consensus_specs.test.helpers.constants import MINIMAL
from eth_consensus_specs.test.helpers.keys import (
    privkeys,
    pubkeys,
)
from eth_consensus_specs.test.helpers.preregistrations import (
    build_preregistration_request,
    preregistration_withdrawal_credentials,
)
from eth_consensus_specs.test.helpers.state import state_transition_and_sign_block
from eth_consensus_specs.test.helpers.withdrawals import set_parent_block_full

# A key pair that is not part of the genesis validator set
FRESH_PUBKEY = pubkeys[-1]
FRESH_PRIVKEY = privkeys[-1]


@with_eip8205_and_later
@spec_state_test
@with_presets([MINIMAL], reason="filling the preregistration list is slow on mainnet")
def test_preregistration_admitted_after_epoch_sweep(spec, state):
    """
    A block whose transition crosses an epoch boundary first sweeps the expired
    records, then admits the parent payload's preregistration into the compacted
    list. The pre-state still holds a full list of expired records, so both steps
    happen inside this transition.
    """
    for index in range(spec.PREREGISTRATIONS_LIMIT):
        state.validator_preregistrations.append(
            spec.StoredPreregistration(
                pubkey=spec.BLSPubkey(index.to_bytes(48, "little")),
                withdrawal_credentials=preregistration_withdrawal_credentials(spec),
                expiry_slot=spec.Slot(spec.PREREGISTRATION_EXPIRY_SLOTS),
            )
        )

    # The records survive the transition at their deadline: the outstanding bid
    # is still from an earlier covered slot.
    spec.process_slots(state, spec.PREREGISTRATION_EXPIRY_SLOTS)
    assert len(state.validator_preregistrations) == spec.PREREGISTRATIONS_LIMIT

    request = build_preregistration_request(
        spec, state, FRESH_PUBKEY, FRESH_PRIVKEY, preregistration_withdrawal_credentials(spec)
    )
    requests = spec.ExecutionRequests(
        preregistrations=spec.PreregistrationRequests([request]),
    )
    set_parent_block_full(spec, state)
    state.latest_execution_payload_bid.execution_requests_root = spec.hash_tree_root(requests)
    # The payload now outstanding was created at the records' expiry slot, so
    # they are no longer covered by it
    state.latest_execution_payload_bid.slot = state.slot

    # Missed slots delay the payload to the next epoch boundary
    block = build_empty_block(spec, state, state.slot + spec.SLOTS_PER_EPOCH)
    block.body.parent_execution_requests = requests

    yield "pre", state
    signed_block = state_transition_and_sign_block(spec, state, block)
    yield "blocks", [signed_block]
    yield "post", state

    # The sweep freed the whole list and the new preregistration was admitted
    assert len(state.validator_preregistrations) == 1
    assert state.validator_preregistrations[0].pubkey == FRESH_PUBKEY
