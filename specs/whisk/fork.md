### Fork

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
| `WHISK_FORK_VERSION` | `Version('0x05000000')` |
| `WHISK_FORK_EPOCH`   | **TBD**                 |

## Fork to WHISK

If `state.slot % SLOTS_PER_EPOCH == 0` and `compute_epoch_at_slot(state.slot) == WHISK_FORK_EPOCH`, an irregular state change is made to upgrade to Whisk. `WHISK_FORK_EPOCH` must be a multiple of `WHISK_RUN_DURATION_IN_EPOCHS`.

The upgrade occurs after the completion of the inner loop of `process_slots` that sets `state.slot` equal to `WHISK_FORK_EPOCH * SLOTS_PER_EPOCH`.

This ensures that we drop right into the beginning of the shuffling phase but without `process_whisk_epoch()` triggering for this Whisk run. Hence we handle all the setup ourselves in `upgrade_to_whisk()` below.

```python
def upgrade_to_whisk(pre: bellatrix.BeaconState) -> BeaconState:
    epoch = bellatrix.get_current_epoch(pre)
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
        inactivity_scores=pre.inactivity_Scores,
    )

    # Initialize all validators with predictable commitments
    for val_index, pre_validator in enumerate(pre.validators):
        whisk_commitment, whisk_tracker = whisk_get_initial_commitments(val_index)

        post_validator = Validator(
            pubkey=pre_validator.pubkey,
            withdrawal_credentials=pre_validator.withdrawal_credentials,
            effective_balance=pre_validator.effective_balance,
            slashed=pre_validator.slashed,
            activation_eligibility_epoch=pre_validator.activation_eligibility_epoch,
            activation_epoch=pre_validator.activation_epoch,
            exit_epoch=pre_validator.exit_epoch,
            withdrawable_epoch=pre_validator.withdrawable_epoch,
            whisk_commitment=whisk_commitment,
            whisk_tracker=whisk_tracker,
        )
        post.validators.append(post_validator)

    # Do a candidate selection followed by a proposer selection so that we have proposers for the upcoming day
    # Use an old epoch when selecting candidates so that we don't get the same seed as in the next candidate selection
    whisk_candidate_selection(post, epoch - WHISK_PROPOSER_SELECTION_GAP - 1)
    whisk_proposer_selection(post, epoch)

    # Do a final round of candidate selection. We need it so that we have something to shuffle over the upcoming shuffling phase
    whisk_candidate_selection(post, epoch)
```
