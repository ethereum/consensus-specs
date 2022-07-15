# Altair -- Minimal Light Client

**Notice**: This document is a work-in-progress for researchers and implementers.

## Table of contents

<!-- TOC -->
<!-- START doctoc generated TOC please keep comment here to allow auto update -->
<!-- DON'T EDIT THIS SECTION, INSTEAD RE-RUN doctoc TO UPDATE -->

- [Introduction](#introduction)
- [Constants](#constants)
- [Preset](#preset)
  - [Misc](#misc)
- [Containers](#containers)
  - [`LightClientBootstrap`](#lightclientbootstrap)
  - [`LightClientUpdate`](#lightclientupdate)
  - [`LightClientStore`](#lightclientstore)
- [Helper functions](#helper-functions)
  - [`is_sync_committee_update`](#is_sync_committee_update)
  - [`is_finality_update`](#is_finality_update)
  - [`is_better_update`](#is_better_update)
  - [`is_next_sync_committee_known`](#is_next_sync_committee_known)
  - [`get_safety_threshold`](#get_safety_threshold)
  - [`compute_sync_committee_period_at_slot`](#compute_sync_committee_period_at_slot)
  - [`get_subtree_index`](#get_subtree_index)
  - [`compute_merkle_proof_for_state`](#compute_merkle_proof_for_state)
- [Light client initialization](#light-client-initialization)
  - [`initialize_light_client_store`](#initialize_light_client_store)
- [Light client state updates](#light-client-state-updates)
  - [`process_slot_for_light_client_store`](#process_slot_for_light_client_store)
  - [`validate_light_client_update`](#validate_light_client_update)
  - [`apply_light_client_update`](#apply_light_client_update)
  - [`process_light_client_update`](#process_light_client_update)
- [Deriving light client data](#deriving-light-client-data)
  - [`create_light_client_bootstrap`](#create_light_client_bootstrap)
  - [`create_light_client_update`](#create_light_client_update)

<!-- END doctoc generated TOC please keep comment here to allow auto update -->
<!-- /TOC -->

## Introduction

The beacon chain is designed to be light client friendly for constrained environments to
access Ethereum with reasonable safety and liveness.
Such environments include resource-constrained devices (e.g. phones for trust-minimized wallets)
and metered VMs (e.g. blockchain VMs for cross-chain bridges).

This document suggests a minimal light client design for the beacon chain that
uses sync committees introduced in [this beacon chain extension](./beacon-chain.md).

## Constants

| Name | Value |
| - | - |
| `FINALIZED_ROOT_INDEX` | `get_generalized_index(BeaconState, 'finalized_checkpoint', 'root')` (= 105) |
| `CURRENT_SYNC_COMMITTEE_INDEX` | `get_generalized_index(BeaconState, 'current_sync_committee')` (= 54) |
| `NEXT_SYNC_COMMITTEE_INDEX` | `get_generalized_index(BeaconState, 'next_sync_committee')` (= 55) |

## Preset

### Misc

| Name | Value | Unit | Duration |
| - | - | - | - |
| `MIN_SYNC_COMMITTEE_PARTICIPANTS` | `1` | validators | |
| `UPDATE_TIMEOUT` | `SLOTS_PER_EPOCH * EPOCHS_PER_SYNC_COMMITTEE_PERIOD` | slots | ~27.3 hours |

## Containers

### `LightClientBootstrap`

```python
class LightClientBootstrap(Container):
    # The requested beacon block header
    header: BeaconBlockHeader
    # Current sync committee corresponding to `header`
    current_sync_committee: SyncCommittee
    current_sync_committee_branch: Vector[Bytes32, floorlog2(CURRENT_SYNC_COMMITTEE_INDEX)]
```

### `LightClientUpdate`

```python
class LightClientUpdate(Container):
    # The beacon block header that is attested to by the sync committee
    attested_header: BeaconBlockHeader
    # Next sync committee corresponding to `attested_header`
    next_sync_committee: SyncCommittee
    next_sync_committee_branch: Vector[Bytes32, floorlog2(NEXT_SYNC_COMMITTEE_INDEX)]
    # The finalized beacon block header attested to by Merkle branch
    finalized_header: BeaconBlockHeader
    finality_branch: Vector[Bytes32, floorlog2(FINALIZED_ROOT_INDEX)]
    # Sync committee aggregate signature
    sync_aggregate: SyncAggregate
    # Slot at which the aggregate signature was created (untrusted)
    signature_slot: Slot
```

### `LightClientStore`

```python
@dataclass
class LightClientStore(object):
    # Beacon block header that is finalized
    finalized_header: BeaconBlockHeader
    # Sync committees corresponding to the header
    current_sync_committee: SyncCommittee
    next_sync_committee: SyncCommittee
    # Best available header to switch finalized head to if we see nothing else
    best_valid_update: Optional[LightClientUpdate]
    # Most recent available reasonably-safe header
    optimistic_header: BeaconBlockHeader
    # Max number of active participants in a sync committee (used to calculate safety threshold)
    previous_max_active_participants: uint64
    current_max_active_participants: uint64
```

## Helper functions

### `is_sync_committee_update`

```python
def is_sync_committee_update(update: LightClientUpdate) -> bool:
    return update.next_sync_committee_branch != [Bytes32() for _ in range(floorlog2(NEXT_SYNC_COMMITTEE_INDEX))]
```

### `is_finality_update`

```python
def is_finality_update(update: LightClientUpdate) -> bool:
    return update.finality_branch != [Bytes32() for _ in range(floorlog2(FINALIZED_ROOT_INDEX))]
```

### `is_better_update`

```python
def is_better_update(new_update: LightClientUpdate, old_update: LightClientUpdate) -> bool:
    # Compare supermajority (> 2/3) sync committee participation
    max_active_participants = len(new_update.sync_aggregate.sync_committee_bits)
    new_num_active_participants = sum(new_update.sync_aggregate.sync_committee_bits)
    old_num_active_participants = sum(old_update.sync_aggregate.sync_committee_bits)
    new_has_supermajority = new_num_active_participants * 3 >= max_active_participants * 2
    old_has_supermajority = old_num_active_participants * 3 >= max_active_participants * 2
    if new_has_supermajority != old_has_supermajority:
        return new_has_supermajority > old_has_supermajority
    if not new_has_supermajority and new_num_active_participants != old_num_active_participants:
        return new_num_active_participants > old_num_active_participants

    # Compare presence of relevant sync committee
    new_has_relevant_sync_committee = is_sync_committee_update(new_update) and (
        compute_sync_committee_period_at_slot(new_update.attested_header.slot)
        == compute_sync_committee_period_at_slot(new_update.signature_slot)
    )
    old_has_relevant_sync_committee = is_sync_committee_update(old_update) and (
        compute_sync_committee_period_at_slot(old_update.attested_header.slot)
        == compute_sync_committee_period_at_slot(old_update.signature_slot)
    )
    if new_has_relevant_sync_committee != old_has_relevant_sync_committee:
        return new_has_relevant_sync_committee

    # Compare indication of any finality
    new_has_finality = is_finality_update(new_update)
    old_has_finality = is_finality_update(old_update)
    if new_has_finality != old_has_finality:
        return new_has_finality

    # Compare sync committee finality
    if new_has_finality:
        new_has_sync_committee_finality = (
            compute_sync_committee_period_at_slot(new_update.finalized_header.slot)
            == compute_sync_committee_period_at_slot(new_update.attested_header.slot)
        )
        old_has_sync_committee_finality = (
            compute_sync_committee_period_at_slot(old_update.finalized_header.slot)
            == compute_sync_committee_period_at_slot(old_update.attested_header.slot)
        )
        if new_has_sync_committee_finality != old_has_sync_committee_finality:
            return new_has_sync_committee_finality

    # Tiebreaker 1: Sync committee participation beyond supermajority
    if new_num_active_participants != old_num_active_participants:
        return new_num_active_participants > old_num_active_participants

    # Tiebreaker 2: Prefer older data (fewer changes to best)
    if new_update.attested_header.slot != old_update.attested_header.slot:
        return new_update.attested_header.slot < old_update.attested_header.slot
    return new_update.signature_slot < old_update.signature_slot
```

### `is_next_sync_committee_known`

```python
def is_next_sync_committee_known(store: LightClientStore) -> bool:
    return store.next_sync_committee != SyncCommittee()
```

### `get_safety_threshold`

```python
def get_safety_threshold(store: LightClientStore) -> uint64:
    return max(
        store.previous_max_active_participants,
        store.current_max_active_participants,
    ) // 2
```

### `compute_sync_committee_period_at_slot`

```python
def compute_sync_committee_period_at_slot(slot: Slot) -> uint64:
    return compute_sync_committee_period(compute_epoch_at_slot(slot))
```

### `get_subtree_index`

```python
def get_subtree_index(generalized_index: GeneralizedIndex) -> uint64:
    return uint64(generalized_index % 2**(floorlog2(generalized_index)))
```

### `compute_merkle_proof_for_state`

```python
def compute_merkle_proof_for_state(state: BeaconState,
                                   index: GeneralizedIndex) -> Sequence[Bytes32]:
    ...
```

## Light client initialization

A light client maintains its state in a `store` object of type `LightClientStore`. `initialize_light_client_store` initializes a new `store` with a received `LightClientBootstrap` derived from a given `trusted_block_root`.

### `initialize_light_client_store`

```python
def initialize_light_client_store(trusted_block_root: Root,
                                  bootstrap: LightClientBootstrap) -> LightClientStore:
    assert hash_tree_root(bootstrap.header) == trusted_block_root

    assert is_valid_merkle_branch(
        leaf=hash_tree_root(bootstrap.current_sync_committee),
        branch=bootstrap.current_sync_committee_branch,
        depth=floorlog2(CURRENT_SYNC_COMMITTEE_INDEX),
        index=get_subtree_index(CURRENT_SYNC_COMMITTEE_INDEX),
        root=bootstrap.header.state_root,
    )

    return LightClientStore(
        finalized_header=bootstrap.header,
        current_sync_committee=bootstrap.current_sync_committee,
        next_sync_committee=SyncCommittee(),
        best_valid_update=None,
        optimistic_header=bootstrap.header,
        previous_max_active_participants=0,
        current_max_active_participants=0,
    )
```

## Light client state updates

A light client receives `update` objects of type `LightClientUpdate`. Every `update` triggers `process_light_client_update(store, update, current_slot, genesis_validators_root)` where `current_slot` is the current slot based on a local clock. `process_slot_for_light_client_store` is triggered every time the current slot increments.

### `process_slot_for_light_client_store`

```python
def process_slot_for_light_client_store(store: LightClientStore, current_slot: Slot) -> None:
    if current_slot % UPDATE_TIMEOUT == 0:
        store.previous_max_active_participants = store.current_max_active_participants
        store.current_max_active_participants = 0
    if (
        current_slot > store.finalized_header.slot + UPDATE_TIMEOUT
        and store.best_valid_update is not None
    ):
        # Forced best update when the update timeout has elapsed.
        # Because the apply logic waits for `finalized_header.slot` to indicate sync committee finality,
        # the `attested_header` may be treated as `finalized_header` in extended periods of non-finality
        # to guarantee progression into later sync committee periods according to `is_better_update`.
        if store.best_valid_update.finalized_header.slot <= store.finalized_header.slot:
            store.best_valid_update.finalized_header = store.best_valid_update.attested_header
        apply_light_client_update(store, store.best_valid_update)
        store.best_valid_update = None
```

### `validate_light_client_update`

```python
def validate_light_client_update(store: LightClientStore,
                                 update: LightClientUpdate,
                                 current_slot: Slot,
                                 genesis_validators_root: Root) -> None:
    # Verify sync committee has sufficient participants
    sync_aggregate = update.sync_aggregate
    assert sum(sync_aggregate.sync_committee_bits) >= MIN_SYNC_COMMITTEE_PARTICIPANTS

    # Verify update does not skip a sync committee period
    assert current_slot >= update.signature_slot > update.attested_header.slot >= update.finalized_header.slot
    store_period = compute_sync_committee_period_at_slot(store.finalized_header.slot)
    update_signature_period = compute_sync_committee_period_at_slot(update.signature_slot)
    if is_next_sync_committee_known(store):
        assert update_signature_period in (store_period, store_period + 1)
    else:
        assert update_signature_period == store_period

    # Verify update is relevant
    update_attested_period = compute_sync_committee_period_at_slot(update.attested_header.slot)
    update_has_next_sync_committee = not is_next_sync_committee_known(store) and (
        is_sync_committee_update(update) and update_attested_period == store_period
    )
    assert (
        update.attested_header.slot > store.finalized_header.slot
        or update_has_next_sync_committee
    )

    # Verify that the `finality_branch`, if present, confirms `finalized_header`
    # to match the finalized checkpoint root saved in the state of `attested_header`.
    # Note that the genesis finalized checkpoint root is represented as a zero hash.
    if not is_finality_update(update):
        assert update.finalized_header == BeaconBlockHeader()
    else:
        if update.finalized_header.slot == GENESIS_SLOT:
            assert update.finalized_header == BeaconBlockHeader()
            finalized_root = Bytes32()
        else:
            finalized_root = hash_tree_root(update.finalized_header)
        assert is_valid_merkle_branch(
            leaf=finalized_root,
            branch=update.finality_branch,
            depth=floorlog2(FINALIZED_ROOT_INDEX),
            index=get_subtree_index(FINALIZED_ROOT_INDEX),
            root=update.attested_header.state_root,
        )

    # Verify that the `next_sync_committee`, if present, actually is the next sync committee saved in the
    # state of the `attested_header`
    if not is_sync_committee_update(update):
        assert update.next_sync_committee == SyncCommittee()
    else:
        if update_attested_period == store_period and is_next_sync_committee_known(store):
            assert update.next_sync_committee == store.next_sync_committee
        assert is_valid_merkle_branch(
            leaf=hash_tree_root(update.next_sync_committee),
            branch=update.next_sync_committee_branch,
            depth=floorlog2(NEXT_SYNC_COMMITTEE_INDEX),
            index=get_subtree_index(NEXT_SYNC_COMMITTEE_INDEX),
            root=update.attested_header.state_root,
        )

    # Verify sync committee aggregate signature
    if update_signature_period == store_period:
        sync_committee = store.current_sync_committee
    else:
        sync_committee = store.next_sync_committee
    participant_pubkeys = [
        pubkey for (bit, pubkey) in zip(sync_aggregate.sync_committee_bits, sync_committee.pubkeys)
        if bit
    ]
    fork_version = compute_fork_version(compute_epoch_at_slot(update.signature_slot))
    domain = compute_domain(DOMAIN_SYNC_COMMITTEE, fork_version, genesis_validators_root)
    signing_root = compute_signing_root(update.attested_header, domain)
    assert bls.FastAggregateVerify(participant_pubkeys, signing_root, sync_aggregate.sync_committee_signature)
```

### `apply_light_client_update`

```python
def apply_light_client_update(store: LightClientStore, update: LightClientUpdate) -> None:
    store_period = compute_sync_committee_period_at_slot(store.finalized_header.slot)
    update_finalized_period = compute_sync_committee_period_at_slot(update.finalized_header.slot)
    if not is_next_sync_committee_known(store):
        assert update_finalized_period == store_period
        store.next_sync_committee = update.next_sync_committee
    elif update_finalized_period == store_period + 1:
        store.current_sync_committee = store.next_sync_committee
        store.next_sync_committee = update.next_sync_committee
    if update.finalized_header.slot > store.finalized_header.slot:
        store.finalized_header = update.finalized_header
        if store.finalized_header.slot > store.optimistic_header.slot:
            store.optimistic_header = store.finalized_header
```

### `process_light_client_update`

```python
def process_light_client_update(store: LightClientStore,
                                update: LightClientUpdate,
                                current_slot: Slot,
                                genesis_validators_root: Root) -> None:
    validate_light_client_update(store, update, current_slot, genesis_validators_root)

    sync_committee_bits = update.sync_aggregate.sync_committee_bits

    # Update the best update in case we have to force-update to it if the timeout elapses
    if (
        store.best_valid_update is None
        or is_better_update(update, store.best_valid_update)
    ):
        store.best_valid_update = update

    # Track the maximum number of active participants in the committee signatures
    store.current_max_active_participants = max(
        store.current_max_active_participants,
        sum(sync_committee_bits),
    )

    # Update the optimistic header
    if (
        sum(sync_committee_bits) > get_safety_threshold(store)
        and update.attested_header.slot > store.optimistic_header.slot
    ):
        store.optimistic_header = update.attested_header

    # Update finalized header
    update_has_finalized_next_sync_committee = (
        not is_next_sync_committee_known(store)
        and is_sync_committee_update(update) and is_finality_update(update) and (
            compute_sync_committee_period_at_slot(update.finalized_header.slot)
            == compute_sync_committee_period_at_slot(update.attested_header.slot)
        )
    )
    if (
        sum(sync_committee_bits) * 3 >= len(sync_committee_bits) * 2
        and (
            update.finalized_header.slot > store.finalized_header.slot
            or update_has_finalized_next_sync_committee
        )
    ):
        # Normal update through 2/3 threshold
        apply_light_client_update(store, update)
        store.best_valid_update = None
```

## Deriving light client data

Full nodes are expected to derive light client data from historic blocks and states and provide it to other clients.

### `create_light_client_bootstrap`

```python
def create_light_client_bootstrap(state: BeaconState) -> LightClientBootstrap:
    assert compute_epoch_at_slot(state.slot) >= ALTAIR_FORK_EPOCH
    assert state.slot == state.latest_block_header.slot

    return LightClientBootstrap(
        header=BeaconBlockHeader(
            slot=state.latest_block_header.slot,
            proposer_index=state.latest_block_header.proposer_index,
            parent_root=state.latest_block_header.parent_root,
            state_root=hash_tree_root(state),
            body_root=state.latest_block_header.body_root,
        ),
        current_sync_committee=state.current_sync_committee,
        current_sync_committee_branch=compute_merkle_proof_for_state(state, CURRENT_SYNC_COMMITTEE_INDEX)
    )
```

Full nodes SHOULD provide `LightClientBootstrap` for all finalized epoch boundary blocks in the epoch range `[max(ALTAIR_FORK_EPOCH, current_epoch - MIN_EPOCHS_FOR_BLOCK_REQUESTS), current_epoch]` where `current_epoch` is defined by the current wall-clock time. Full nodes MAY also provide `LightClientBootstrap` for other blocks.

Blocks are considered to be epoch boundary blocks if their block root can occur as part of a valid `Checkpoint`, i.e., if their slot is the initial slot of an epoch, or if all following slots through the initial slot of the next epoch are empty (no block proposed / orphaned).

`LightClientBootstrap` is computed from the block's immediate post state (without applying empty slots).

### `create_light_client_update`

To form a `LightClientUpdate`, the following historical states and blocks are needed:
- `state`: the post state of any block with a post-Altair parent block
- `block`: the corresponding block
- `attested_state`: the post state of the block referred to by `block.parent_root`
- `finalized_block`: the block referred to by `attested_state.finalized_checkpoint.root`, if locally available (may be unavailable, e.g., when using checkpoint sync, or if it was pruned locally)

```python
def create_light_client_update(state: BeaconState,
                               block: SignedBeaconBlock,
                               attested_state: BeaconState,
                               finalized_block: Optional[SignedBeaconBlock]) -> LightClientUpdate:
    assert compute_epoch_at_slot(attested_state.slot) >= ALTAIR_FORK_EPOCH
    assert sum(block.message.body.sync_aggregate.sync_committee_bits) >= MIN_SYNC_COMMITTEE_PARTICIPANTS

    assert state.slot == state.latest_block_header.slot
    header = state.latest_block_header.copy()
    header.state_root = hash_tree_root(state)
    assert hash_tree_root(header) == hash_tree_root(block.message)
    update_signature_period = compute_sync_committee_period(compute_epoch_at_slot(block.message.slot))

    assert attested_state.slot == attested_state.latest_block_header.slot
    attested_header = attested_state.latest_block_header.copy()
    attested_header.state_root = hash_tree_root(attested_state)
    assert hash_tree_root(attested_header) == block.message.parent_root
    update_attested_period = compute_sync_committee_period(compute_epoch_at_slot(attested_header.slot))

    # `next_sync_committee` is only useful if the message is signed by the current sync committee
    if update_attested_period == update_signature_period:
        next_sync_committee = attested_state.next_sync_committee
        next_sync_committee_branch = compute_merkle_proof_for_state(attested_state, NEXT_SYNC_COMMITTEE_INDEX)
    else:
        next_sync_committee = SyncCommittee()
        next_sync_committee_branch = [Bytes32() for _ in range(floorlog2(NEXT_SYNC_COMMITTEE_INDEX))]

    # Indicate finality whenever possible
    if finalized_block is not None:
        if finalized_block.message.slot != GENESIS_SLOT:
            finalized_header = BeaconBlockHeader(
                slot=finalized_block.message.slot,
                proposer_index=finalized_block.message.proposer_index,
                parent_root=finalized_block.message.parent_root,
                state_root=finalized_block.message.state_root,
                body_root=hash_tree_root(finalized_block.message.body),
            )
            assert hash_tree_root(finalized_header) == attested_state.finalized_checkpoint.root
        else:
            assert attested_state.finalized_checkpoint.root == Bytes32()
            finalized_header = BeaconBlockHeader()
        finality_branch = compute_merkle_proof_for_state(attested_state, FINALIZED_ROOT_INDEX)
    else:
        finalized_header = BeaconBlockHeader()
        finality_branch = [Bytes32() for _ in range(floorlog2(FINALIZED_ROOT_INDEX))]

    return LightClientUpdate(
        attested_header=attested_header,
        next_sync_committee=next_sync_committee,
        next_sync_committee_branch=next_sync_committee_branch,
        finalized_header=finalized_header,
        finality_branch=finality_branch,
        sync_aggregate=block.message.body.sync_aggregate,
        signature_slot=block.message.slot,
    )
```

Full nodes SHOULD provide the best derivable `LightClientUpdate` (according to `is_better_update`) for each sync committee period covering any epochs in range `[max(ALTAIR_FORK_EPOCH, current_epoch - MIN_EPOCHS_FOR_BLOCK_REQUESTS), current_epoch]` where `current_epoch` is defined by the current wall-clock time. Full nodes MAY also provide `LightClientUpdate` for other sync committee periods.

- `LightClientUpdate` are assigned to sync committee periods based on their `attested_header.slot`
- `LightClientUpdate` are only considered if `compute_sync_committee_period(compute_epoch_at_slot(update.attested_header.slot)) == compute_sync_committee_period(compute_epoch_at_slot(update.signature_slot))`
- Only `LightClientUpdate` with `next_sync_committee` as selected by fork choice are provided, regardless of ranking by `is_better_update`. To uniquely identify a non-finalized sync committee fork, all of `period`, `current_sync_committee` and `next_sync_committee` need to be incorporated, as sync committees may reappear over time.
