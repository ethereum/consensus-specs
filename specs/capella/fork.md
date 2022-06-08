# Capella -- Fork Logic

## Table of contents

<!-- START doctoc generated TOC please keep comment here to allow auto update -->
<!-- DON'T EDIT THIS SECTION, INSTEAD RE-RUN doctoc TO UPDATE -->

- [Introduction](#introduction)
- [Configuration](#configuration)
- [Fork to Capella](#fork-to-capella)
  - [Fork trigger](#fork-trigger)
  - [Upgrading the state](#upgrading-the-state)

<!-- END doctoc generated TOC please keep comment here to allow auto update -->

## Introduction

This document describes the process of the Capella upgrade.

## Configuration

Warning: this configuration is not definitive.

| Name | Value |
| - | - |
| `CAPELLA_FORK_VERSION` | `Version('0x03000000')` |
| `CAPELLA_FORK_EPOCH` | `Epoch(18446744073709551615)` **TBD** |


## Fork to Capella

### Fork trigger

The fork is triggered at epoch `CAPELLA_FORK_EPOCH`.

Note that for the pure Capella networks, we don't apply `upgrade_to_capella` since it starts with Capella version logic.

### Upgrading the state

If `state.slot % SLOTS_PER_EPOCH == 0` and `compute_epoch_at_slot(state.slot) == CAPELLA_FORK_EPOCH`,
an irregular state change is made to upgrade to Capella.

The upgrade occurs after the completion of the inner loop of `process_slots` that sets `state.slot` equal to `CAPELLA_FORK_EPOCH * SLOTS_PER_EPOCH`.
Care must be taken when transitioning through the fork boundary as implementations will need a modified [state transition function](../phase0/beacon-chain.md#beacon-chain-state-transition-function) that deviates from the Phase 0 document.
In particular, the outer `state_transition` function defined in the Phase 0 document will not expose the precise fork slot to execute the upgrade in the presence of skipped slots at the fork boundary. Instead the logic must be within `process_slots`.

```python
def upgrade_to_capella(pre: bellatrix.BeaconState) -> BeaconState:
    epoch = bellatrix.get_current_epoch(pre)
    post = BeaconState(
        # Versioning
        genesis_time=pre.genesis_time,
        genesis_validators_root=pre.genesis_validators_root,
        slot=pre.slot,
        fork=Fork(
            previous_version=pre.fork.current_version,
            current_version=CAPELLA_FORK_VERSION,
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
        withdrawal_queue=[],
        next_withdrawal_index=WithdrawalIndex(0),
        next_partial_withdrawal_validator_index=ValidatorIndex(0),
    )

    for pre_validator in pre.validators:
        post_validator = Validator(
            pubkey=pre_validator.pubkey,
            withdrawal_credentials=pre_validator.withdrawal_credentials,
            effective_balance=pre_validator.effective_balance,
            slashed=pre_validator.slashed,
            activation_eligibility_epoch=pre_validator.activation_eligibility_epoch,
            activation_epoch=pre_validator.activation_epoch,
            exit_epoch=pre_validator.exit_epoch,
            withdrawable_epoch=pre_validator.withdrawable_epoch,
            fully_withdrawn_epoch=FAR_FUTURE_EPOCH,
        )
        post.validators.append(post_validator)

    return post
```
