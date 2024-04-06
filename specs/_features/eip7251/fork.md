# EIP7251 -- Fork Logic

**Notice**: This document is a work-in-progress for researchers and implementers.

## Table of contents

<!-- START doctoc generated TOC please keep comment here to allow auto update -->
<!-- DON'T EDIT THIS SECTION, INSTEAD RE-RUN doctoc TO UPDATE -->

- [Introduction](#introduction)
- [Configuration](#configuration)
- [Helper functions](#helper-functions)
  - [Misc](#misc)
    - [Modified `compute_fork_version`](#modified-compute_fork_version)
- [Fork to EIP7251](#fork-to-eip7251)
  - [Fork trigger](#fork-trigger)
  - [Upgrading the state](#upgrading-the-state)

<!-- END doctoc generated TOC please keep comment here to allow auto update -->

## Introduction

This document describes the process of the EIP7251 upgrade.

## Configuration

Warning: this configuration is not definitive.

| Name | Value |
| - | - |
| `EIP7251_FORK_VERSION` | `Version('0x06000000')` |
| `EIP7251_FORK_EPOCH` | `Epoch(18446744073709551615)` **TBD** |

## Helper functions

### Misc

#### Modified `compute_fork_version`

```python
def compute_fork_version(epoch: Epoch) -> Version:
    """
    Return the fork version at the given ``epoch``.
    """
    if epoch >= EIP7251_FORK_EPOCH:
        return EIP7251_FORK_VERSION
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

## Fork to EIP7251

### Fork trigger

TBD. This fork is defined for testing purposes, the EIP may be combined with other consensus-layer upgrade.
For now, we assume the condition will be triggered at epoch `EIP7251_FORK_EPOCH`.

Note that for the pure EIP7251 networks, we don't apply `upgrade_to_eip7251` since it starts with EIP7251 version logic.

### Upgrading the state

If `state.slot % SLOTS_PER_EPOCH == 0` and `compute_epoch_at_slot(state.slot) == EIP7251_FORK_EPOCH`,
an irregular state change is made to upgrade to EIP7251.

```python
def upgrade_to_eip7251(pre: deneb.BeaconState) -> BeaconState:
    post = BeaconState(
        # Versioning
        genesis_time=pre.genesis_time,
        genesis_validators_root=pre.genesis_validators_root,
        slot=pre.slot,
        fork=Fork(
            previous_version=pre.fork.current_version,
            current_version=EIP7251_FORK_VERSION,
            epoch=deneb.get_current_epoch(pre),
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
        latest_execution_payload_header=pre.latest_execution_payload_header,
        # Withdrawals
        next_withdrawal_index=pre.next_withdrawal_index,
        next_withdrawal_validator_index=pre.next_withdrawal_validator_index,
        # Deep history valid from Capella onwards
        historical_summaries=pre.historical_summaries,
        # [New in EIP7251] 
        deposit_balance_to_consume=0,
        exit_balance_to_consume=get_activation_exit_churn_limit(pre),
        earliest_exit_epoch=max([v.exit_epoch for v in pre.validators if v.exit_epoch != FAR_FUTURE_EPOCH]) + 1,
        consolidation_balance_to_consume=get_consolidation_churn_limit(pre),
        earliest_consolidation_epoch=compute_activation_exit_epoch(get_current_epoch(pre)),
        pending_balance_deposits=[],
        pending_partial_withdrawals=[],
        pending_consolidations=[],
    )

    # Ensure early adopters of compounding credentials go through the activation churn
    for index, validator in enumerate(post.validators):
        if has_compounding_withdrawal_credential(validator):
            queue_excess_active_balance(post, index)

    return post
```

