# Ethereum 2.0 Light Client Support -- From Phase 0 to Light Client Patch

**Notice**: This document is a work-in-progress for researchers and implementers.

## Table of contents

<!-- START doctoc generated TOC please keep comment here to allow auto update -->
<!-- DON'T EDIT THIS SECTION, INSTEAD RE-RUN doctoc TO UPDATE -->

- [Introduction](#introduction)
- [Configuration](#configuration)
- [Fork to Light-client patch](#fork-to-light-client-patch)
  - [Fork trigger](#fork-trigger)
  - [Upgrading the state](#upgrading-the-state)

<!-- END doctoc generated TOC please keep comment here to allow auto update -->

## Introduction

This document describes the process of moving from Phase 0 to Phase 1 of Ethereum 2.0.

## Configuration

Warning: this configuration is not definitive.

| Name | Value |
| - | - |
| `LIGHTCLIENT_PATCH_FORK_VERSION` | `Version('0x01000000')` |
| `LIGHTCLIENT_PATCH_FORK_SLOT` | `Slot(0)` **TBD** |

## Fork to Light-client patch

### Fork trigger

TBD. Social consensus, along with state conditions such as epoch boundary, finality, deposits, active validator count, etc. may be part of the decision process to trigger the fork. For now we assume the condition will be triggered at slot `LIGHTCLIENT_PATCH_FORK_SLOT`, where `LIGHTCLIENT_PATCH_FORK_SLOT % SLOTS_PER_EPOCH == 0`.

### Upgrading the state

After `process_slots` of Phase 0 finishes, if `state.slot == LIGHTCLIENT_PATCH_FORK_SLOT`, an irregular state change is made to upgrade to light-client patch.

```python
def upgrade_to_lightclient_patch(pre: phase0.BeaconState) -> BeaconState:
    epoch = get_current_epoch(pre)
    post = BeaconState(
        genesis_time=pre.genesis_time,
        genesis_validators_root=pre.genesis_validators_root,
        slot=pre.slot,
        fork=Fork(
            previous_version=pre.fork.current_version,
            current_version=LIGHTCLIENT_PATCH_FORK_VERSION,
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
        # Attestations
        previous_epoch_participation=[ValidatorFlag(0) for _ in range(len(pre.validators))],
        current_epoch_participation=[ValidatorFlag(0) for _ in range(len(pre.validators))],
        # Finality
        justification_bits=pre.justification_bits,
        previous_justified_checkpoint=pre.previous_justified_checkpoint,
        current_justified_checkpoint=pre.current_justified_checkpoint,
        finalized_checkpoint=pre.finalized_checkpoint,
    )
    # Fill in sync committees
    post.current_sync_committee = get_sync_committee(post, get_current_epoch(post))
    post.next_sync_committee = get_sync_committee(post, get_current_epoch(post) + EPOCHS_PER_SYNC_COMMITTEE_PERIOD)
    return post
```
