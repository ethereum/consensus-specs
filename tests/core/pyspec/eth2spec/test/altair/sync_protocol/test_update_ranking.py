from eth2spec.test.context import (
    spec_state_test,
    with_presets,
    with_altair_and_later,
)
from eth2spec.test.helpers.attestations import (
    next_slots_with_attestations,
    state_transition_with_full_block,
)
from eth2spec.test.helpers.constants import MINIMAL
from eth2spec.test.helpers.light_client import (
    get_sync_aggregate,
    signed_block_to_header,
)
from eth2spec.test.helpers.state import (
    next_slots,
)
from eth2spec.test.helpers.merkle import build_proof
from math import floor


def create_update(spec, test, with_next_sync_committee, with_finality, participation_rate):
    attested_state, attested_block, finalized_block = test
    num_participants = floor(spec.SYNC_COMMITTEE_SIZE * participation_rate)

    attested_header = signed_block_to_header(spec, attested_block)

    if with_next_sync_committee:
        next_sync_committee = attested_state.next_sync_committee
        next_sync_committee_branch = build_proof(attested_state.get_backing(), spec.NEXT_SYNC_COMMITTEE_INDEX)
    else:
        next_sync_committee = spec.SyncCommittee()
        next_sync_committee_branch = [spec.Bytes32() for _ in range(spec.floorlog2(spec.NEXT_SYNC_COMMITTEE_INDEX))]

    if with_finality:
        finalized_header = signed_block_to_header(spec, finalized_block)
        finality_branch = build_proof(attested_state.get_backing(), spec.FINALIZED_ROOT_INDEX)
    else:
        finalized_header = spec.BeaconBlockHeader()
        finality_branch = [spec.Bytes32() for _ in range(spec.floorlog2(spec.FINALIZED_ROOT_INDEX))]

    sync_aggregate, signature_slot = get_sync_aggregate(spec, attested_state, num_participants)

    return spec.LightClientUpdate(
        attested_header=attested_header,
        next_sync_committee=next_sync_committee,
        next_sync_committee_branch=next_sync_committee_branch,
        finalized_header=finalized_header,
        finality_branch=finality_branch,
        sync_aggregate=sync_aggregate,
        signature_slot=signature_slot,
    )


@with_altair_and_later
@spec_state_test
@with_presets([MINIMAL], reason="too slow")
def test_update_ranking(spec, state):
    # Set up blocks and states:
    # - `sig_finalized` / `sig_attested` --> Only signature in next sync committee period
    # - `att_finalized` / `att_attested` --> Attested header also in next sync committee period
    # - `fin_finalized` / `fin_attested` --> Finalized header also in next sync committee period
    # - `lat_finalized` / `lat_attested` --> Like `fin`, but at a later `attested_header.slot`
    next_slots(spec, state, spec.compute_start_slot_at_epoch(spec.EPOCHS_PER_SYNC_COMMITTEE_PERIOD - 3) - 1)
    sig_finalized_block = state_transition_with_full_block(spec, state, True, True)
    _, _, state = next_slots_with_attestations(spec, state, spec.SLOTS_PER_EPOCH - 1, True, True)
    att_finalized_block = state_transition_with_full_block(spec, state, True, True)
    _, _, state = next_slots_with_attestations(spec, state, 2 * spec.SLOTS_PER_EPOCH - 2, True, True)
    sig_attested_block = state_transition_with_full_block(spec, state, True, True)
    sig_attested_state = state.copy()
    att_attested_block = state_transition_with_full_block(spec, state, True, True)
    att_attested_state = state.copy()
    fin_finalized_block = att_attested_block
    _, _, state = next_slots_with_attestations(spec, state, 2 * spec.SLOTS_PER_EPOCH - 1, True, True)
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
        create_update(spec, fin, with_next_sync_committee=1, with_finality=1, participation_rate=1.0),
        create_update(spec, lat, with_next_sync_committee=1, with_finality=1, participation_rate=1.0),
        create_update(spec, fin, with_next_sync_committee=1, with_finality=1, participation_rate=0.8),
        create_update(spec, lat, with_next_sync_committee=1, with_finality=1, participation_rate=0.8),

        # Updates without sync committee finality
        create_update(spec, att, with_next_sync_committee=1, with_finality=1, participation_rate=1.0),
        create_update(spec, att, with_next_sync_committee=1, with_finality=1, participation_rate=0.8),

        # Updates without indication of any finality
        create_update(spec, att, with_next_sync_committee=1, with_finality=0, participation_rate=1.0),
        create_update(spec, fin, with_next_sync_committee=1, with_finality=0, participation_rate=1.0),
        create_update(spec, lat, with_next_sync_committee=1, with_finality=0, participation_rate=1.0),
        create_update(spec, att, with_next_sync_committee=1, with_finality=0, participation_rate=0.8),
        create_update(spec, fin, with_next_sync_committee=1, with_finality=0, participation_rate=0.8),
        create_update(spec, lat, with_next_sync_committee=1, with_finality=0, participation_rate=0.8),

        # Updates with sync committee finality but no `next_sync_committee`
        create_update(spec, sig, with_next_sync_committee=0, with_finality=1, participation_rate=1.0),
        create_update(spec, fin, with_next_sync_committee=0, with_finality=1, participation_rate=1.0),
        create_update(spec, lat, with_next_sync_committee=0, with_finality=1, participation_rate=1.0),
        create_update(spec, sig, with_next_sync_committee=0, with_finality=1, participation_rate=0.8),
        create_update(spec, fin, with_next_sync_committee=0, with_finality=1, participation_rate=0.8),
        create_update(spec, lat, with_next_sync_committee=0, with_finality=1, participation_rate=0.8),

        # Updates without sync committee finality and also no `next_sync_committee`
        create_update(spec, att, with_next_sync_committee=0, with_finality=1, participation_rate=1.0),
        create_update(spec, att, with_next_sync_committee=0, with_finality=1, participation_rate=0.8),

        # Updates without indication of any finality nor `next_sync_committee`
        create_update(spec, sig, with_next_sync_committee=0, with_finality=0, participation_rate=1.0),
        create_update(spec, att, with_next_sync_committee=0, with_finality=0, participation_rate=1.0),
        create_update(spec, fin, with_next_sync_committee=0, with_finality=0, participation_rate=1.0),
        create_update(spec, lat, with_next_sync_committee=0, with_finality=0, participation_rate=1.0),
        create_update(spec, sig, with_next_sync_committee=0, with_finality=0, participation_rate=0.8),
        create_update(spec, att, with_next_sync_committee=0, with_finality=0, participation_rate=0.8),
        create_update(spec, fin, with_next_sync_committee=0, with_finality=0, participation_rate=0.8),
        create_update(spec, lat, with_next_sync_committee=0, with_finality=0, participation_rate=0.8),

        # Updates with low sync committee participation
        create_update(spec, fin, with_next_sync_committee=1, with_finality=1, participation_rate=0.4),
        create_update(spec, lat, with_next_sync_committee=1, with_finality=1, participation_rate=0.4),
        create_update(spec, att, with_next_sync_committee=1, with_finality=1, participation_rate=0.4),
        create_update(spec, att, with_next_sync_committee=1, with_finality=0, participation_rate=0.4),
        create_update(spec, fin, with_next_sync_committee=1, with_finality=0, participation_rate=0.4),
        create_update(spec, lat, with_next_sync_committee=1, with_finality=0, participation_rate=0.4),
        create_update(spec, sig, with_next_sync_committee=0, with_finality=1, participation_rate=0.4),
        create_update(spec, fin, with_next_sync_committee=0, with_finality=1, participation_rate=0.4),
        create_update(spec, lat, with_next_sync_committee=0, with_finality=1, participation_rate=0.4),
        create_update(spec, att, with_next_sync_committee=0, with_finality=1, participation_rate=0.4),
        create_update(spec, sig, with_next_sync_committee=0, with_finality=0, participation_rate=0.4),
        create_update(spec, att, with_next_sync_committee=0, with_finality=0, participation_rate=0.4),
        create_update(spec, fin, with_next_sync_committee=0, with_finality=0, participation_rate=0.4),
        create_update(spec, lat, with_next_sync_committee=0, with_finality=0, participation_rate=0.4),

        # Updates with very low sync committee participation
        create_update(spec, fin, with_next_sync_committee=1, with_finality=1, participation_rate=0.2),
        create_update(spec, lat, with_next_sync_committee=1, with_finality=1, participation_rate=0.2),
        create_update(spec, att, with_next_sync_committee=1, with_finality=1, participation_rate=0.2),
        create_update(spec, att, with_next_sync_committee=1, with_finality=0, participation_rate=0.2),
        create_update(spec, fin, with_next_sync_committee=1, with_finality=0, participation_rate=0.2),
        create_update(spec, lat, with_next_sync_committee=1, with_finality=0, participation_rate=0.2),
        create_update(spec, sig, with_next_sync_committee=0, with_finality=1, participation_rate=0.2),
        create_update(spec, fin, with_next_sync_committee=0, with_finality=1, participation_rate=0.2),
        create_update(spec, lat, with_next_sync_committee=0, with_finality=1, participation_rate=0.2),
        create_update(spec, att, with_next_sync_committee=0, with_finality=1, participation_rate=0.2),
        create_update(spec, sig, with_next_sync_committee=0, with_finality=0, participation_rate=0.2),
        create_update(spec, att, with_next_sync_committee=0, with_finality=0, participation_rate=0.2),
        create_update(spec, fin, with_next_sync_committee=0, with_finality=0, participation_rate=0.2),
        create_update(spec, lat, with_next_sync_committee=0, with_finality=0, participation_rate=0.2),
    ]
    yield "updates", updates

    for i in range(len(updates) - 1):
        assert spec.is_better_update(updates[i], updates[i + 1])
