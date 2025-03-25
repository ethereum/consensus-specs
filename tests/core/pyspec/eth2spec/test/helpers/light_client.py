from eth2spec.test.helpers.constants import (
    CAPELLA,
    DENEB,
    ELECTRA,
)
from eth2spec.test.helpers.fork_transition import (
    transition_across_forks,
)
from eth2spec.test.helpers.forks import is_post_capella, is_post_deneb, is_post_electra
from eth2spec.test.helpers.sync_committee import (
    compute_aggregate_sync_committee_signature,
    compute_committee_indices,
)
from math import floor


def latest_finalized_root_gindex(spec):
    if hasattr(spec, "FINALIZED_ROOT_GINDEX_ELECTRA"):
        return spec.FINALIZED_ROOT_GINDEX_ELECTRA
    return spec.FINALIZED_ROOT_GINDEX


def latest_current_sync_committee_gindex(spec):
    if hasattr(spec, "CURRENT_SYNC_COMMITTEE_GINDEX_ELECTRA"):
        return spec.CURRENT_SYNC_COMMITTEE_GINDEX_ELECTRA
    return spec.CURRENT_SYNC_COMMITTEE_GINDEX


def latest_next_sync_committee_gindex(spec):
    if hasattr(spec, "NEXT_SYNC_COMMITTEE_GINDEX_ELECTRA"):
        return spec.NEXT_SYNC_COMMITTEE_GINDEX_ELECTRA
    return spec.NEXT_SYNC_COMMITTEE_GINDEX


def latest_normalize_merkle_branch(spec, branch, gindex):
    if hasattr(spec, "normalize_merkle_branch"):
        return spec.normalize_merkle_branch(branch, gindex)
    return branch


def compute_start_slot_at_sync_committee_period(spec, sync_committee_period):
    return spec.compute_start_slot_at_epoch(
        sync_committee_period * spec.EPOCHS_PER_SYNC_COMMITTEE_PERIOD
    )


def compute_start_slot_at_next_sync_committee_period(spec, state):
    sync_committee_period = spec.compute_sync_committee_period_at_slot(state.slot)
    return compute_start_slot_at_sync_committee_period(spec, sync_committee_period + 1)


def get_sync_aggregate(spec, state, num_participants=None, signature_slot=None, phases=None):
    # By default, the sync committee signs the previous slot
    if signature_slot is None:
        signature_slot = state.slot + 1
    assert signature_slot > state.slot

    # Ensure correct sync committee and fork version are selected
    signature_spec, signature_state, _ = transition_across_forks(
        spec, state, signature_slot, phases
    )

    # Fetch sync committee
    committee_indices = compute_committee_indices(signature_state)
    committee_size = len(committee_indices)

    # By default, use full participation
    if num_participants is None:
        num_participants = committee_size
    assert committee_size >= num_participants >= 0

    # Compute sync aggregate
    sync_committee_bits = [True] * num_participants + [False] * (committee_size - num_participants)
    sync_committee_signature = compute_aggregate_sync_committee_signature(
        signature_spec,
        signature_state,
        max(signature_slot, 1) - 1,
        committee_indices[:num_participants],
    )
    sync_aggregate = signature_spec.SyncAggregate(
        sync_committee_bits=sync_committee_bits,
        sync_committee_signature=sync_committee_signature,
    )
    return sync_aggregate, signature_slot


def create_update(
    spec,
    attested_state,
    attested_block,
    finalized_block,
    with_next,
    with_finality,
    participation_rate,
    signature_slot=None,
):
    num_participants = floor(spec.SYNC_COMMITTEE_SIZE * participation_rate)

    update = spec.LightClientUpdate()

    update.attested_header = spec.block_to_light_client_header(attested_block)

    if with_next:
        update.next_sync_committee = attested_state.next_sync_committee
        update.next_sync_committee_branch = spec.compute_merkle_proof(
            attested_state, latest_next_sync_committee_gindex(spec)
        )

    if with_finality:
        update.finalized_header = spec.block_to_light_client_header(finalized_block)
        update.finality_branch = spec.compute_merkle_proof(
            attested_state, latest_finalized_root_gindex(spec)
        )

    update.sync_aggregate, update.signature_slot = get_sync_aggregate(
        spec, attested_state, num_participants, signature_slot=signature_slot
    )

    return update


def needs_upgrade_to_capella(spec, new_spec):
    return is_post_capella(new_spec) and not is_post_capella(spec)


def needs_upgrade_to_deneb(spec, new_spec):
    return is_post_deneb(new_spec) and not is_post_deneb(spec)


def needs_upgrade_to_electra(spec, new_spec):
    return is_post_electra(new_spec) and not is_post_electra(spec)


def check_merkle_branch_equal(spec, new_spec, data, upgraded, gindex):
    if is_post_electra(new_spec):
        assert new_spec.normalize_merkle_branch(
            upgraded, gindex
        ) == new_spec.normalize_merkle_branch(data, gindex)
    else:
        assert upgraded == data


def check_lc_header_equal(spec, new_spec, data, upgraded):
    assert upgraded.beacon.slot == data.beacon.slot
    assert upgraded.beacon.hash_tree_root() == data.beacon.hash_tree_root()
    if is_post_capella(new_spec):
        if is_post_capella(spec):
            assert new_spec.get_lc_execution_root(upgraded) == spec.get_lc_execution_root(data)
        else:
            assert new_spec.get_lc_execution_root(upgraded) == new_spec.Root()


def upgrade_lc_header_to_new_spec(spec, new_spec, data, phases):
    upgraded = data

    if needs_upgrade_to_capella(spec, new_spec):
        upgraded = phases[CAPELLA].upgrade_lc_header_to_capella(upgraded)
        check_lc_header_equal(spec, new_spec, data, upgraded)

    if needs_upgrade_to_deneb(spec, new_spec):
        upgraded = phases[DENEB].upgrade_lc_header_to_deneb(upgraded)
        check_lc_header_equal(spec, new_spec, data, upgraded)

    if needs_upgrade_to_electra(spec, new_spec):
        upgraded = phases[ELECTRA].upgrade_lc_header_to_electra(upgraded)
        check_lc_header_equal(spec, new_spec, data, upgraded)

    return upgraded


def check_lc_bootstrap_equal(spec, new_spec, data, upgraded):
    check_lc_header_equal(spec, new_spec, data.header, upgraded.header)
    assert upgraded.current_sync_committee == data.current_sync_committee
    check_merkle_branch_equal(
        spec,
        new_spec,
        data.current_sync_committee_branch,
        upgraded.current_sync_committee_branch,
        latest_current_sync_committee_gindex(new_spec),
    )


def upgrade_lc_bootstrap_to_new_spec(spec, new_spec, data, phases):
    upgraded = data

    if needs_upgrade_to_capella(spec, new_spec):
        upgraded = phases[CAPELLA].upgrade_lc_bootstrap_to_capella(upgraded)
        check_lc_bootstrap_equal(spec, new_spec, data, upgraded)

    if needs_upgrade_to_deneb(spec, new_spec):
        upgraded = phases[DENEB].upgrade_lc_bootstrap_to_deneb(upgraded)
        check_lc_bootstrap_equal(spec, new_spec, data, upgraded)

    if needs_upgrade_to_electra(spec, new_spec):
        upgraded = phases[ELECTRA].upgrade_lc_bootstrap_to_electra(upgraded)
        check_lc_bootstrap_equal(spec, new_spec, data, upgraded)

    return upgraded


def check_lc_update_equal(spec, new_spec, data, upgraded):
    check_lc_header_equal(spec, new_spec, data.attested_header, upgraded.attested_header)
    assert upgraded.next_sync_committee == data.next_sync_committee
    check_merkle_branch_equal(
        spec,
        new_spec,
        data.next_sync_committee_branch,
        upgraded.next_sync_committee_branch,
        latest_next_sync_committee_gindex(new_spec),
    )
    check_lc_header_equal(spec, new_spec, data.finalized_header, upgraded.finalized_header)
    check_merkle_branch_equal(
        spec,
        new_spec,
        data.finality_branch,
        upgraded.finality_branch,
        latest_finalized_root_gindex(new_spec),
    )
    assert upgraded.sync_aggregate == data.sync_aggregate
    assert upgraded.signature_slot == data.signature_slot


def upgrade_lc_update_to_new_spec(spec, new_spec, data, phases):
    upgraded = data

    if needs_upgrade_to_capella(spec, new_spec):
        upgraded = phases[CAPELLA].upgrade_lc_update_to_capella(upgraded)
        check_lc_update_equal(spec, new_spec, data, upgraded)

    if needs_upgrade_to_deneb(spec, new_spec):
        upgraded = phases[DENEB].upgrade_lc_update_to_deneb(upgraded)
        check_lc_update_equal(spec, new_spec, data, upgraded)

    if needs_upgrade_to_electra(spec, new_spec):
        upgraded = phases[ELECTRA].upgrade_lc_update_to_electra(upgraded)
        check_lc_update_equal(spec, new_spec, data, upgraded)

    return upgraded


def check_lc_finality_update_equal(spec, new_spec, data, upgraded):
    check_lc_header_equal(spec, new_spec, data.attested_header, upgraded.attested_header)
    check_lc_header_equal(spec, new_spec, data.finalized_header, upgraded.finalized_header)
    check_merkle_branch_equal(
        spec,
        new_spec,
        data.finality_branch,
        upgraded.finality_branch,
        latest_finalized_root_gindex(new_spec),
    )
    assert upgraded.sync_aggregate == data.sync_aggregate
    assert upgraded.signature_slot == data.signature_slot


def upgrade_lc_finality_update_to_new_spec(spec, new_spec, data, phases):
    upgraded = data

    if needs_upgrade_to_capella(spec, new_spec):
        upgraded = phases[CAPELLA].upgrade_lc_finality_update_to_capella(upgraded)
        check_lc_finality_update_equal(spec, new_spec, data, upgraded)

    if needs_upgrade_to_deneb(spec, new_spec):
        upgraded = phases[DENEB].upgrade_lc_finality_update_to_deneb(upgraded)
        check_lc_finality_update_equal(spec, new_spec, data, upgraded)

    if needs_upgrade_to_electra(spec, new_spec):
        upgraded = phases[ELECTRA].upgrade_lc_finality_update_to_electra(upgraded)
        check_lc_finality_update_equal(spec, new_spec, data, upgraded)

    return upgraded


def check_lc_store_equal(spec, new_spec, data, upgraded):
    check_lc_header_equal(spec, new_spec, data.finalized_header, upgraded.finalized_header)
    assert upgraded.current_sync_committee == data.current_sync_committee
    assert upgraded.next_sync_committee == data.next_sync_committee
    if upgraded.best_valid_update is None:
        assert data.best_valid_update is None
    else:
        check_lc_update_equal(spec, new_spec, data.best_valid_update, upgraded.best_valid_update)
    check_lc_header_equal(spec, new_spec, data.optimistic_header, upgraded.optimistic_header)
    assert upgraded.previous_max_active_participants == data.previous_max_active_participants
    assert upgraded.current_max_active_participants == data.current_max_active_participants


def upgrade_lc_store_to_new_spec(spec, new_spec, data, phases):
    upgraded = data

    if needs_upgrade_to_capella(spec, new_spec):
        upgraded = phases[CAPELLA].upgrade_lc_store_to_capella(upgraded)
        check_lc_store_equal(spec, new_spec, data, upgraded)

    if needs_upgrade_to_deneb(spec, new_spec):
        upgraded = phases[DENEB].upgrade_lc_store_to_deneb(upgraded)
        check_lc_store_equal(spec, new_spec, data, upgraded)

    if needs_upgrade_to_electra(spec, new_spec):
        upgraded = phases[ELECTRA].upgrade_lc_store_to_electra(upgraded)
        check_lc_store_equal(spec, new_spec, data, upgraded)

    return upgraded
