# EIP-6110 -- Fork Logic

**Notice**: This document is a work-in-progress for researchers and implementers.

## Table of contents

<!-- START doctoc generated TOC please keep comment here to allow auto update -->
<!-- DON'T EDIT THIS SECTION, INSTEAD RE-RUN doctoc TO UPDATE -->

- [Introduction](#introduction)
- [Configuration](#configuration)
- [Helper functions](#helper-functions)
  - [Misc](#misc)
    - [Modified `compute_fork_version`](#modified-compute_fork_version)
- [Fork to EIP-6110](#fork-to-eip-6110)
  - [Fork trigger](#fork-trigger)
  - [Upgrading the state](#upgrading-the-state)

<!-- END doctoc generated TOC please keep comment here to allow auto update -->

## Introduction

This document describes the process of EIP-6110 upgrade.

## Configuration

Warning: this configuration is not definitive.

| Name | Value |
| - | - |
| `EIP6110_FORK_VERSION` | `Version('0x05000000')` |
| `EIP6110_FORK_EPOCH` | `Epoch(18446744073709551615)` **TBD** |

## Helper functions

### Misc

#### Modified `compute_fork_version`

```python
def compute_fork_version(epoch: Epoch) -> Version:
    """
    Return the fork version at the given ``epoch``.
    """
    if epoch >= EIP6110_FORK_EPOCH:
        return EIP6110_FORK_VERSION
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

## Fork to EIP-6110

### Fork trigger

TBD. This fork is defined for testing purposes, the EIP may be combined with other consensus-layer upgrade.
For now, we assume the condition will be triggered at epoch `EIP6110_FORK_EPOCH`.

Note that for the pure EIP-6110 networks, we don't apply `upgrade_to_eip6110` since it starts with EIP-6110 version logic.

### Upgrading the state

If `state.slot % SLOTS_PER_EPOCH == 0` and `compute_epoch_at_slot(state.slot) == EIP6110_FORK_EPOCH`,
an irregular state change is made to upgrade to EIP-6110.

```python
def upgrade_to_eip6110(pre: deneb.BeaconState) -> BeaconState:
    epoch = deneb.get_current_epoch(pre)
    latest_execution_payload_header = ExecutionPayloadHeader(
        parent_hash=pre.latest_execution_payload_header.parent_hash,
        fee_recipient=pre.latest_execution_payload_header.fee_recipient,
        state_root=pre.latest_execution_payload_header.state_root,
        receipts_root=pre.latest_execution_payload_header.receipts_root,
        logs_bloom=pre.latest_execution_payload_header.logs_bloom,
        prev_randao=pre.latest_execution_payload_header.prev_randao,
        block_number=pre.latest_execution_payload_header.block_number,
        gas_limit=pre.latest_execution_payload_header.gas_limit,
        gas_used=pre.latest_execution_payload_header.gas_used,
        timestamp=pre.latest_execution_payload_header.timestamp,
        extra_data=pre.latest_execution_payload_header.extra_data,
        base_fee_per_gas=pre.latest_execution_payload_header.base_fee_per_gas,
        block_hash=pre.latest_execution_payload_header.block_hash,
        transactions_root=pre.latest_execution_payload_header.transactions_root,
        withdrawals_root=pre.latest_execution_payload_header.withdrawals_root,
        excess_data_gas=uint256(0),
        deposit_receipts_root=Root(),  # [New in EIP-6110]
    )
    post = BeaconState(
        # Versioning
        genesis_time=pre.genesis_time,
        genesis_validators_root=pre.genesis_validators_root,
        slot=pre.slot,
        fork=Fork(
            previous_version=pre.fork.current_version,
            current_version=EIP6110_FORK_VERSION,  # [Modified in EIP-6110]
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
        latest_execution_payload_header=latest_execution_payload_header,  # [Modified in EIP-6110]
        # Withdrawals
        next_withdrawal_index=pre.next_withdrawal_index,
        next_withdrawal_validator_index=pre.next_withdrawal_validator_index,
        # Deep history valid from Capella onwards
        historical_summaries=pre.historical_summaries,
        # EIP-6110
        deposit_receipts_start_index=UNSET_DEPOSIT_RECEIPTS_START_INDEX,  # [New in EIP-6110]
    )

    return post
```
