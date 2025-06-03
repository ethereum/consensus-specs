# EIP-7441 -- Fork Logic

*Note*: This document is a work-in-progress for researchers and implementers.

<!-- mdformat-toc start --slug=github --no-anchors --maxlevel=6 --minlevel=2 -->

- [Introduction](#introduction)
- [Configuration](#configuration)
- [Fork to EIP-7441](#fork-to-eip-7441)

<!-- mdformat-toc end -->

## Introduction

This document describes the process of the EIP-7441 upgrade.

```
"""
EIP7441_FORK_EPOCH
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

| Name                   | Value                                 |
| ---------------------- | ------------------------------------- |
| `EIP7441_FORK_VERSION` | `Version('0x08000000')`               |
| `EIP7441_FORK_EPOCH`   | `Epoch(18446744073709551615)` **TBD** |

## Fork to EIP-7441

If `state.slot % SLOTS_PER_EPOCH == 0` and
`compute_epoch_at_slot(state.slot) == EIP7441_FORK_EPOCH`, an irregular state
change is made to upgrade to Whisk. `EIP7441_FORK_EPOCH` must be a multiple of
`RUN_DURATION_IN_EPOCHS`.

The upgrade occurs after the completion of the inner loop of `process_slots`
that sets `state.slot` equal to `EIP7441_FORK_EPOCH * SLOTS_PER_EPOCH`.

This ensures that we drop right into the beginning of the shuffling phase but
without `process_whisk_epoch()` triggering for this Whisk run. Hence we handle
all the setup ourselves in `upgrade_to_whisk()` below.

```python
def upgrade_to_eip7441(pre: capella.BeaconState) -> BeaconState:
    # Compute initial unsafe trackers for all validators
    ks = [
        get_initial_whisk_k(ValidatorIndex(validator_index), 0)
        for validator_index in range(len(pre.validators))
    ]
    whisk_k_commitments = [get_k_commitment(k) for k in ks]
    whisk_trackers = [get_initial_tracker(k) for k in ks]

    epoch = get_current_epoch(pre)
    post = BeaconState(
        genesis_time=pre.genesis_time,
        genesis_validators_root=pre.genesis_validators_root,
        slot=pre.slot,
        fork=Fork(
            previous_version=pre.fork.current_version,
            current_version=EIP7441_FORK_VERSION,
            epoch=epoch,
        ),
        latest_block_header=pre.latest_block_header,
        block_roots=pre.block_roots,
        state_roots=pre.state_roots,
        historical_roots=pre.historical_roots,
        eth1_data=pre.eth1_data,
        eth1_data_votes=pre.eth1_data_votes,
        eth1_deposit_index=pre.eth1_deposit_index,
        validators=[],
        balances=pre.balances,
        randao_mixes=pre.randao_mixes,
        slashings=pre.slashings,
        previous_epoch_participation=pre.previous_epoch_participation,
        current_epoch_participation=pre.current_epoch_participation,
        justification_bits=pre.justification_bits,
        previous_justified_checkpoint=pre.previous_justified_checkpoint,
        current_justified_checkpoint=pre.current_justified_checkpoint,
        finalized_checkpoint=pre.finalized_checkpoint,
        inactivity_scores=pre.inactivity_scores,
        current_sync_committee=pre.current_sync_committee,
        next_sync_committee=pre.next_sync_committee,
        latest_execution_payload_header=pre.latest_execution_payload_header,
        next_withdrawal_index=pre.next_withdrawal_index,
        next_withdrawal_validator_index=pre.next_withdrawal_validator_index,
        historical_summaries=pre.historical_summaries,
        # [New in EIP7441]
        whisk_proposer_trackers=[WhiskTracker() for _ in range(PROPOSER_TRACKERS_COUNT)],
        # [New in EIP7441]
        whisk_candidate_trackers=[WhiskTracker() for _ in range(CANDIDATE_TRACKERS_COUNT)],
        # [New in EIP7441]
        whisk_trackers=whisk_trackers,
        # [New in EIP7441]
        whisk_k_commitments=whisk_k_commitments,
    )

    # Do a candidate selection followed by a proposer selection so that we have proposers for the upcoming day
    # Use an old epoch when selecting candidates so that we don't get the same seed as in the next candidate selection
    select_whisk_candidate_trackers(post, Epoch(saturating_sub(epoch, PROPOSER_SELECTION_GAP + 1)))
    select_whisk_proposer_trackers(post, epoch)

    # Do a final round of candidate selection.
    # We need it so that we have something to shuffle over the upcoming shuffling phase.
    select_whisk_candidate_trackers(post, epoch)

    return post
```
