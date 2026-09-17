# EIP-8198 -- Networking

*Note*: This document is a work-in-progress for researchers and implementers.

<!-- mdformat-toc start --slug=github --no-anchors --maxlevel=6 --minlevel=2 -->

- [Introduction](#introduction)
- [Configs](#configs)
- [Modifications in EIP-8198](#modifications-in-eip-8198)
  - [Helpers](#helpers)
    - [Modified `compute_fork_version`](#modified-compute_fork_version)
    - [Modified `compute_time_at_slot_ms`](#modified-compute_time_at_slot_ms)
    - [Modified `compute_slot_at_time_ms`](#modified-compute_slot_at_time_ms)
    - [New `get_data_column_sidecars_retention_start`](#new-get_data_column_sidecars_retention_start)
  - [The gossip domain: gossipsub](#the-gossip-domain-gossipsub)
  - [The Req/Resp domain](#the-reqresp-domain)
    - [Status v2](#status-v2)
    - [DataColumnSidecarsByRange v1](#datacolumnsidecarsbyrange-v1)
    - [DataColumnSidecarsByRoot v1](#datacolumnsidecarsbyroot-v1)

<!-- mdformat-toc end -->

## Introduction

This document contains the consensus-layer networking specifications for
EIP-8198.

The specification of these changes continues in the same format as the network
specifications of previous upgrades, and assumes them as pre-requisite.

*Note*: This specification is built upon [Heze](../../heze/p2p-interface.md).

## Configs

*[New in EIP8198]*

| Name                                            |             Value | Description                                                             |
| ----------------------------------------------- | ----------------: | ----------------------------------------------------------------------- |
| `MIN_SECONDS_FOR_DATA_COLUMN_SIDECARS_REQUESTS` | `Uint64(1572864)` | Minimum wall-clock duration of the data-column sidecar retention window |

This replaces `MIN_EPOCHS_FOR_DATA_COLUMN_SIDECARS_REQUESTS` for EIP-8198. The
value preserves the previous retention duration: 4,096 epochs of 32 slots at 12
seconds per slot on mainnet. It MUST be positive and does not change with the
slot duration. The slot timeline is used to find the epoch containing the
cutoff, rounding the retained range outward to a whole epoch.

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

```python
def compute_time_at_slot_ms(genesis_time: Uint64, slot: Slot) -> Uint64:
    """
    Return the Unix time in milliseconds at the start of ``slot``.
    """
    # [Modified in EIP8198]
    end_slot = slot
    time_ms = seconds_to_milliseconds(genesis_time)
    for entry in reversed(SLOT_DURATION_SCHEDULE):
        entry_slot = compute_start_slot_at_epoch(entry["EPOCH"])
        if entry_slot < end_slot:
            slots = end_slot - entry_slot
            time_ms += slots * entry["SLOT_DURATION_MS"]
            end_slot = entry_slot
    return time_ms
```

#### Modified `compute_slot_at_time_ms`

```python
def compute_slot_at_time_ms(genesis_time: Uint64, time_ms: Uint64) -> Slot:
    """
    Return the slot at Unix time ``time_ms``.
    """
    assert time_ms >= seconds_to_milliseconds(genesis_time)
    for entry in reversed(SLOT_DURATION_SCHEDULE):
        entry_slot = compute_start_slot_at_epoch(entry["EPOCH"])
        entry_time_ms = compute_time_at_slot_ms(genesis_time, entry_slot)
        if time_ms >= entry_time_ms:
            break
    time_diff_ms = time_ms - entry_time_ms
    slots = time_diff_ms // entry["SLOT_DURATION_MS"]
    return entry_slot + slots
```

#### New `get_data_column_sidecars_retention_start`

```python
def get_data_column_sidecars_retention_start(current_epoch: Epoch) -> Epoch:
    """
    Return the earliest epoch of the data column sidecar retention window,
    preserving its wall-clock length across slot duration changes.
    """
    window_ms = seconds_to_milliseconds(MIN_SECONDS_FOR_DATA_COLUMN_SIDECARS_REQUESTS)
    current_start_ms = compute_time_at_slot_ms(
        Uint64(0), compute_start_slot_at_epoch(current_epoch)
    )
    if current_start_ms < window_ms:
        return GENESIS_EPOCH
    window_start_ms = Uint64(current_start_ms - window_ms)
    return compute_epoch_at_slot(compute_slot_at_time_ms(Uint64(0), window_start_ms))
```

### The gossip domain: gossipsub

Each duration schedule entry after genesis MUST coincide with a network upgrade
at or after `EIP8198_FORK_EPOCH`. Clients SHOULD subscribe to the new
fork-digest topics ahead of the upgrade epoch and unsubscribe from the old
topics after it.

Durations defined in slots or epochs MUST use the piecewise timeline
(`compute_time_at_slot_ms` / `compute_slot_at_time_ms`). For example, the
gossipsub `seen_ttl` is the difference between the start times of
`current_slot + 2 * SLOTS_PER_EPOCH` and `current_slot`, converted to seconds
with `milliseconds_to_seconds`. Duty schedulers and the light-client local-clock
`current_slot` MUST also use this timeline. Durations configured in seconds,
including data-column sidecar retention, remain fixed in wall-clock time.

### The Req/Resp domain

#### Status v2

*[Modified in EIP8198]* The data-column sidecar retention period used to
interpret `earliest_available_slot` begins at
`max(get_data_column_sidecars_retention_start(current_epoch), FULU_FORK_EPOCH)`.

#### DataColumnSidecarsByRange v1

*[Modified in EIP8198]* The lower bound of `data_column_serve_range` is replaced
by
`max(get_data_column_sidecars_retention_start(current_epoch), FULU_FORK_EPOCH)`.
Clients MUST keep and serve sidecars throughout this range.

#### DataColumnSidecarsByRoot v1

*[Modified in EIP8198]* `minimum_request_epoch` is replaced by
`max(get_data_column_sidecars_retention_start(current_epoch), FULU_FORK_EPOCH)`.
The permission to return `ResourceUnavailable` for older blocks applies to this
lower bound.
