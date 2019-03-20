# Ethereum 2.0 Phase 1 -- Honest Validator

__NOTICE__: This document is a work-in-progress for researchers and implementers. This is an accompanying document to [Ethereum 2.0 Phase 0 -- The Beacon Chain](https://github.com/ethereum/eth2.0-specs/blob/master/specs/core/0_beacon-chain.md) that describes the expected actions of a "validator" participating in the Ethereum 2.0 protocol.

## Table of Contents

<!-- TOC -->

- [Ethereum 2.0 Phase 0 -- Honest Validator](#ethereum-20-phase-0----honest-validator)
    - [Table of Contents](#table-of-contents)
    - [Introduction](#introduction)
    - [Constants](#constants)
        - [Time parameters](#time-parameters)
    - [Crosslink data root](#crosslink-data-root)

<!-- /TOC -->

## Introduction

This document represents the expected behavior of an "honest validator" with respect to Phase 1 of the Ethereum 2.0 protocol.

## Constants

### Time parameters

| Name | Value | Unit | Duration |
| - | - | :-: | :-: |
| `CROSSLINK_LOOKBACK` | 2**5 (= 32) | slots  | 3.2 minutes |

## Crosslink data root

A node should only sign an `attestation` if `attestation.crosslink_data_root` has been reccursively verified for availability using `attestation.previous_crosslink.crosslink_data_root` up to genesis where `crosslink_data_root == ZERO_HASH`.

Let `store` be the store of observed block headers and bodies and let `get_shard_block_header(store, slot)` and `get_shard_block_body(store, slot)` return the canonical shard block header and body at the specified `slot`. The expected `get_shard_block_body` is then computed as:

```python
def compute_crosslink_data_root(state: BeaconState, store: Store) -> Bytes32:
    start_slot = state.latest_crosslinks[shard].epoch * SLOTS_PER_EPOCH + SLOTS_PER_EPOCH - CROSSLINK_LOOKBACK
    end_slot = attestation.data.slot - attestation.data.slot % SLOTS_PER_EPOCH - CROSSLINK_LOOKBACK

    headers = []
    bodies = []
    for slot in range(start_slot, end_slot):
        headers = get_shard_block_header(store, slot)
        bodies = get_shard_block_body(store, slot)

    return hash(
        merkle_root(pad_to_power_of_2([
            merkle_root_of_bytes(zpad(serialize(header), BYTES_PER_SHARD_BLOCK)) for header in headers
        ])) +
        merkle_root(pad_to_power_of_2([
                merkle_root_of_bytes(body) for body in bodies
        ]))
    )
```

using the following helpers:

```python
def is_power_of_two(value: int) -> bool:
    return (value > 0) and (value & (value - 1) == 0)

def pad_to_power_of_2(values: List[bytes]) -> List[bytes]:
    while not is_power_of_two(len(values)):
        values += [b'\x00' * BYTES_PER_SHARD_BLOCK]
    return values

def merkle_root_of_bytes(data: bytes) -> bytes:
    return merkle_root([data[i:i + 32] for i in range(0, len(data), 32)])
```
