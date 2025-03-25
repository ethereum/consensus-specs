from eth2spec.test.context import (
    spec_state_test,
    with_presets,
    with_light_client,
)
from eth2spec.test.helpers.attestations import (
    next_slots_with_attestations,
    state_transition_with_full_block,
)
from eth2spec.test.helpers.constants import MINIMAL
from eth2spec.test.helpers.light_client import (
    create_update,
)
from eth2spec.test.helpers.state import (
    next_slots,
)


def create_test_update(
    spec, test, with_next, with_finality, participation_rate, signature_slot=None
):
    attested_state, attested_block, finalized_block = test
    return create_update(
        spec,
        attested_state,
        attested_block,
        finalized_block,
        with_next,
        with_finality,
        participation_rate,
        signature_slot=signature_slot,
    )


@with_light_client
@spec_state_test
@with_presets([MINIMAL], reason="too slow")
def test_update_ranking(spec, state):
    # Set up blocks and states:
    # - `sig_finalized` / `sig_attested` --> Only signature in next sync committee period
    # - `att_finalized` / `att_attested` --> Attested header also in next sync committee period
    # - `fin_finalized` / `fin_attested` --> Finalized header also in next sync committee period
    # - `lat_finalized` / `lat_attested` --> Like `fin`, but at a later `attested_header.beacon.slot`
    next_slots(
        spec,
        state,
        spec.compute_start_slot_at_epoch(spec.EPOCHS_PER_SYNC_COMMITTEE_PERIOD - 3) - 1,
    )
    sig_finalized_block = state_transition_with_full_block(spec, state, True, True)
    _, _, state = next_slots_with_attestations(spec, state, spec.SLOTS_PER_EPOCH - 1, True, True)
    att_finalized_block = state_transition_with_full_block(spec, state, True, True)
    _, _, state = next_slots_with_attestations(
        spec, state, 2 * spec.SLOTS_PER_EPOCH - 2, True, True
    )
    sig_attested_block = state_transition_with_full_block(spec, state, True, True)
    sig_attested_state = state.copy()
    att_attested_block = state_transition_with_full_block(spec, state, True, True)
    att_attested_state = state.copy()
    fin_finalized_block = att_attested_block
    _, _, state = next_slots_with_attestations(
        spec, state, 2 * spec.SLOTS_PER_EPOCH - 1, True, True
    )
    fin_attested_block = state_transition_with_full_block(spec, state, True, True)
    fin_attested_state = state.copy()
    lat_finalized_block = fin_finalized_block
    lat_attested_block = state_transition_with_full_block(spec, state, True, True)
    lat_attested_state = state.copy()
    sig = (sig_attested_state, sig_attested_block, sig_finalized_block)
    att = (att_attested_state, att_attested_block, att_finalized_block)
    fin = (fin_attested_state, fin_attested_block, fin_finalized_block)
    lat = (lat_attested_state, lat_attested_block, lat_finalized_block)

    # Create updates (in descending order of quality)
    updates = [
        # Updates with sync committee finality
        create_test_update(spec, fin, with_next=1, with_finality=1, participation_rate=1.0),
        create_test_update(spec, lat, with_next=1, with_finality=1, participation_rate=1.0),
        create_test_update(spec, fin, with_next=1, with_finality=1, participation_rate=0.8),
        create_test_update(spec, lat, with_next=1, with_finality=1, participation_rate=0.8),
        # Updates without sync committee finality
        create_test_update(spec, att, with_next=1, with_finality=1, participation_rate=1.0),
        create_test_update(spec, att, with_next=1, with_finality=1, participation_rate=0.8),
        # Updates without indication of any finality
        create_test_update(spec, att, with_next=1, with_finality=0, participation_rate=1.0),
        create_test_update(spec, fin, with_next=1, with_finality=0, participation_rate=1.0),
        create_test_update(spec, lat, with_next=1, with_finality=0, participation_rate=1.0),
        create_test_update(spec, att, with_next=1, with_finality=0, participation_rate=0.8),
        create_test_update(spec, fin, with_next=1, with_finality=0, participation_rate=0.8),
        create_test_update(spec, lat, with_next=1, with_finality=0, participation_rate=0.8),
        # Updates with sync committee finality but no `next_sync_committee`
        create_test_update(spec, sig, with_next=0, with_finality=1, participation_rate=1.0),
        create_test_update(spec, fin, with_next=0, with_finality=1, participation_rate=1.0),
        create_test_update(spec, lat, with_next=0, with_finality=1, participation_rate=1.0),
        create_test_update(spec, sig, with_next=0, with_finality=1, participation_rate=0.8),
        create_test_update(spec, fin, with_next=0, with_finality=1, participation_rate=0.8),
        create_test_update(spec, lat, with_next=0, with_finality=1, participation_rate=0.8),
        # Updates without sync committee finality and also no `next_sync_committee`
        create_test_update(spec, att, with_next=0, with_finality=1, participation_rate=1.0),
        create_test_update(spec, att, with_next=0, with_finality=1, participation_rate=0.8),
        # Updates without indication of any finality nor `next_sync_committee`
        create_test_update(spec, sig, with_next=0, with_finality=0, participation_rate=1.0),
        create_test_update(spec, att, with_next=0, with_finality=0, participation_rate=1.0),
        create_test_update(spec, fin, with_next=0, with_finality=0, participation_rate=1.0),
        create_test_update(spec, lat, with_next=0, with_finality=0, participation_rate=1.0),
        create_test_update(spec, sig, with_next=0, with_finality=0, participation_rate=0.8),
        create_test_update(spec, att, with_next=0, with_finality=0, participation_rate=0.8),
        create_test_update(spec, fin, with_next=0, with_finality=0, participation_rate=0.8),
        create_test_update(spec, lat, with_next=0, with_finality=0, participation_rate=0.8),
        # Updates with low sync committee participation
        create_test_update(spec, fin, with_next=1, with_finality=1, participation_rate=0.4),
        create_test_update(spec, lat, with_next=1, with_finality=1, participation_rate=0.4),
        create_test_update(spec, att, with_next=1, with_finality=1, participation_rate=0.4),
        create_test_update(spec, att, with_next=1, with_finality=0, participation_rate=0.4),
        create_test_update(spec, fin, with_next=1, with_finality=0, participation_rate=0.4),
        create_test_update(spec, lat, with_next=1, with_finality=0, participation_rate=0.4),
        create_test_update(spec, sig, with_next=0, with_finality=1, participation_rate=0.4),
        create_test_update(spec, fin, with_next=0, with_finality=1, participation_rate=0.4),
        create_test_update(spec, lat, with_next=0, with_finality=1, participation_rate=0.4),
        create_test_update(spec, att, with_next=0, with_finality=1, participation_rate=0.4),
        create_test_update(spec, sig, with_next=0, with_finality=0, participation_rate=0.4),
        create_test_update(spec, att, with_next=0, with_finality=0, participation_rate=0.4),
        create_test_update(spec, fin, with_next=0, with_finality=0, participation_rate=0.4),
        create_test_update(spec, lat, with_next=0, with_finality=0, participation_rate=0.4),
        # Updates with very low sync committee participation
        create_test_update(spec, fin, with_next=1, with_finality=1, participation_rate=0.2),
        create_test_update(spec, lat, with_next=1, with_finality=1, participation_rate=0.2),
        create_test_update(spec, att, with_next=1, with_finality=1, participation_rate=0.2),
        create_test_update(spec, att, with_next=1, with_finality=0, participation_rate=0.2),
        create_test_update(spec, fin, with_next=1, with_finality=0, participation_rate=0.2),
        create_test_update(spec, lat, with_next=1, with_finality=0, participation_rate=0.2),
        create_test_update(spec, sig, with_next=0, with_finality=1, participation_rate=0.2),
        create_test_update(spec, fin, with_next=0, with_finality=1, participation_rate=0.2),
        create_test_update(spec, lat, with_next=0, with_finality=1, participation_rate=0.2),
        create_test_update(spec, att, with_next=0, with_finality=1, participation_rate=0.2),
        create_test_update(spec, sig, with_next=0, with_finality=0, participation_rate=0.2),
        create_test_update(spec, att, with_next=0, with_finality=0, participation_rate=0.2),
        create_test_update(spec, fin, with_next=0, with_finality=0, participation_rate=0.2),
        create_test_update(spec, lat, with_next=0, with_finality=0, participation_rate=0.2),
        # Test signature_slot tiebreaker: identical update but with later signature_slot
        create_test_update(
            spec,
            lat,
            with_next=0,
            with_finality=0,
            participation_rate=0.2,
            signature_slot=lat_attested_state.slot + 2,
        ),
    ]
    yield "updates", updates

    for i in range(len(updates) - 1):
        assert spec.is_better_update(updates[i], updates[i + 1])
