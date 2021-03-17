# Ethereum 2.0 Altair fork

**Notice**: This document is a work-in-progress for researchers and implementers.

## Table of contents

<!-- START doctoc generated TOC please keep comment here to allow auto update -->
<!-- DON'T EDIT THIS SECTION, INSTEAD RE-RUN doctoc TO UPDATE -->

- [Introduction](#introduction)
- [Configuration](#configuration)
- [Fork to Altair](#fork-to-altair)
  - [Fork trigger](#fork-trigger)
  - [Upgrading the state](#upgrading-the-state)

<!-- END doctoc generated TOC please keep comment here to allow auto update -->

## Introduction

This document describes the process of the first upgrade of Ethereum 2.0: the Altair hard fork, introducing light client support and other improvements.

## Configuration

Warning: this configuration is not definitive.

| Name | Value |
| - | - |
| `ALTAIR_FORK_VERSION` | `Version('0x01000000')` |
| `ALTAIR_FORK_SLOT` | `Slot(0)` **TBD** |

## Fork to Altair

### Fork trigger

TBD. Social consensus, along with state conditions such as epoch boundary, finality, deposits, active validator count, etc. may be part of the decision process to trigger the fork. For now we assume the condition will be triggered at slot `ALTAIR_FORK_SLOT`, where `ALTAIR_FORK_SLOT % SLOTS_PER_EPOCH == 0`.

### Upgrading the state

After `process_slots` of Phase 0 finishes, if `state.slot == ALTAIR_FORK_SLOT`, an irregular state change is made to upgrade to Altair.

```python
def upgrade_to_altair(pre: phase0.BeaconState) -> BeaconState:
    epoch = get_current_epoch(pre)
    post = BeaconState(
        # Versioning
        genesis_time=pre.genesis_time,
        genesis_validators_root=pre.genesis_validators_root,
        slot=pre.slot,
        fork=Fork(
            previous_version=pre.fork.current_version,
            current_version=ALTAIR_FORK_VERSION,
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
        previous_epoch_participation=[ParticipationFlags(0b0000_0000) for _ in range(len(pre.validators))],
        current_epoch_participation=[ParticipationFlags(0b0000_0000) for _ in range(len(pre.validators))],
        # Finality
        justification_bits=pre.justification_bits,
        previous_justified_checkpoint=pre.previous_justified_checkpoint,
        current_justified_checkpoint=pre.current_justified_checkpoint,
        finalized_checkpoint=pre.finalized_checkpoint,
        # Inactivity
        inactivity_scores=[0 for _ in range(len(pre.validators))],
    )
    # Fill in sync committees
    post.current_sync_committee = get_sync_committee(post, get_current_epoch(post))
    post.next_sync_committee = get_sync_committee(post, get_current_epoch(post) + EPOCHS_PER_SYNC_COMMITTEE_PERIOD)
    return post
```
