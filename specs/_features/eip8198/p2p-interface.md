# EIP-8198 -- Networking

*Note*: This document is a work-in-progress for researchers and implementers.

<!-- mdformat-toc start --slug=github --no-anchors --maxlevel=6 --minlevel=2 -->

- [Introduction](#introduction)
- [Modifications in EIP-8198](#modifications-in-eip-8198)
  - [Helpers](#helpers)
    - [Modified `compute_fork_version`](#modified-compute_fork_version)
    - [Modified `compute_time_at_slot_ms`](#modified-compute_time_at_slot_ms)
    - [New `get_data_column_sidecars_retention_start`](#new-get_data_column_sidecars_retention_start)
  - [The gossip domain: gossipsub](#the-gossip-domain-gossipsub)
    - [Topics and messages](#topics-and-messages)
      - [Global topics](#global-topics)
        - [Modified `execution_payload_bid`](#modified-execution_payload_bid)
  - [The Req/Resp domain](#the-reqresp-domain)

<!-- mdformat-toc end -->

## Introduction

This document contains the consensus-layer networking specifications for
EIP-8198.

The specification of these changes continues in the same format as the network
specifications of previous upgrades, and assumes them as pre-requisite.

*Note*: This specification is built upon [Heze](../../heze/p2p-interface.md).

## Modifications in EIP-8198

### Helpers

#### Modified `compute_fork_version`

```python
def compute_fork_version(epoch: Epoch) -> Version:
    """
    Return the fork version at the given ``epoch``.
    """
    if epoch >= EIP8198_FORK_EPOCH:
        return EIP8198_FORK_VERSION
    if epoch >= HEZE_FORK_EPOCH:
        return HEZE_FORK_VERSION
    if epoch >= GLOAS_FORK_EPOCH:
        return GLOAS_FORK_VERSION
    if epoch >= FULU_FORK_EPOCH:
        return FULU_FORK_VERSION
    if epoch >= ELECTRA_FORK_EPOCH:
        return ELECTRA_FORK_VERSION
    if epoch >= DENEB_FORK_EPOCH:
        return DENEB_FORK_VERSION
    if epoch >= CAPELLA_FORK_EPOCH:
        return CAPELLA_FORK_VERSION
    if epoch >= BELLATRIX_FORK_EPOCH:
        return BELLATRIX_FORK_VERSION
    if epoch >= ALTAIR_FORK_EPOCH:
        return ALTAIR_FORK_VERSION
    return GENESIS_FORK_VERSION
```

#### Modified `compute_time_at_slot_ms`

*Note*: The gossip slot gates `is_not_from_future_slot` and
`is_within_slot_range` are defined in terms of this function and inherit the
piecewise timeline without further changes.

```python
def compute_time_at_slot_ms(state: BeaconState, slot: Slot) -> Uint64:
    """
    Return the time in milliseconds at the start of the given slot.
    """
    # [Modified in EIP8198]
    return compute_slot_start_time_ms(state.genesis_time, slot)
```

#### New `get_data_column_sidecars_retention_start`

```python
def get_data_column_sidecars_retention_start(current_epoch: Epoch) -> Epoch:
    """
    Return the earliest epoch of the data column sidecar retention window at
    ``current_epoch``, preserving the window's pre-schedule wall-clock
    length across slot duration changes.
    """
    window_ms = MIN_EPOCHS_FOR_DATA_COLUMN_SIDECARS_REQUESTS * SLOTS_PER_EPOCH * SLOT_DURATION_MS
    current_start_ms = compute_slot_start_time_ms(
        Uint64(0), compute_start_slot_at_epoch(current_epoch)
    )
    if current_start_ms < window_ms:
        return GENESIS_EPOCH
    window_start_ms = Uint64(current_start_ms - window_ms)
    return compute_epoch_at_slot(compute_slot_at_time_ms(Uint64(0), window_start_ms))
```

### The gossip domain: gossipsub

EIP-8198 adds no message types and modifies no gossip validation conditions
beyond those noted below. All topics carry over from Heze, re-keyed under the
EIP-8198 fork digest (derived from `EIP8198_FORK_VERSION` via the modified
`compute_fork_version`). As with previous upgrades, clients SHOULD subscribe to
the new-digest topics ahead of the fork epoch and unsubscribe from the
old-digest topics after it.

The interpretation of time-sensitive networking parameters under a slot duration
change is as follows:

- `ATTESTATION_PROPAGATION_SLOT_RANGE` remains `32` slots (one epoch plus
  margin); its wall-clock duration scales with the slot duration.
- `MAXIMUM_GOSSIP_CLOCK_DISPARITY` is an absolute wall-clock allowance and is
  not rescaled.
- The gossipsub `seen_ttl` parameter (seconds) becomes
  `compute_slot_range_duration_ms(current_slot, Slot(current_slot + 2 * SLOTS_PER_EPOCH)) // 1000`,
  covering two epochs also when the window crosses a duration change.

All other slot-derived durations — schedulers, expiry windows, gossip-scoring
windows, and the light-client local-clock `current_slot` — MUST be derived from
the piecewise timeline (`compute_slot_start_time_ms` /
`compute_slot_at_time_ms`) rather than from a fixed slot duration anchored at
genesis. The inherited `bls_to_execution_change` epoch gate keeps its
pre-schedule slot computation; it is provably unaffected, since schedule entries
lie far beyond `CAPELLA_FORK_EPOCH`.

#### Topics and messages

##### Global topics

###### Modified `execution_payload_bid`

The gas-limit _[IGNORE]_ condition is replaced with the following, where
`parent_execution_payload_slot` is the slot of the beacon block associated with
the known execution payload identified by `bid.parent_block_hash`:

- _[IGNORE]_ `bid.parent_block_hash` is the block hash of a known execution
  payload in fork choice and
  `is_gas_limit_transition_compatible(parent_gas_limit, bid.gas_limit, proposer_preferences.target_gas_limit, parent_execution_payload_slot, bid.slot)`
  is `True` where `parent_gas_limit` is the `gas_limit` of that execution
  payload.

*Note*: The transition condition is keyed to the slot of the parent execution
payload, not the parent beacon block, so the one-time scaling cannot be bypassed
by missed slots or withheld payloads around a duration change. This mirrors the
execution-layer gas-limit rule of EIP-8198; if the execution layer adopts a
different policy at the transition, this check changes accordingly.

```python
def is_gas_limit_transition_compatible(
    parent_gas_limit: Uint64,
    gas_limit: Uint64,
    target_gas_limit: Uint64,
    parent_execution_payload_slot: Slot,
    bid_slot: Slot,
) -> bool:
    """
    Check the bid gas limit, including the one-time scaling at a slot
    duration change.
    """
    parent_duration_ms = get_slot_duration_ms(compute_epoch_at_slot(parent_execution_payload_slot))
    bid_duration_ms = get_slot_duration_ms(compute_epoch_at_slot(bid_slot))
    if parent_duration_ms != bid_duration_ms:
        return gas_limit == parent_gas_limit * bid_duration_ms // parent_duration_ms
    return is_gas_limit_target_compatible(parent_gas_limit, gas_limit, target_gas_limit)
```

### The Req/Resp domain

Request and response message types are unchanged from Heze. In the inherited
data-column sidecar request validations and pruning guidance,
`get_data_column_sidecars_retention_start(current_epoch)` replaces the rolling
`current_epoch - MIN_EPOCHS_FOR_DATA_COLUMN_SIDECARS_REQUESTS` term; the
inherited `FULU_FORK_EPOCH` floor is unchanged. This preserves the window's
wall-clock length across slot duration changes, so a node retaining the
inherited window when a change activates never serves a shorter wall-clock
history, without pre-change over-retention or backfill. The blob sidecar
Req/Resp messages are already deprecated as of
`FULU_FORK_EPOCH + MIN_EPOCHS_FOR_BLOB_SIDECARS_REQUESTS`, so their retention
window needs no treatment.

Epoch-denominated retention windows without a wall-clock target — in particular
the block retention window `compute_min_epochs_for_block_requests()` — keep
their epoch counts, and their wall-clock spans scale with the slot duration. The
Req/Resp timeouts (`TTFB_TIMEOUT`, `RESP_TIMEOUT`) are absolute wall-clock
allowances and are not rescaled.
