# EIP-7732 -- Fork Logic

*Note*: This document is a work-in-progress for researchers and implementers.

<!-- mdformat-toc start --slug=github --no-anchors --maxlevel=6 --minlevel=2 -->

- [Introduction](#introduction)
- [Configuration](#configuration)
- [Helper functions](#helper-functions)
  - [Misc](#misc)
    - [Modified `compute_fork_version`](#modified-compute_fork_version)
- [Fork to EIP-7732](#fork-to-eip-7732)
  - [Fork trigger](#fork-trigger)
  - [Upgrading the state](#upgrading-the-state)

<!-- mdformat-toc end -->

## Introduction

This document describes the process of the EIP-7732 upgrade.

## Configuration

Warning: this configuration is not definitive.

| Name                | Value |
|---------------------| - |
| `EIP7732_FORK_VERSION` | `Version('0x09000000')` |
| `EIP7732_FORK_EPOCH`   | `Epoch(18446744073709551615)` **TBD** |

## Helper functions

### Misc

#### Modified `compute_fork_version`

```python
def compute_fork_version(epoch: Epoch) -> Version:
    """
    Return the fork version at the given ``epoch``.
    """
    if epoch >= EIP7732_FORK_EPOCH:
        return EIP7732_FORK_VERSION
    if epoch >= ELECTRA_FORK_EPOCH:
        return ELECTRA_FORK_VERSION
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

## Fork to EIP-7732

### Fork trigger

The fork is triggered at epoch `EIP7732_FORK_EPOCH`. The EIP may be combined with other consensus-layer upgrade.

### Upgrading the state

If `state.slot % SLOTS_PER_EPOCH == 0` and `compute_epoch_at_slot(state.slot) == EIP7732_FORK_EPOCH`,
an irregular state change is made to upgrade to EIP-7732.

```python
def upgrade_to_eip7732(pre: electra.BeaconState) -> BeaconState:
    epoch = electra.get_current_epoch(pre)

    post = BeaconState(
        # Versioning
        genesis_time=pre.genesis_time,
        genesis_validators_root=pre.genesis_validators_root,
        slot=pre.slot,
        fork=Fork(
            previous_version=pre.fork.current_version,
            current_version=EIP7732_FORK_VERSION,  # [Modified in EIP-7732]
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
        latest_execution_payload_header=ExecutionPayloadHeader(),  # [Modified in EIP-7732]
        # Withdrawals
        next_withdrawal_index=pre.next_withdrawal_index,
        next_withdrawal_validator_index=pre.next_withdrawal_validator_index,
        # Deep history valid from Capella onwards
        historical_summaries=pre.historical_summaries,
        deposit_requests_start_index=pre.deposit_requests_start_index,
        deposit_balance_to_consume=pre.deposit_balance_to_consume,
        exit_balance_to_consume=pre.exit_balance_to_consume,
        earliest_exit_epoch=pre.earliest_exit_epoch,
        consolidation_balance_to_consume=pre.consolidation_balance_to_consume,
        earliest_consolidation_epoch=pre.earliest_consolidation_epoch,
        pending_deposits=pre.pending_deposits,
        pending_partial_withdrawals=pre.pending_partial_withdrawals,
        pending_consolidations=pre.pending_consolidations,
        # ePBS
        latest_block_hash=pre.latest_execution_payload_header.block_hash,  # [New in EIP-7732]
        latest_full_slot=pre.slot,  # [New in EIP-7732]
        latest_withdrawals_root=Root(),  # [New in EIP-7732]
    )

    return post
```
