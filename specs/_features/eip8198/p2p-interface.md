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
  - [The Req/Resp domain](#the-reqresp-domain)
    - [Modified `DataColumnSidecarsByRange`](#modified-datacolumnsidecarsbyrange)
    - [Modified `DataColumnSidecarsByRoot`](#modified-datacolumnsidecarsbyroot)

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

*Note*: The gossip slot gates `is_future_slot` and `is_within_slot_range` are
defined in terms of this function and inherit the piecewise timeline without
further changes.

```python
def compute_time_at_slot_ms(store: Store, slot: Slot) -> Uint64:
    """
    Return the time in milliseconds at the start of the given slot.
    """
    # [Modified in EIP8198]
    return compute_slot_start_time_ms(store.genesis_time, slot)
```

#### New `get_data_column_sidecars_retention_start`

```python
def get_data_column_sidecars_retention_start(current_epoch: Epoch) -> Epoch:
    """
    Return the earliest epoch of the data column sidecar retention window,
    preserving its wall-clock length across slot duration changes.
    """
    window_ms = (
        Uint64(MIN_EPOCHS_FOR_DATA_COLUMN_SIDECARS_REQUESTS)
        * SLOTS_PER_EPOCH
        * get_slot_duration_ms(GENESIS_EPOCH)
    )
    current_start_ms = compute_slot_start_time_ms(
        Uint64(0), compute_start_slot_at_epoch(current_epoch)
    )
    if current_start_ms < window_ms:
        return GENESIS_EPOCH
    window_start_ms = Uint64(current_start_ms - window_ms)
    return compute_epoch_at_slot(compute_slot_at_time_ms(Uint64(0), window_start_ms))
```

### The gossip domain: gossipsub

Slot timing changes coincide with network upgrades. Clients SHOULD subscribe to
the new fork-digest topics ahead of the upgrade epoch and unsubscribe from the
old topics after it.

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
genesis.

### The Req/Resp domain

#### Modified `DataColumnSidecarsByRange`

The lower bound of `data_column_serve_range` is replaced by
`max(get_data_column_sidecars_retention_start(current_epoch), FULU_FORK_EPOCH)`.
Clients MUST keep and serve sidecars throughout this range.

#### Modified `DataColumnSidecarsByRoot`

`minimum_request_epoch` is replaced by
`max(get_data_column_sidecars_retention_start(current_epoch), FULU_FORK_EPOCH)`.
The permission to return `ResourceUnavailable` for older blocks applies to this
lower bound.
