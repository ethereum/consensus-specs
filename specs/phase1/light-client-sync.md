# Minimal Light Client Design

**Notice**: This document is a work-in-progress for researchers and implementers.

## Table of contents

<!-- TOC -->
<!-- START doctoc generated TOC please keep comment here to allow auto update -->
<!-- DON'T EDIT THIS SECTION, INSTEAD RE-RUN doctoc TO UPDATE -->


- [Introduction](#introduction)
- [Custom types](#custom-types)
- [Constants](#constants)
- [Containers](#containers)
  - [`LightClientUpdate`](#lightclientupdate)
  - [`LightClientMemory`](#lightclientmemory)
- [Helpers](#helpers)
  - [Math](#math)
    - [`log_2`](#log_2)
  - [Misc](#misc)
    - [`get_persistent_committee`](#get_persistent_committee)
- [Light client state updates](#light-client-state-updates)
- [Data overhead](#data-overhead)

<!-- END doctoc generated TOC please keep comment here to allow auto update -->
<!-- /TOC -->

## Introduction

Ethereum 2.0 is designed to be light client friendly. This allows low-resource clients such as mobile phones to access Ethereum 2.0 with reasonable safety and liveness. It also facilitates the development of "bridges" to external blockchains. This document suggests a minimal light client design for the beacon chain.

## Custom types

We define the following Python custom types for type hinting and readability:

| Name | SSZ equivalent | Description |
| - | - | - |
| `CompactValidator` | `uint64` | compact representation of a validator for light clients |

## Constants

| Name | Value |
| - | - |
| `BEACON_CHAIN_ROOT_IN_SHARD_BLOCK_HEADER_DEPTH` | `3` |
| `BEACON_CHAIN_ROOT_IN_SHARD_BLOCK_HEADER_INDEX` | 1 |
| `PERIOD_COMMITTEE_ROOT_IN_BEACON_STATE_DEPTH` | `5` |
| `PERIOD_COMMITTEE_ROOT_IN_BEACON_STATE_INDEX` | **TBD** |
| `LOG_2_SHARD_COUNT` | 6 |

`LOG_2_SHARD_COUNT` is set to `log_2(INITIAL_ACTIVE_SHARDS)` now, but might increase in the future forks.

## Containers

### `LightClientUpdate`

```python
class LightClientUpdate(Container):
    # Shard block root (and authenticating signature data)
    shard_block_root: Root
    fork_version: Version
    aggregation_bits: Bitlist[MAX_VALIDATORS_PER_COMMITTEE]
    signature: BLSSignature
    # Updated beacon header (and authenticating branch)
    header: BeaconBlockHeader
    header_branch: Vector[Bytes32, BEACON_CHAIN_ROOT_IN_SHARD_BLOCK_HEADER_DEPTH]
    # Updated period committee (and authenticating branch)
    committee: CompactCommittee
    committee_branch: Vector[Bytes32, PERIOD_COMMITTEE_ROOT_IN_BEACON_STATE_DEPTH + LOG_2_SHARD_COUNT]
```

### `LightClientMemory`

```python
@dataclass
class LightClientMemory(object):
    shard: Shard  # Randomly initialized and retained forever
    header: BeaconBlockHeader  # Beacon header which is not expected to revert
    # period committees corresponding to the beacon header
    previous_committee: CompactCommittee
    current_committee: CompactCommittee
    next_committee: CompactCommittee
```

## Helpers

### Math

#### `log_2`

```python
def log_2(n: uint64) -> uint64:
    # TODO: maybe need stricter definition
    return uint64(math.log2(n))
```

### Misc

#### `get_persistent_committee`

```python
def get_persistent_committee(
        memory: LightClientMemory,
        epoch: Epoch) -> Tuple[Sequence[BLSPubkey], Sequence[uint64], Sequence[uint64]]:
    """
    Return pubkeys and balances for the persistent committee at ``epoch``.
    """
    current_period = compute_epoch_at_slot(memory.header.slot) // LIGHT_CLIENT_COMMITTEE_PERIOD
    next_period = epoch // LIGHT_CLIENT_COMMITTEE_PERIOD
    assert next_period in (current_period, current_period + 1)
    if next_period == current_period:
        earlier_committee, later_committee = memory.previous_committee, memory.current_committee
    else:
        earlier_committee, later_committee = memory.current_committee, memory.next_committee

    pubkeys = []
    balance_in_increments = []  # balance // EFFECTIVE_BALANCE_INCREMENT
    committee_offsets = []
    earlier_committee_offsets = list(range(len(earlier_committee.pubkeys)))

    # Take not-yet-cycled-out validators from earlier committee and already-cycled-in validators from
    # later committee; return a sorted list of the union of the two, deduplicated.
    for i, pubkey, compact_validator in zip(
        earlier_committee_offsets, earlier_committee.pubkeys, earlier_committee.compact_validators
    ):
        index, slashed, balance = unpack_compact_validator(compact_validator)
        if epoch % LIGHT_CLIENT_COMMITTEE_PERIOD < index % LIGHT_CLIENT_COMMITTEE_PERIOD:
            pubkeys.append(pubkey)
            balance_in_increments.append(balance)
            committee_offsets.append(i)
    later_committee_offsets = list(range(len(later_committee.pubkeys)))
    for i, pubkey, compact_validator in zip(
        later_committee_offsets, later_committee.pubkeys, later_committee.compact_validators
    ):
        index, slashed, balance = unpack_compact_validator(compact_validator)
        if epoch % LIGHT_CLIENT_COMMITTEE_PERIOD >= index % LIGHT_CLIENT_COMMITTEE_PERIOD and pubkey not in pubkeys:
            pubkeys.append(pubkey)
            balance_in_increments.append(balance)
            committee_offsets.append(i)

    return pubkeys, balance_in_increments, committee_offsets
```

## Light client state updates

The state of a light client is stored in a `memory` object of type `LightClientMemory`. To advance its state a light client requests an `update` object of type `LightClientUpdate` from the network by sending a request containing `(memory.shard, memory.header.slot, slot_range_end)` and calls `update_memory(memory, update, shard_count)` where `shard_count` is the shard count `len(beacon_state.shard_states)`.

```python
def update_memory(memory: LightClientMemory, update: LightClientUpdate, shard_count: uint64) -> None:
    # Verify the update does not skip a period
    epoch = compute_epoch_at_slot(memory.header.slot)
    current_period = epoch // LIGHT_CLIENT_COMMITTEE_PERIOD
    next_epoch = Epoch(epoch + 1)
    next_period = next_epoch // LIGHT_CLIENT_COMMITTEE_PERIOD
    assert next_period in (current_period, current_period + 1)  

    # Verify update header against shard block root and header branch
    assert is_valid_merkle_branch(
        leaf=hash_tree_root(update.header),
        branch=update.header_branch,
        depth=BEACON_CHAIN_ROOT_IN_SHARD_BLOCK_HEADER_DEPTH,
        index=BEACON_CHAIN_ROOT_IN_SHARD_BLOCK_HEADER_INDEX,
        root=update.shard_block_root,
    )

    # Verify persistent committee votes pass 2/3 threshold
    pubkeys, balance_in_increments, committee_offsets = get_persistent_committee(memory, next_epoch)
    indices = list(filter(lambda i: update.aggregation_bits[i], committee_offsets))
    assert (
        3 * sum(balance_in_increments[index] for index in indices)
    ) > 2 * sum(balance_in_increments)

    # Verify shard attestations
    pubkeys = [pubkeys[i] for i in indices]
    domain = compute_domain(DOMAIN_SHARD_COMMITTEE, update.fork_version)
    signing_root = compute_signing_root(update.shard_block_root, domain)
    assert bls.FastAggregateVerify(pubkeys, signing_root, update.signature)

    # Update period committees if entering a new period
    if next_period == current_period + 1:
        assert is_valid_merkle_branch(
            leaf=hash_tree_root(update.committee),
            branch=update.committee_branch,
            depth=PERIOD_COMMITTEE_ROOT_IN_BEACON_STATE_DEPTH + log_2(shard_count),
            index=PERIOD_COMMITTEE_ROOT_IN_BEACON_STATE_INDEX << log_2(shard_count) + memory.shard,
            root=hash_tree_root(update.header),
        )
        memory.previous_committee = memory.current_committee
        memory.current_committee = memory.next_committee
        memory.next_committee = update.committee

    # Update header
    memory.header = update.header
```

## Data overhead

Once every `LIGHT_CLIENT_COMMITTEE_PERIOD` epochs (~27 hours) a light client downloads a `LightClientUpdate` object:

* `shard_block_root`: 32 bytes
* `fork_version`: 4 bytes
* `aggregation_bits`: 16 bytes
* `signature`: 96 bytes
* `header`: 8 + 8 + 32 + 32 + 32 = 112 bytes
* `header_branch`: 4 * 32 = 128 bytes
* `committee`: 128 * (48 + 8) = 7,168 bytes
* `committee_branch`: (5 + 6) * 32 = 352 bytes

The total overhead is 7,908 bytes, or ~0.079 bytes per second. The Bitcoin SPV equivalent is 80 bytes per ~560 seconds, or ~0.143 bytes per second. Various compression optimisations (similar to [these](https://github.com/RCasatta/compressedheaders)) are possible.

A light client can choose to update the header (without updating the committee) more frequently than once every `LIGHT_CLIENT_COMMITTEE_PERIOD` epochs at a cost of 32 + 4 + 16 + 96 + 112 + 128 = 388 bytes per update.
