# Whisk -- Fork Logic

**Notice**: This document is a work-in-progress for researchers and implementers.

## Table of contents

<!-- TOC -->
<!-- START doctoc generated TOC please keep comment here to allow auto update -->
<!-- DON'T EDIT THIS SECTION, INSTEAD RE-RUN doctoc TO UPDATE -->

- [Introduction](#introduction)
- [Configuration](#configuration)
- [Fork to Whisk](#fork-to-whisk)

<!-- END doctoc generated TOC please keep comment here to allow auto update -->
<!-- /TOC -->

## Introduction

This document describes the process of Whisk upgrade.


```
"""
    WHISK_FORK_EPOCH
        |                     cooldown
        |                     | ||
        v                     vsvv
      --+~~~~~~~~~~~~~~~~~~~~~----+-
               shuffling          ^
                                  |
                                  |
                         proposer selection
                        candidate selection
"""
```

## Configuration

Warning: this configuration is not definitive.

| Name                 | Value                   |
| -------------------- | ----------------------- |
| `WHISK_FORK_VERSION` | `Version('0x08000000')` |
| `WHISK_FORK_EPOCH`   | `Epoch(18446744073709551615)` **TBD** |

## Fork to Whisk

If `state.slot % SLOTS_PER_EPOCH == 0` and `compute_epoch_at_slot(state.slot) == WHISK_FORK_EPOCH`, an irregular state change is made to upgrade to Whisk. `WHISK_FORK_EPOCH` must be a multiple of `WHISK_RUN_DURATION_IN_EPOCHS`.

The upgrade occurs after the completion of the inner loop of `process_slots` that sets `state.slot` equal to `WHISK_FORK_EPOCH * SLOTS_PER_EPOCH`.

This ensures that we drop right into the beginning of the shuffling phase but without `process_whisk_epoch()` triggering for this Whisk run. Hence we handle all the setup ourselves in `upgrade_to_whisk()` below.

```python
def upgrade_to_whisk(pre: capella.BeaconState) -> BeaconState:
    # Compute initial unsafe trackers for all validators
    ks = [get_initial_whisk_k(ValidatorIndex(validator_index), 0) for validator_index in range(len(pre.validators))]
    whisk_k_commitments = [get_k_commitment(k) for k in ks]
    whisk_trackers = [get_initial_tracker(k) for k in ks]

    epoch = get_current_epoch(pre)
    post = BeaconState(
        # Versioning
        genesis_time=pre.genesis_time,
        genesis_validators_root=pre.genesis_validators_root,
        slot=pre.slot,
        fork=Fork(
            previous_version=pre.fork.current_version,
            current_version=WHISK_FORK_VERSION,
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
        validators=[],
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
        latest_execution_payload_header=pre.latest_execution_payload_header,
        # Withdrawals
        next_withdrawal_index=pre.next_withdrawal_index,
        next_withdrawal_validator_index=pre.next_withdrawal_validator_index,
        # Deep history valid from Capella onwards
        historical_summaries=pre.historical_summaries,
        # Whisk
        whisk_proposer_trackers=[WhiskTracker() for _ in range(WHISK_PROPOSER_TRACKERS_COUNT)],  # [New in Whisk]
        whisk_candidate_trackers=[WhiskTracker() for _ in range(WHISK_CANDIDATE_TRACKERS_COUNT)],  # [New in Whisk]
        whisk_trackers=whisk_trackers,  # [New in Whisk]
        whisk_k_commitments=whisk_k_commitments,  # [New in Whisk]
    )

    # Do a candidate selection followed by a proposer selection so that we have proposers for the upcoming day
    # Use an old epoch when selecting candidates so that we don't get the same seed as in the next candidate selection
    select_whisk_candidate_trackers(post, Epoch(saturating_sub(epoch, WHISK_PROPOSER_SELECTION_GAP + 1)))
    select_whisk_proposer_trackers(post, epoch)

    # Do a final round of candidate selection.
    # We need it so that we have something to shuffle over the upcoming shuffling phase.
    select_whisk_candidate_trackers(post, epoch)

    return post
```
