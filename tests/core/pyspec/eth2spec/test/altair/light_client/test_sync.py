from typing import (Any, Dict, List)

from eth_utils import encode_hex
from eth2spec.test.context import (
    spec_state_test_with_matching_config,
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
)
from eth2spec.test.helpers.state import (
    next_slots,
    transition_to,
)


def setup_test(spec, state):
    class LightClientSyncTest(object):
        steps: List[Dict[str, Any]]
        genesis_validators_root: spec.Root
        store: spec.LightClientStore

    test = LightClientSyncTest()
    test.steps = []

    yield "genesis_validators_root", "meta", "0x" + state.genesis_validators_root.hex()
    test.genesis_validators_root = state.genesis_validators_root

    next_slots(spec, state, spec.SLOTS_PER_EPOCH * 2 - 1)
    trusted_block = state_transition_with_full_block(spec, state, True, True)
    trusted_block_root = trusted_block.message.hash_tree_root()
    bootstrap = spec.create_light_client_bootstrap(state, trusted_block)
    yield "trusted_block_root", "meta", "0x" + trusted_block_root.hex()
    yield "bootstrap", bootstrap
    test.store = spec.initialize_light_client_store(trusted_block_root, bootstrap)

    return test


def finish_test(test):
    yield "steps", test.steps


def get_update_file_name(spec, update):
    if spec.is_sync_committee_update(update):
        suffix1 = "s"
    else:
        suffix1 = "x"
    if spec.is_finality_update(update):
        suffix2 = "f"
    else:
        suffix2 = "x"
    return f"update_{encode_hex(spec.get_lc_beacon_root(update.attested_header))}_{suffix1}{suffix2}"


def get_checks(spec, store):
    return {
        "finalized_header": {
            'slot': int(spec.get_lc_beacon_slot(store.finalized_header)),
            'beacon_root': encode_hex(spec.get_lc_beacon_root(store.finalized_header)),
        },
        "optimistic_header": {
            'slot': int(spec.get_lc_beacon_slot(store.optimistic_header)),
            'beacon_root': encode_hex(spec.get_lc_beacon_root(store.optimistic_header)),
        },
    }


def emit_force_update(test, spec, state):
    current_slot = state.slot
    spec.process_light_client_store_force_update(test.store, current_slot)

    yield from []  # Consistently enable `yield from` syntax in calling tests
    test.steps.append({
        "force_update": {
            "current_slot": int(current_slot),
            "checks": get_checks(spec, test.store),
        }
    })


def emit_update(test, spec, state, block, attested_state, attested_block, finalized_block, with_next=True):
    update = spec.create_light_client_update(state, block, attested_state, attested_block, finalized_block)
    if not with_next:
        update.next_sync_committee = spec.SyncCommittee()
        update.next_sync_committee_branch = \
            [spec.Bytes32() for _ in range(spec.floorlog2(spec.NEXT_SYNC_COMMITTEE_INDEX))]
    current_slot = state.slot
    spec.process_light_client_update(test.store, update, current_slot, test.genesis_validators_root)

    yield get_update_file_name(spec, update), update
    test.steps.append({
        "process_update": {
            "update": get_update_file_name(spec, update),
            "current_slot": int(current_slot),
            "checks": get_checks(spec, test.store),
        }
    })
    return update


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
    assert spec.get_lc_beacon_slot(test.store.finalized_header) == finalized_state.slot
    assert test.store.next_sync_committee == finalized_state.next_sync_committee
    assert test.store.best_valid_update is None
    assert spec.get_lc_beacon_slot(test.store.optimistic_header) == attested_state.slot

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
    assert spec.get_lc_beacon_slot(test.store.finalized_header) == finalized_state.slot
    assert test.store.next_sync_committee == finalized_state.next_sync_committee
    assert test.store.best_valid_update is None
    assert spec.get_lc_beacon_slot(test.store.optimistic_header) == attested_state.slot

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
    assert spec.get_lc_beacon_slot(test.store.finalized_header) == finalized_state.slot
    assert test.store.next_sync_committee == finalized_state.next_sync_committee
    assert test.store.best_valid_update is None
    assert spec.get_lc_beacon_slot(test.store.optimistic_header) == attested_state.slot

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
    assert spec.get_lc_beacon_slot(test.store.finalized_header) == finalized_state.slot
    assert test.store.next_sync_committee == finalized_state.next_sync_committee
    assert test.store.best_valid_update == update
    assert spec.get_lc_beacon_slot(test.store.optimistic_header) == attested_state.slot

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
    assert spec.get_lc_beacon_slot(test.store.finalized_header) == finalized_state.slot
    assert test.store.next_sync_committee == finalized_state.next_sync_committee
    assert test.store.best_valid_update == update
    assert spec.get_lc_beacon_slot(test.store.optimistic_header) == attested_state.slot

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
    assert spec.get_lc_beacon_slot(test.store.optimistic_header) == attested_state.slot

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
    assert spec.get_lc_beacon_slot(test.store.optimistic_header) == attested_state.slot
    yield from emit_force_update(test, spec, state)
    assert spec.get_lc_beacon_slot(test.store.finalized_header) == attested_state.slot
    assert test.store.next_sync_committee == attested_state.next_sync_committee
    assert test.store.best_valid_update is None
    assert spec.get_lc_beacon_slot(test.store.optimistic_header) == attested_state.slot

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
    assert spec.get_lc_beacon_slot(test.store.finalized_header) == finalized_state.slot
    assert test.store.next_sync_committee == finalized_state.next_sync_committee
    assert test.store.best_valid_update is None
    assert spec.get_lc_beacon_slot(test.store.optimistic_header) == attested_state.slot

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
    assert spec.get_lc_beacon_slot(test.store.finalized_header) == finalized_state.slot
    assert test.store.next_sync_committee == finalized_state.next_sync_committee
    assert test.store.best_valid_update is None
    assert spec.get_lc_beacon_slot(test.store.optimistic_header) == attested_state.slot

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
    assert spec.get_lc_beacon_slot(test.store.finalized_header) == finalized_state.slot
    assert not spec.is_next_sync_committee_known(test.store)
    assert test.store.best_valid_update is None
    assert spec.get_lc_beacon_slot(test.store.optimistic_header) == attested_state.slot

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
    assert spec.get_lc_beacon_slot(test.store.optimistic_header) == attested_state.slot

    # Apply `LightClientUpdate` with `finalized_header` but no `next_sync_committee`
    yield from emit_update(test, spec, state, block, attested_state, attested_block, finalized_block, with_next=False)
    assert spec.get_lc_beacon_slot(test.store.finalized_header) == finalized_state.slot
    assert not spec.is_next_sync_committee_known(test.store)
    assert test.store.best_valid_update is None
    assert spec.get_lc_beacon_slot(test.store.optimistic_header) == attested_state.slot

    # Apply full `LightClientUpdate`, supplying `next_sync_committee`
    yield from emit_update(test, spec, state, block, attested_state, attested_block, finalized_block)
    assert spec.get_lc_beacon_slot(test.store.finalized_header) == finalized_state.slot
    assert test.store.next_sync_committee == finalized_state.next_sync_committee
    assert test.store.best_valid_update is None
    assert spec.get_lc_beacon_slot(test.store.optimistic_header) == attested_state.slot

    # Finish test
    yield from finish_test(test)
