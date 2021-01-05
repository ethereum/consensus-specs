import random
from eth2spec.test.helpers.block import (
    build_empty_block_for_next_slot,
)
from eth2spec.test.lightclient_patch.helpers import (
    compute_aggregate_sync_committee_signature,
)
from eth2spec.test.context import (
    PHASE0, PHASE1,
    expect_assertion_error,
    with_all_phases_except,
    spec_state_test,
)


@with_all_phases_except([PHASE0, PHASE1])
@spec_state_test
def test_invalid_sync_committee_bits(spec, state):
    committee = spec.get_sync_committee_indices(state, spec.get_current_epoch(state))
    random_participant = random.choice(committee)

    yield 'pre', state

    block = build_empty_block_for_next_slot(spec, state)
    # Exclude one participant whose signature was included.
    block.body.sync_committee_bits = [index != random_participant for index in committee]
    block.body.sync_committee_signature = compute_aggregate_sync_committee_signature(
        spec,
        state,
        block.slot - 1,
        committee,
    )

    yield 'blocks', [block]
    expect_assertion_error(lambda: spec.process_sync_committee(state, block.body))
    yield 'post', None
