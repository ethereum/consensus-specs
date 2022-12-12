from typing import (Any, Dict, List)

from eth_utils import encode_hex
from eth2spec.test.context import (
    spec_state_test_with_matching_config,
    spec_test,
    with_config_overrides,
    with_matching_spec_config,
    with_phases,
    with_presets,
    with_state,
    with_altair_and_later,
)
from eth2spec.test.helpers.attestations import (
    next_slots_with_attestations,
    state_transition_with_full_block,
)
from eth2spec.test.helpers.constants import (
    PHASE0, ALTAIR, BELLATRIX, CAPELLA, EIP4844,
    MINIMAL,
    ALL_PHASES,
)
from eth2spec.test.helpers.fork_transition import (
    do_fork,
)
from eth2spec.test.helpers.forks import (
    is_post_capella, is_post_eip4844,
    is_post_fork,
)
from eth2spec.test.helpers.light_client import (
    get_sync_aggregate,
)
from eth2spec.test.helpers.state import (
    next_slots,
    transition_to,
)


def get_spec_for_fork_version(spec, fork_version, phases):
    if phases is None:
        return spec
    for fork in [fork for fork in ALL_PHASES if is_post_fork(spec.fork, fork)]:
        if fork == PHASE0:
            fork_version_field = 'GENESIS_FORK_VERSION'
        else:
            fork_version_field = fork.upper() + '_FORK_VERSION'
        if fork_version == getattr(spec.config, fork_version_field):
            return phases[fork]
    raise ValueError("Unknown fork version %s" % fork_version)


def needs_upgrade_to_capella(d_spec, s_spec):
    return is_post_capella(s_spec) and not is_post_capella(d_spec)


def needs_upgrade_to_eip4844(d_spec, s_spec):
    return is_post_eip4844(s_spec) and not is_post_eip4844(d_spec)


def check_lc_header_equal(d_spec, s_spec, data, upgraded):
    assert s_spec.get_lc_beacon_slot(upgraded) == d_spec.get_lc_beacon_slot(data)
    assert s_spec.get_lc_beacon_root(upgraded) == d_spec.get_lc_beacon_root(data)
    if is_post_capella(s_spec):
        if is_post_capella(d_spec):
            assert s_spec.get_lc_execution_root(upgraded) == d_spec.get_lc_execution_root(data)
        else:
            assert s_spec.get_lc_execution_root(upgraded) == s_spec.Root()


def check_lc_bootstrap_equal(d_spec, s_spec, data, upgraded):
    check_lc_header_equal(d_spec, s_spec, data.header, upgraded.header)
    assert upgraded.current_sync_committee == data.current_sync_committee
    assert upgraded.current_sync_committee_branch == data.current_sync_committee_branch


def upgrade_lc_bootstrap_to_store(d_spec, s_spec, data):
    upgraded = data

    if needs_upgrade_to_capella(d_spec, s_spec):
        upgraded = s_spec.upgrade_lc_bootstrap_to_capella(upgraded)
        check_lc_bootstrap_equal(d_spec, s_spec, data, upgraded)

    if needs_upgrade_to_eip4844(d_spec, s_spec):
        upgraded = s_spec.upgrade_lc_bootstrap_to_eip4844(upgraded)
        check_lc_bootstrap_equal(d_spec, s_spec, data, upgraded)

    return upgraded


def check_lc_update_equal(d_spec, s_spec, data, upgraded):
    check_lc_header_equal(d_spec, s_spec, data.attested_header, upgraded.attested_header)
    assert upgraded.next_sync_committee == data.next_sync_committee
    assert upgraded.next_sync_committee_branch == data.next_sync_committee_branch
    check_lc_header_equal(d_spec, s_spec, data.finalized_header, upgraded.finalized_header)
    assert upgraded.sync_aggregate == data.sync_aggregate
    assert upgraded.signature_slot == data.signature_slot


def upgrade_lc_update_to_store(d_spec, s_spec, data):
    upgraded = data

    if needs_upgrade_to_capella(d_spec, s_spec):
        upgraded = s_spec.upgrade_lc_update_to_capella(upgraded)
        check_lc_update_equal(d_spec, s_spec, data, upgraded)

    if needs_upgrade_to_eip4844(d_spec, s_spec):
        upgraded = s_spec.upgrade_lc_update_to_eip4844(upgraded)
        check_lc_update_equal(d_spec, s_spec, data, upgraded)

    return upgraded


def check_lc_store_equal(d_spec, s_spec, data, upgraded):
    check_lc_header_equal(d_spec, s_spec, data.finalized_header, upgraded.finalized_header)
    assert upgraded.current_sync_committee == data.current_sync_committee
    assert upgraded.next_sync_committee == data.next_sync_committee
    if upgraded.best_valid_update is None:
        assert data.best_valid_update is None
    else:
        check_lc_update_equal(d_spec, s_spec, data.best_valid_update, upgraded.best_valid_update)
    check_lc_header_equal(d_spec, s_spec, data.optimistic_header, upgraded.optimistic_header)
    assert upgraded.previous_max_active_participants == data.previous_max_active_participants
    assert upgraded.current_max_active_participants == data.current_max_active_participants


def upgrade_lc_store_to_new_spec(d_spec, s_spec, data):
    upgraded = data

    if needs_upgrade_to_capella(d_spec, s_spec):
        upgraded = s_spec.upgrade_lc_store_to_capella(upgraded)
        check_lc_store_equal(d_spec, s_spec, data, upgraded)

    if needs_upgrade_to_eip4844(d_spec, s_spec):
        upgraded = s_spec.upgrade_lc_store_to_eip4844(upgraded)
        check_lc_store_equal(d_spec, s_spec, data, upgraded)

    return upgraded


class LightClientSyncTest(object):
    steps: List[Dict[str, Any]]
    genesis_validators_root: Any
    s_spec: Any
    store: Any


def get_store_fork_version(s_spec):
    if is_post_eip4844(s_spec):
        return s_spec.config.EIP4844_FORK_VERSION
    if is_post_capella(s_spec):
        return s_spec.config.CAPELLA_FORK_VERSION
    return s_spec.config.ALTAIR_FORK_VERSION


def setup_test(spec, state, s_spec=None, phases=None):
    test = LightClientSyncTest()
    test.steps = []

    if s_spec is None:
        s_spec = spec
    test.s_spec = s_spec

    yield "genesis_validators_root", "meta", "0x" + state.genesis_validators_root.hex()
    test.genesis_validators_root = state.genesis_validators_root

    next_slots(spec, state, spec.SLOTS_PER_EPOCH * 2 - 1)
    trusted_block = state_transition_with_full_block(spec, state, True, True)
    trusted_block_root = trusted_block.message.hash_tree_root()
    yield "trusted_block_root", "meta", "0x" + trusted_block_root.hex()

    data_fork_version = spec.compute_fork_version(spec.compute_epoch_at_slot(trusted_block.message.slot))
    data_fork_digest = spec.compute_fork_digest(data_fork_version, test.genesis_validators_root)
    d_spec = get_spec_for_fork_version(spec, data_fork_version, phases)
    data = d_spec.create_light_client_bootstrap(state, trusted_block)
    yield "bootstrap_fork_digest", "meta", encode_hex(data_fork_digest)
    yield "bootstrap", data

    upgraded = upgrade_lc_bootstrap_to_store(d_spec, test.s_spec, data)
    test.store = test.s_spec.initialize_light_client_store(trusted_block_root, upgraded)
    store_fork_version = get_store_fork_version(test.s_spec)
    store_fork_digest = test.s_spec.compute_fork_digest(store_fork_version, test.genesis_validators_root)
    yield "store_fork_digest", "meta", encode_hex(store_fork_digest)

    return test


def finish_test(test):
    yield "steps", test.steps


def get_update_file_name(d_spec, update):
    if d_spec.is_sync_committee_update(update):
        suffix1 = "s"
    else:
        suffix1 = "x"
    if d_spec.is_finality_update(update):
        suffix2 = "f"
    else:
        suffix2 = "x"
    return f"update_{encode_hex(d_spec.get_lc_beacon_root(update.attested_header))}_{suffix1}{suffix2}"


def get_checks(s_spec, store):
    if is_post_capella(s_spec):
        return {
            "finalized_header": {
                'slot': int(s_spec.get_lc_beacon_slot(store.finalized_header)),
                'beacon_root': encode_hex(s_spec.get_lc_beacon_root(store.finalized_header)),
                'execution_root': encode_hex(s_spec.get_lc_execution_root(store.finalized_header)),
            },
            "optimistic_header": {
                'slot': int(s_spec.get_lc_beacon_slot(store.optimistic_header)),
                'beacon_root': encode_hex(s_spec.get_lc_beacon_root(store.optimistic_header)),
                'execution_root': encode_hex(s_spec.get_lc_execution_root(store.optimistic_header)),
            },
        }

    return {
        "finalized_header": {
            'slot': int(s_spec.get_lc_beacon_slot(store.finalized_header)),
            'beacon_root': encode_hex(s_spec.get_lc_beacon_root(store.finalized_header)),
        },
        "optimistic_header": {
            'slot': int(s_spec.get_lc_beacon_slot(store.optimistic_header)),
            'beacon_root': encode_hex(s_spec.get_lc_beacon_root(store.optimistic_header)),
        },
    }


def emit_force_update(test, spec, state):
    current_slot = state.slot
    test.s_spec.process_light_client_store_force_update(test.store, current_slot)

    yield from []  # Consistently enable `yield from` syntax in calling tests
    test.steps.append({
        "force_update": {
            "current_slot": int(current_slot),
            "checks": get_checks(test.s_spec, test.store),
        }
    })


def emit_update(test, spec, state, block, attested_state, attested_block, finalized_block, with_next=True, phases=None):
    data_fork_version = spec.compute_fork_version(spec.compute_epoch_at_slot(attested_block.message.slot))
    data_fork_digest = spec.compute_fork_digest(data_fork_version, test.genesis_validators_root)
    d_spec = get_spec_for_fork_version(spec, data_fork_version, phases)
    data = d_spec.create_light_client_update(state, block, attested_state, attested_block, finalized_block)
    if not with_next:
        data.next_sync_committee = spec.SyncCommittee()
        data.next_sync_committee_branch = \
            [spec.Bytes32() for _ in range(spec.floorlog2(spec.NEXT_SYNC_COMMITTEE_INDEX))]
    current_slot = state.slot

    upgraded = upgrade_lc_update_to_store(d_spec, test.s_spec, data)
    test.s_spec.process_light_client_update(test.store, upgraded, current_slot, test.genesis_validators_root)

    yield get_update_file_name(d_spec, data), data
    test.steps.append({
        "process_update": {
            "update_fork_digest": encode_hex(data_fork_digest),
            "update": get_update_file_name(d_spec, data),
            "current_slot": int(current_slot),
            "checks": get_checks(test.s_spec, test.store),
        }
    })
    return upgraded


def emit_upgrade_store(test, new_s_spec, phases=None):
    test.store = upgrade_lc_store_to_new_spec(test.s_spec, new_s_spec, test.store)
    test.s_spec = new_s_spec
    store_fork_version = get_store_fork_version(test.s_spec)
    store_fork_digest = test.s_spec.compute_fork_digest(store_fork_version, test.genesis_validators_root)

    yield from []  # Consistently enable `yield from` syntax in calling tests
    test.steps.append({
        "process_upgrade_store": {
            "store_fork_digest": encode_hex(store_fork_digest),
            "checks": get_checks(test.s_spec, test.store),
        }
    })


def compute_start_slot_at_sync_committee_period(spec, sync_committee_period):
    return spec.compute_start_slot_at_epoch(sync_committee_period * spec.EPOCHS_PER_SYNC_COMMITTEE_PERIOD)


def compute_start_slot_at_next_sync_committee_period(spec, state):
    sync_committee_period = spec.compute_sync_committee_period_at_slot(state.slot)
    return compute_start_slot_at_sync_committee_period(spec, sync_committee_period + 1)


@with_altair_and_later
@spec_state_test_with_matching_config
@with_presets([MINIMAL], reason="too slow")
def test_light_client_sync(spec, state):
    # Start test
    test = yield from setup_test(spec, state)

    # Initial `LightClientUpdate`, populating `store.next_sync_committee`
    # ```
    #                                                                   |
    #    +-----------+                   +----------+     +-----------+ |
    #    | finalized | <-- (2 epochs) -- | attested | <-- | signature | |
    #    +-----------+                   +----------+     +-----------+ |
    #                                                                   |
    #                                                                   |
    #                                                            sync committee
    #                                                            period boundary
    # ```
    next_slots(spec, state, spec.SLOTS_PER_EPOCH - 1)
    finalized_block = state_transition_with_full_block(spec, state, True, True)
    finalized_state = state.copy()
    _, _, state = next_slots_with_attestations(spec, state, 2 * spec.SLOTS_PER_EPOCH - 1, True, True)
    attested_block = state_transition_with_full_block(spec, state, True, True)
    attested_state = state.copy()
    sync_aggregate, _ = get_sync_aggregate(spec, state)
    block = state_transition_with_full_block(spec, state, True, True, sync_aggregate=sync_aggregate)
    yield from emit_update(test, spec, state, block, attested_state, attested_block, finalized_block)
    assert test.s_spec.get_lc_beacon_slot(test.store.finalized_header) == finalized_state.slot
    assert test.store.next_sync_committee == finalized_state.next_sync_committee
    assert test.store.best_valid_update is None
    assert test.s_spec.get_lc_beacon_slot(test.store.optimistic_header) == attested_state.slot

    # Advance to next sync committee period
    # ```
    #                                                                   |
    #    +-----------+                   +----------+     +-----------+ |
    #    | finalized | <-- (2 epochs) -- | attested | <-- | signature | |
    #    +-----------+                   +----------+     +-----------+ |
    #                                                                   |
    #                                                                   |
    #                                                            sync committee
    #                                                            period boundary
    # ```
    transition_to(spec, state, compute_start_slot_at_next_sync_committee_period(spec, state))
    next_slots(spec, state, spec.SLOTS_PER_EPOCH - 1)
    finalized_block = state_transition_with_full_block(spec, state, True, True)
    finalized_state = state.copy()
    _, _, state = next_slots_with_attestations(spec, state, 2 * spec.SLOTS_PER_EPOCH - 1, True, True)
    attested_block = state_transition_with_full_block(spec, state, True, True)
    attested_state = state.copy()
    sync_aggregate, _ = get_sync_aggregate(spec, state)
    block = state_transition_with_full_block(spec, state, True, True, sync_aggregate=sync_aggregate)
    yield from emit_update(test, spec, state, block, attested_state, attested_block, finalized_block)
    assert test.s_spec.get_lc_beacon_slot(test.store.finalized_header) == finalized_state.slot
    assert test.store.next_sync_committee == finalized_state.next_sync_committee
    assert test.store.best_valid_update is None
    assert test.s_spec.get_lc_beacon_slot(test.store.optimistic_header) == attested_state.slot

    # Edge case: Signature in next period
    # ```
    #                                                  |
    #    +-----------+                   +----------+  |  +-----------+
    #    | finalized | <-- (2 epochs) -- | attested | <-- | signature |
    #    +-----------+                   +----------+  |  +-----------+
    #                                                  |
    #                                                  |
    #                                           sync committee
    #                                           period boundary
    # ```
    next_slots(spec, state, spec.SLOTS_PER_EPOCH - 2)
    finalized_block = state_transition_with_full_block(spec, state, True, True)
    finalized_state = state.copy()
    _, _, state = next_slots_with_attestations(spec, state, 2 * spec.SLOTS_PER_EPOCH - 1, True, True)
    attested_block = state_transition_with_full_block(spec, state, True, True)
    attested_state = state.copy()
    transition_to(spec, state, compute_start_slot_at_next_sync_committee_period(spec, state))
    sync_aggregate, _ = get_sync_aggregate(spec, state)
    block = state_transition_with_full_block(spec, state, True, True, sync_aggregate=sync_aggregate)
    yield from emit_update(test, spec, state, block, attested_state, attested_block, finalized_block)
    assert test.s_spec.get_lc_beacon_slot(test.store.finalized_header) == finalized_state.slot
    assert test.store.next_sync_committee == finalized_state.next_sync_committee
    assert test.store.best_valid_update is None
    assert test.s_spec.get_lc_beacon_slot(test.store.optimistic_header) == attested_state.slot

    # Edge case: Finalized header not included
    # ```
    #                          |
    #    + - - - - - +         |         +----------+     +-----------+
    #    ¦ finalized ¦ <-- (2 epochs) -- | attested | <-- | signature |
    #    + - - - - - +         |         +----------+     +-----------+
    #                          |
    #                          |
    #                   sync committee
    #                   period boundary
    # ```
    attested_block = block.copy()
    attested_state = state.copy()
    sync_aggregate, _ = get_sync_aggregate(spec, state)
    block = state_transition_with_full_block(spec, state, True, True, sync_aggregate=sync_aggregate)
    update = yield from emit_update(test, spec, state, block, attested_state, attested_block, finalized_block=None)
    assert test.s_spec.get_lc_beacon_slot(test.store.finalized_header) == finalized_state.slot
    assert test.store.next_sync_committee == finalized_state.next_sync_committee
    assert test.store.best_valid_update == update
    assert test.s_spec.get_lc_beacon_slot(test.store.optimistic_header) == attested_state.slot

    # Non-finalized case: Attested `next_sync_committee` is not finalized
    # ```
    #                          |
    #    +-----------+         |         +----------+     +-----------+
    #    | finalized | <-- (2 epochs) -- | attested | <-- | signature |
    #    +-----------+         |         +----------+     +-----------+
    #                          |
    #                          |
    #                   sync committee
    #                   period boundary
    # ```
    attested_block = block.copy()
    attested_state = state.copy()
    store_state = attested_state.copy()
    sync_aggregate, _ = get_sync_aggregate(spec, state)
    block = state_transition_with_full_block(spec, state, True, True, sync_aggregate=sync_aggregate)
    update = yield from emit_update(test, spec, state, block, attested_state, attested_block, finalized_block)
    assert test.s_spec.get_lc_beacon_slot(test.store.finalized_header) == finalized_state.slot
    assert test.store.next_sync_committee == finalized_state.next_sync_committee
    assert test.store.best_valid_update == update
    assert test.s_spec.get_lc_beacon_slot(test.store.optimistic_header) == attested_state.slot

    # Force-update using timeout
    # ```
    #                          |
    #    +-----------+         |         +----------+
    #    | finalized | <-- (2 epochs) -- | attested |
    #    +-----------+         |         +----------+
    #                          |            ^
    #                          |             \
    #                   sync committee        `--- store.finalized_header
    #                   period boundary
    # ```
    attested_block = block.copy()
    attested_state = state.copy()
    next_slots(spec, state, spec.UPDATE_TIMEOUT - 1)
    yield from emit_force_update(test, spec, state)
    assert spec.get_lc_beacon_slot(test.store.finalized_header) == store_state.slot
    assert test.store.next_sync_committee == store_state.next_sync_committee
    assert test.store.best_valid_update is None
    assert spec.get_lc_beacon_slot(test.store.optimistic_header) == store_state.slot

    # Edge case: Finalized header not included, after force-update
    # ```
    #                          |                                |
    #    + - - - - - +         |         +--+     +----------+  |  +-----------+
    #    ¦ finalized ¦ <-- (2 epochs) -- |  | <-- | attested | <-- | signature |
    #    + - - - - - +         |         +--+     +----------+  |  +-----------+
    #                          |          /                     |
    #                          |  store.fin                     |
    #                   sync committee                   sync committee
    #                   period boundary                  period boundary
    # ```
    sync_aggregate, _ = get_sync_aggregate(spec, state)
    block = state_transition_with_full_block(spec, state, True, True, sync_aggregate=sync_aggregate)
    update = yield from emit_update(test, spec, state, block, attested_state, attested_block, finalized_block=None)
    assert spec.get_lc_beacon_slot(test.store.finalized_header) == store_state.slot
    assert test.store.next_sync_committee == store_state.next_sync_committee
    assert test.store.best_valid_update == update
    assert test.s_spec.get_lc_beacon_slot(test.store.optimistic_header) == attested_state.slot

    # Edge case: Finalized header older than store
    # ```
    #                          |               |
    #    +-----------+         |         +--+  |  +----------+     +-----------+
    #    | finalized | <-- (2 epochs) -- |  | <-- | attested | <-- | signature |
    #    +-----------+         |         +--+  |  +----------+     +-----------+
    #                          |          /    |
    #                          |  store.fin    |
    #                   sync committee       sync committee
    #                   period boundary      period boundary
    # ```
    attested_block = block.copy()
    attested_state = state.copy()
    sync_aggregate, _ = get_sync_aggregate(spec, state)
    block = state_transition_with_full_block(spec, state, True, True, sync_aggregate=sync_aggregate)
    update = yield from emit_update(test, spec, state, block, attested_state, attested_block, finalized_block)
    assert spec.get_lc_beacon_slot(test.store.finalized_header) == store_state.slot
    assert test.store.next_sync_committee == store_state.next_sync_committee
    assert test.store.best_valid_update == update
    assert test.s_spec.get_lc_beacon_slot(test.store.optimistic_header) == attested_state.slot
    yield from emit_force_update(test, spec, state)
    assert spec.get_lc_beacon_slot(test.store.finalized_header) == attested_state.slot
    assert test.store.next_sync_committee == attested_state.next_sync_committee
    assert test.store.best_valid_update is None
    assert test.s_spec.get_lc_beacon_slot(test.store.optimistic_header) == attested_state.slot

    # Advance to next sync committee period
    # ```
    #                                                                   |
    #    +-----------+                   +----------+     +-----------+ |
    #    | finalized | <-- (2 epochs) -- | attested | <-- | signature | |
    #    +-----------+                   +----------+     +-----------+ |
    #                                                                   |
    #                                                                   |
    #                                                            sync committee
    #                                                            period boundary
    # ```
    transition_to(spec, state, compute_start_slot_at_next_sync_committee_period(spec, state))
    next_slots(spec, state, spec.SLOTS_PER_EPOCH - 1)
    finalized_block = state_transition_with_full_block(spec, state, True, True)
    finalized_state = state.copy()
    _, _, state = next_slots_with_attestations(spec, state, 2 * spec.SLOTS_PER_EPOCH - 1, True, True)
    attested_block = state_transition_with_full_block(spec, state, True, True)
    attested_state = state.copy()
    sync_aggregate, _ = get_sync_aggregate(spec, state)
    block = state_transition_with_full_block(spec, state, True, True, sync_aggregate=sync_aggregate)
    yield from emit_update(test, spec, state, block, attested_state, attested_block, finalized_block)
    assert test.s_spec.get_lc_beacon_slot(test.store.finalized_header) == finalized_state.slot
    assert test.store.next_sync_committee == finalized_state.next_sync_committee
    assert test.store.best_valid_update is None
    assert test.s_spec.get_lc_beacon_slot(test.store.optimistic_header) == attested_state.slot

    # Finish test
    yield from finish_test(test)


@with_altair_and_later
@spec_state_test_with_matching_config
@with_presets([MINIMAL], reason="too slow")
def test_supply_sync_committee_from_past_update(spec, state):
    # Advance the chain, so that a `LightClientUpdate` from the past is available
    next_slots(spec, state, spec.SLOTS_PER_EPOCH * 2 - 1)
    finalized_block = state_transition_with_full_block(spec, state, True, True)
    finalized_state = state.copy()
    _, _, state = next_slots_with_attestations(spec, state, 2 * spec.SLOTS_PER_EPOCH - 1, True, True)
    attested_block = state_transition_with_full_block(spec, state, True, True)
    attested_state = state.copy()
    sync_aggregate, _ = get_sync_aggregate(spec, state)
    block = state_transition_with_full_block(spec, state, True, True, sync_aggregate=sync_aggregate)
    past_state = state.copy()

    # Start test
    test = yield from setup_test(spec, state)
    assert not spec.is_next_sync_committee_known(test.store)

    # Apply `LightClientUpdate` from the past, populating `store.next_sync_committee`
    yield from emit_update(test, spec, past_state, block, attested_state, attested_block, finalized_block)
    assert spec.get_lc_beacon_slot(test.store.finalized_header) == state.slot
    assert test.store.next_sync_committee == finalized_state.next_sync_committee
    assert test.store.best_valid_update is None
    assert spec.get_lc_beacon_slot(test.store.optimistic_header) == state.slot

    # Finish test
    yield from finish_test(test)


@with_altair_and_later
@spec_state_test_with_matching_config
@with_presets([MINIMAL], reason="too slow")
def test_advance_finality_without_sync_committee(spec, state):
    # Start test
    test = yield from setup_test(spec, state)

    # Initial `LightClientUpdate`, populating `store.next_sync_committee`
    next_slots(spec, state, spec.SLOTS_PER_EPOCH - 1)
    finalized_block = state_transition_with_full_block(spec, state, True, True)
    finalized_state = state.copy()
    _, _, state = next_slots_with_attestations(spec, state, 2 * spec.SLOTS_PER_EPOCH - 1, True, True)
    attested_block = state_transition_with_full_block(spec, state, True, True)
    attested_state = state.copy()
    sync_aggregate, _ = get_sync_aggregate(spec, state)
    block = state_transition_with_full_block(spec, state, True, True, sync_aggregate=sync_aggregate)
    yield from emit_update(test, spec, state, block, attested_state, attested_block, finalized_block)
    assert test.s_spec.get_lc_beacon_slot(test.store.finalized_header) == finalized_state.slot
    assert test.store.next_sync_committee == finalized_state.next_sync_committee
    assert test.store.best_valid_update is None
    assert test.s_spec.get_lc_beacon_slot(test.store.optimistic_header) == attested_state.slot

    # Advance finality into next sync committee period, but omit `next_sync_committee`
    transition_to(spec, state, compute_start_slot_at_next_sync_committee_period(spec, state))
    next_slots(spec, state, spec.SLOTS_PER_EPOCH - 1)
    finalized_block = state_transition_with_full_block(spec, state, True, True)
    finalized_state = state.copy()
    _, _, state = next_slots_with_attestations(spec, state, spec.SLOTS_PER_EPOCH - 1, True, True)
    justified_block = state_transition_with_full_block(spec, state, True, True)
    justified_state = state.copy()
    _, _, state = next_slots_with_attestations(spec, state, spec.SLOTS_PER_EPOCH - 1, True, True)
    attested_block = state_transition_with_full_block(spec, state, True, True)
    attested_state = state.copy()
    sync_aggregate, _ = get_sync_aggregate(spec, state)
    block = state_transition_with_full_block(spec, state, True, True, sync_aggregate=sync_aggregate)
    yield from emit_update(test, spec, state, block, attested_state, attested_block, finalized_block, with_next=False)
    assert test.s_spec.get_lc_beacon_slot(test.store.finalized_header) == finalized_state.slot
    assert not spec.is_next_sync_committee_known(test.store)
    assert test.store.best_valid_update is None
    assert test.s_spec.get_lc_beacon_slot(test.store.optimistic_header) == attested_state.slot

    # Advance finality once more, with `next_sync_committee` still unknown
    past_state = finalized_state
    finalized_block = justified_block
    finalized_state = justified_state
    _, _, state = next_slots_with_attestations(spec, state, spec.SLOTS_PER_EPOCH - 2, True, True)
    attested_block = state_transition_with_full_block(spec, state, True, True)
    attested_state = state.copy()
    sync_aggregate, _ = get_sync_aggregate(spec, state)
    block = state_transition_with_full_block(spec, state, True, True, sync_aggregate=sync_aggregate)

    # Apply `LightClientUpdate` without `finalized_header` nor `next_sync_committee`
    update = yield from emit_update(test, spec, state, block, attested_state, attested_block, None, with_next=False)
    assert spec.get_lc_beacon_slot(test.store.finalized_header) == past_state.slot
    assert not spec.is_next_sync_committee_known(test.store)
    assert test.store.best_valid_update == update
    assert test.s_spec.get_lc_beacon_slot(test.store.optimistic_header) == attested_state.slot

    # Apply `LightClientUpdate` with `finalized_header` but no `next_sync_committee`
    yield from emit_update(test, spec, state, block, attested_state, attested_block, finalized_block, with_next=False)
    assert test.s_spec.get_lc_beacon_slot(test.store.finalized_header) == finalized_state.slot
    assert not spec.is_next_sync_committee_known(test.store)
    assert test.store.best_valid_update is None
    assert test.s_spec.get_lc_beacon_slot(test.store.optimistic_header) == attested_state.slot

    # Apply full `LightClientUpdate`, supplying `next_sync_committee`
    yield from emit_update(test, spec, state, block, attested_state, attested_block, finalized_block)
    assert test.s_spec.get_lc_beacon_slot(test.store.finalized_header) == finalized_state.slot
    assert test.store.next_sync_committee == finalized_state.next_sync_committee
    assert test.store.best_valid_update is None
    assert test.s_spec.get_lc_beacon_slot(test.store.optimistic_header) == attested_state.slot

    # Finish test
    yield from finish_test(test)


@with_phases(phases=[BELLATRIX], other_phases=[CAPELLA])
@spec_test
@with_config_overrides({
    'CAPELLA_FORK_EPOCH': 3,  # `setup_test` advances to epoch 2
}, emit=False)
@with_state
@with_matching_spec_config(emitted_fork=CAPELLA)
@with_presets([MINIMAL], reason="too slow")
def test_capella_fork(spec, phases, state):
    # Start test
    test = yield from setup_test(spec, state, phases=phases)

    # Initial `LightClientUpdate`
    finalized_block = spec.SignedBeaconBlock()
    finalized_block.message.state_root = state.hash_tree_root()
    finalized_state = state.copy()
    attested_block = state_transition_with_full_block(spec, state, True, True)
    attested_state = state.copy()
    sync_aggregate, _ = get_sync_aggregate(spec, state)
    block = state_transition_with_full_block(spec, state, True, True, sync_aggregate=sync_aggregate)
    yield from emit_update(test, spec, state, block, attested_state, attested_block, finalized_block, phases=phases)
    assert test.s_spec.get_lc_beacon_slot(test.store.finalized_header) == finalized_state.slot
    assert test.store.next_sync_committee == finalized_state.next_sync_committee
    assert test.store.best_valid_update is None
    assert test.s_spec.get_lc_beacon_slot(test.store.optimistic_header) == attested_state.slot

    # Jump to two slots before Capella
    transition_to(spec, state, spec.compute_start_slot_at_epoch(phases[CAPELLA].config.CAPELLA_FORK_EPOCH) - 4)
    attested_block = state_transition_with_full_block(spec, state, True, True)
    attested_state = state.copy()
    sync_aggregate, _ = get_sync_aggregate(spec, state)
    block = state_transition_with_full_block(spec, state, True, True, sync_aggregate=sync_aggregate)
    update = \
        yield from emit_update(test, spec, state, block, attested_state, attested_block, finalized_block, phases=phases)
    assert test.s_spec.get_lc_beacon_slot(test.store.finalized_header) == finalized_state.slot
    assert test.store.next_sync_committee == finalized_state.next_sync_committee
    assert test.store.best_valid_update == update
    assert test.s_spec.get_lc_beacon_slot(test.store.optimistic_header) == attested_state.slot

    # Perform `LightClientStore` upgrade
    yield from emit_upgrade_store(test, phases[CAPELLA], phases=phases)
    update = test.store.best_valid_update

    # Final slot before Capella, check that importing the Altair format still works
    attested_block = block.copy()
    attested_state = state.copy()
    sync_aggregate, _ = get_sync_aggregate(spec, state)
    block = state_transition_with_full_block(spec, state, True, True, sync_aggregate=sync_aggregate)
    yield from emit_update(test, spec, state, block, attested_state, attested_block, finalized_block, phases=phases)
    assert test.s_spec.get_lc_beacon_slot(test.store.finalized_header) == finalized_state.slot
    assert test.store.next_sync_committee == finalized_state.next_sync_committee
    assert test.store.best_valid_update == update
    assert test.s_spec.get_lc_beacon_slot(test.store.optimistic_header) == attested_state.slot

    # Upgrade to Capella, attested block is still before the fork
    attested_block = block.copy()
    attested_state = state.copy()
    state, _ = do_fork(state, spec, phases[CAPELLA], phases[CAPELLA].config.CAPELLA_FORK_EPOCH, with_block=False)
    spec = phases[CAPELLA]
    sync_aggregate, _ = get_sync_aggregate(spec, state)
    block = state_transition_with_full_block(spec, state, True, True, sync_aggregate=sync_aggregate)
    yield from emit_update(test, spec, state, block, attested_state, attested_block, finalized_block, phases=phases)
    assert test.s_spec.get_lc_beacon_slot(test.store.finalized_header) == finalized_state.slot
    assert test.store.next_sync_committee == finalized_state.next_sync_committee
    assert test.store.best_valid_update == update
    assert test.s_spec.get_lc_beacon_slot(test.store.optimistic_header) == attested_state.slot
    assert test.s_spec.get_lc_execution_root(test.store.optimistic_header) == test.s_spec.Root()

    # Another block in Capella, this time attested block is after the fork
    attested_block = block.copy()
    attested_state = state.copy()
    sync_aggregate, _ = get_sync_aggregate(spec, state)
    block = state_transition_with_full_block(spec, state, True, True, sync_aggregate=sync_aggregate)
    yield from emit_update(test, spec, state, block, attested_state, attested_block, finalized_block, phases=phases)
    assert test.s_spec.get_lc_beacon_slot(test.store.finalized_header) == finalized_state.slot
    assert test.store.next_sync_committee == finalized_state.next_sync_committee
    assert test.store.best_valid_update == update
    assert test.s_spec.get_lc_beacon_slot(test.store.optimistic_header) == attested_state.slot
    assert test.s_spec.get_lc_execution_root(test.store.optimistic_header) != test.s_spec.Root()

    # Jump to next epoch
    transition_to(spec, state, spec.compute_start_slot_at_epoch(phases[CAPELLA].config.CAPELLA_FORK_EPOCH + 1) - 2)
    attested_block = state_transition_with_full_block(spec, state, True, True)
    attested_state = state.copy()
    sync_aggregate, _ = get_sync_aggregate(spec, state)
    block = state_transition_with_full_block(spec, state, True, True, sync_aggregate=sync_aggregate)
    yield from emit_update(test, spec, state, block, attested_state, attested_block, finalized_block, phases=phases)
    assert test.s_spec.get_lc_beacon_slot(test.store.finalized_header) == finalized_state.slot
    assert test.s_spec.get_lc_execution_root(test.store.finalized_header) == test.s_spec.Root()
    assert test.store.next_sync_committee == finalized_state.next_sync_committee
    assert test.store.best_valid_update == update
    assert test.s_spec.get_lc_beacon_slot(test.store.optimistic_header) == attested_state.slot
    assert test.s_spec.get_lc_execution_root(test.store.optimistic_header) != test.s_spec.Root()

    # Finalize it
    finalized_block = block.copy()
    finalized_state = state.copy()
    _, _, state = next_slots_with_attestations(spec, state, 2 * spec.SLOTS_PER_EPOCH - 1, True, True)
    attested_block = state_transition_with_full_block(spec, state, True, True)
    attested_state = state.copy()
    sync_aggregate, _ = get_sync_aggregate(spec, state)
    block = state_transition_with_full_block(spec, state, True, True, sync_aggregate=sync_aggregate)
    yield from emit_update(test, spec, state, block, attested_state, attested_block, finalized_block, phases=phases)
    assert test.s_spec.get_lc_beacon_slot(test.store.finalized_header) == finalized_state.slot
    assert test.s_spec.get_lc_execution_root(test.store.finalized_header) != test.s_spec.Root()
    assert test.store.next_sync_committee == finalized_state.next_sync_committee
    assert test.store.best_valid_update is None
    assert test.s_spec.get_lc_beacon_slot(test.store.optimistic_header) == attested_state.slot
    assert test.s_spec.get_lc_execution_root(test.store.optimistic_header) != test.s_spec.Root()

    # Finish test
    yield from finish_test(test)


def run_test_upgraded_store_with_legacy_data(spec, state, s_spec, phases):
    # Start test (Legacy bootstrap with an upgraded store)
    test = yield from setup_test(spec, state, s_spec, phases)

    # Initial `LightClientUpdate` (check that the upgraded store can process it)
    finalized_block = spec.SignedBeaconBlock()
    finalized_block.message.state_root = state.hash_tree_root()
    finalized_state = state.copy()
    attested_block = state_transition_with_full_block(spec, state, True, True)
    attested_state = state.copy()
    sync_aggregate, _ = get_sync_aggregate(spec, state)
    block = state_transition_with_full_block(spec, state, True, True, sync_aggregate=sync_aggregate)
    yield from emit_update(test, spec, state, block, attested_state, attested_block, finalized_block, phases=phases)
    assert test.s_spec.get_lc_beacon_slot(test.store.finalized_header) == finalized_state.slot
    assert test.store.next_sync_committee == finalized_state.next_sync_committee
    assert test.store.best_valid_update is None
    assert test.s_spec.get_lc_beacon_slot(test.store.optimistic_header) == attested_state.slot

    # Finish test
    yield from finish_test(test)


@with_phases(phases=[ALTAIR, BELLATRIX], other_phases=[CAPELLA])
@spec_test
@with_state
@with_matching_spec_config(emitted_fork=CAPELLA)
@with_presets([MINIMAL], reason="too slow")
def test_capella_store_with_legacy_data(spec, phases, state):
    yield from run_test_upgraded_store_with_legacy_data(spec, state, phases[CAPELLA], phases)


@with_phases(phases=[ALTAIR, BELLATRIX, CAPELLA], other_phases=[EIP4844])
@spec_test
@with_state
@with_matching_spec_config(emitted_fork=EIP4844)
@with_presets([MINIMAL], reason="too slow")
def test_eip4844_store_with_legacy_data(spec, phases, state):
    yield from run_test_upgraded_store_with_legacy_data(spec, state, phases[EIP4844], phases)
