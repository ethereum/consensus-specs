# Bellatrix -- Fork Logic

## Table of contents

<!-- mdformat-toc start --slug=github --no-anchors --maxlevel=6 --minlevel=2 -->

- [Introduction](#introduction)
- [Configuration](#configuration)
- [Helper functions](#helper-functions)
  - [Misc](#misc)
    - [Modified `compute_fork_version`](#modified-compute_fork_version)
- [Fork to Bellatrix](#fork-to-bellatrix)
  - [Fork trigger](#fork-trigger)
  - [Upgrading the state](#upgrading-the-state)

<!-- mdformat-toc end -->

## Introduction

This document describes the process of Bellatrix upgrade.

## Configuration

| Name | Value |
| - | - |
| `BELLATRIX_FORK_VERSION` | `Version('0x02000000')` |
| `BELLATRIX_FORK_EPOCH` | `Epoch(144896)` (Sept 6, 2022, 11:34:47am UTC) |

## Helper functions

### Misc

#### Modified `compute_fork_version`

```python
def compute_fork_version(epoch: Epoch) -> Version:
    """
    Return the fork version at the given ``epoch``.
    """
    if epoch >= BELLATRIX_FORK_EPOCH:
        return BELLATRIX_FORK_VERSION
    if epoch >= ALTAIR_FORK_EPOCH:
        return ALTAIR_FORK_VERSION
    return GENESIS_FORK_VERSION
```

## Fork to Bellatrix

### Fork trigger

TBD. Social consensus, along with state conditions such as epoch boundary, finality, deposits, active validator count, etc. may be part of the decision process to trigger the fork. For now we assume the condition will be triggered at epoch `BELLATRIX_FORK_EPOCH`.

Note that for the pure Bellatrix networks, we don't apply `upgrade_to_bellatrix` since it starts with Bellatrix version logic.

### Upgrading the state

As with the Phase0-to-Altair upgrade, the `state_transition` is modified to upgrade the `BeaconState`.
The `BeaconState` upgrade runs as part of `process_slots`, slots with missing block proposals do not affect the upgrade time.

If `state.slot % SLOTS_PER_EPOCH == 0` and `compute_epoch_at_slot(state.slot) == BELLATRIX_FORK_EPOCH`, an irregular state change is made to upgrade to Bellatrix.
The upgrade occurs after the completion of the inner loop of `process_slots` that sets `state.slot` equal to `BELLATRIX_FORK_EPOCH * SLOTS_PER_EPOCH`.

When multiple upgrades are scheduled for the same epoch (common for test-networks),
all the upgrades run in sequence before resuming the regular state transition.

```python
def upgrade_to_bellatrix(pre: altair.BeaconState) -> BeaconState:
    epoch = altair.get_current_epoch(pre)
    post = BeaconState(
        # Versioning
        genesis_time=pre.genesis_time,
        genesis_validators_root=pre.genesis_validators_root,
        slot=pre.slot,
        fork=Fork(
            previous_version=pre.fork.current_version,
            current_version=BELLATRIX_FORK_VERSION,
            epoch=epoch,
        ),
        # History
        latest_block_header=pre.latest_block_header,
        block_roots=pre.block_roots,
        state_roots=pre.state_roots,
        historical_roots=pre.historical_roots,
        # Eth1
        eth1_data=pre.eth1_data,
        eth1_data_votes=pre.eth1_data_votes,
        eth1_deposit_index=pre.eth1_deposit_index,
        # Registry
        validators=pre.validators,
        balances=pre.balances,
        # Randomness
        randao_mixes=pre.randao_mixes,
        # Slashings
        slashings=pre.slashings,
        # Participation
        previous_epoch_participation=pre.previous_epoch_participation,
        current_epoch_participation=pre.current_epoch_participation,
        # Finality
        justification_bits=pre.justification_bits,
        previous_justified_checkpoint=pre.previous_justified_checkpoint,
        current_justified_checkpoint=pre.current_justified_checkpoint,
        finalized_checkpoint=pre.finalized_checkpoint,
        # Inactivity
        inactivity_scores=pre.inactivity_scores,
        # Sync
        current_sync_committee=pre.current_sync_committee,
        next_sync_committee=pre.next_sync_committee,
        # Execution-layer
        latest_execution_payload_header=ExecutionPayloadHeader(),
    )

    return post
```
