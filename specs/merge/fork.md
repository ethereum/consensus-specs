# The Merge -- Fork Logic

**Notice**: This document is a work-in-progress for researchers and implementers.

## Table of contents

<!-- START doctoc generated TOC please keep comment here to allow auto update -->
<!-- DON'T EDIT THIS SECTION, INSTEAD RE-RUN doctoc TO UPDATE -->

- [Introduction](#introduction)
- [Configuration](#configuration)
- [Fork to Merge](#fork-to-merge)
  - [Fork trigger](#fork-trigger)
  - [Upgrading the state](#upgrading-the-state)
  - [Initializing transition store](#initializing-transition-store)

<!-- END doctoc generated TOC please keep comment here to allow auto update -->

## Introduction

This document describes the process of the Merge upgrade.

## Configuration

Warning: this configuration is not definitive.

| Name | Value |
| - | - |
| `MERGE_FORK_VERSION` | `Version('0x02000000')` |
| `MERGE_FORK_EPOCH` | `Epoch(18446744073709551615)` **TBD** |
| `MIN_ANCHOR_POW_BLOCK_DIFFICULTY` | **TBD** |
| `TARGET_SECONDS_TO_MERGE` | `uint64(7 * 86400)` = (604,800) |

## Fork to Merge

### Fork trigger

TBD. Social consensus, along with state conditions such as epoch boundary, finality, deposits, active validator count, etc. may be part of the decision process to trigger the fork. For now we assume the condition will be triggered at epoch `MERGE_FORK_EPOCH`.

Since the Merge transition process relies on `Eth1Data` in the beacon state we do want to make sure that this data is fresh. This is achieved by forcing `MERGE_FORK_EPOCH` to point to eth1 voting period boundary, i.e. `MERGE_FORK_EPOCH` should satisfy the following condition `MERGE_FORK_EPOCH % EPOCHS_PER_ETH1_VOTING_PERIOD == 0`.

Note that for the pure Merge networks, we don't apply `upgrade_to_merge` since it starts with Merge version logic.

### Upgrading the state

As with the Phase0-to-Altair upgrade, the `state_transition` is modified to upgrade the `BeaconState`.
The `BeaconState` upgrade runs as part of `process_slots`, slots with missing block proposals do not affect the upgrade time.

If `state.slot % SLOTS_PER_EPOCH == 0` and `compute_epoch_at_slot(state.slot) == MERGE_FORK_EPOCH`, an irregular state change is made to upgrade to Merge.
The upgrade occurs after the completion of the inner loop of `process_slots` that sets `state.slot` equal to `MERGE_FORK_EPOCH * SLOTS_PER_EPOCH`.

When multiple upgrades are scheduled for the same epoch (common for test-networks),
all the upgrades run in sequence before resuming the regular state transition.

```python
def upgrade_to_merge(pre: altair.BeaconState) -> BeaconState:
    epoch = altair.get_current_epoch(pre)
    post = BeaconState(
        # Versioning
        genesis_time=pre.genesis_time,
        genesis_validators_root=pre.genesis_validators_root,
        slot=pre.slot,
        fork=Fork(
            previous_version=pre.fork.current_version,
            current_version=MERGE_FORK_VERSION,
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

### Initializing transition store

If `state.slot % SLOTS_PER_EPOCH == 0` and `compute_epoch_at_slot(state.slot) == MERGE_FORK_EPOCH`, a transition store is initialized to be further utilized by the transition process of the Merge.

Transition store initialization occurs after the state has been modified by corresponding `upgrade_to_merge` function.

```python
def compute_transition_total_difficulty(anchor_pow_block: PowBlock) -> uint256:
    seconds_per_voting_period = EPOCHS_PER_ETH1_VOTING_PERIOD * SLOTS_PER_EPOCH * SECONDS_PER_SLOT
    pow_blocks_per_voting_period = seconds_per_voting_period // SECONDS_PER_ETH1_BLOCK
    pow_blocks_to_merge = TARGET_SECONDS_TO_MERGE // SECONDS_PER_ETH1_BLOCK
    pow_blocks_after_anchor_block = ETH1_FOLLOW_DISTANCE + pow_blocks_per_voting_period + pow_blocks_to_merge
    anchor_difficulty = max(MIN_ANCHOR_POW_BLOCK_DIFFICULTY, anchor_pow_block.difficulty)

    return anchor_pow_block.total_difficulty + anchor_difficulty * pow_blocks_after_anchor_block


def get_transition_store(anchor_pow_block: PowBlock) -> TransitionStore:
    transition_total_difficulty = compute_transition_total_difficulty(anchor_pow_block)
    return TransitionStore(transition_total_difficulty=transition_total_difficulty)


def initialize_transition_store(state: BeaconState) -> TransitionStore:
    pow_block = get_pow_block(state.eth1_data.block_hash)
    return get_transition_store(pow_block)
```
