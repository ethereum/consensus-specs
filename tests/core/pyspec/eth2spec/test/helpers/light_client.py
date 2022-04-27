from copy import deepcopy

from eth2spec.test.helpers.state import (
    transition_to,
)
from eth2spec.test.helpers.sync_committee import (
    compute_aggregate_sync_committee_signature,
    compute_committee_indices,
)


def override_config_fork_epochs(spec, state):
    # Test framework adjusts state fork but leaves spec config constants inconsistent
    config_overrides = {}
    if state.fork.current_version == spec.config.GENESIS_FORK_VERSION:
        pass
    elif state.fork.current_version == spec.config.ALTAIR_FORK_VERSION:
        config_overrides['ALTAIR_FORK_EPOCH'] = spec.GENESIS_EPOCH
    elif state.fork.current_version == spec.config.BELLATRIX_FORK_VERSION:
        config_overrides['ALTAIR_FORK_EPOCH'] = spec.GENESIS_EPOCH
        config_overrides['BELLATRIX_FORK_EPOCH'] = spec.GENESIS_EPOCH
    elif state.fork.current_version == spec.config.CAPELLA_FORK_VERSION:
        config_overrides['ALTAIR_FORK_EPOCH'] = spec.GENESIS_EPOCH
        config_overrides['BELLATRIX_FORK_EPOCH'] = spec.GENESIS_EPOCH
        config_overrides['CAPELLA_FORK_EPOCH'] = spec.GENESIS_EPOCH
    elif state.fork.current_version == spec.config.SHARDING_FORK_VERSION:
        config_overrides['ALTAIR_FORK_EPOCH'] = spec.GENESIS_EPOCH
        config_overrides['BELLATRIX_FORK_EPOCH'] = spec.GENESIS_EPOCH
        config_overrides['CAPELLA_FORK_EPOCH'] = spec.GENESIS_EPOCH
        config_overrides['SHARDING_FORK_EPOCH'] = spec.GENESIS_EPOCH
    else:
        assert False

    tmp_config = deepcopy(spec.config._asdict())
    tmp_config.update(config_overrides)
    config_types = spec.Configuration.__annotations__
    test_config = {k: config_types[k](v) for k, v in tmp_config.items()}
    spec.config = spec.Configuration(**test_config)


def initialize_light_client_store(spec, state):
    return spec.LightClientStore(
        finalized_header=spec.BeaconBlockHeader(),
        current_sync_committee=state.current_sync_committee,
        next_sync_committee=state.next_sync_committee,
        best_valid_update=None,
        optimistic_header=spec.BeaconBlockHeader(),
        previous_max_active_participants=0,
        current_max_active_participants=0,
    )


def get_sync_aggregate(spec, state, block_header, signature_slot=None):
    # By default, the sync committee signs the previous slot
    if signature_slot is None:
        signature_slot = block_header.slot + 1

    # Ensure correct sync committee and fork version are selected
    signature_state = state.copy()
    transition_to(spec, signature_state, signature_slot)

    # Fetch sync committee
    committee_indices = compute_committee_indices(spec, signature_state)
    committee_size = len(committee_indices)

    # Compute sync aggregate
    sync_committee_bits = [True] * committee_size
    sync_committee_signature = compute_aggregate_sync_committee_signature(
        spec,
        signature_state,
        signature_slot,
        committee_indices,
        block_root=spec.Root(block_header.hash_tree_root()),
    )
    sync_aggregate = spec.SyncAggregate(
        sync_committee_bits=sync_committee_bits,
        sync_committee_signature=sync_committee_signature,
    )
    return sync_aggregate, signature_slot
