# Gloas -- Fork Logic

*Note*: This document is a work-in-progress for researchers and implementers.

<!-- mdformat-toc start --slug=github --no-anchors --maxlevel=6 --minlevel=2 -->

- [Introduction](#introduction)
- [Configuration](#configuration)
- [Fork to Gloas](#fork-to-gloas)
  - [Fork trigger](#fork-trigger)
  - [Upgrading the state](#upgrading-the-state)

<!-- mdformat-toc end -->

## Introduction

This document describes the process of the Gloas upgrade.

## Configuration

Warning: this configuration is not definitive.

| Name                 | Value                                 |
| -------------------- | ------------------------------------- |
| `GLOAS_FORK_VERSION` | `Version('0x07000000')`               |
| `GLOAS_FORK_EPOCH`   | `Epoch(18446744073709551615)` **TBD** |

## Fork to Gloas

### Fork trigger

The fork is triggered at epoch `GLOAS_FORK_EPOCH`.

### Upgrading the state

If `state.slot % SLOTS_PER_EPOCH == 0` and
`compute_epoch_at_slot(state.slot) == GLOAS_FORK_EPOCH`, an irregular state
change is made to upgrade to Gloas.

```python
def upgrade_to_gloas(pre: fulu.BeaconState) -> BeaconState:
    epoch = fulu.get_current_epoch(pre)

    post = BeaconState(
        genesis_time=pre.genesis_time,
        genesis_validators_root=pre.genesis_validators_root,
        slot=pre.slot,
        fork=Fork(
            previous_version=pre.fork.current_version,
            # [Modified in Gloas:EIP7732]
            current_version=GLOAS_FORK_VERSION,
            epoch=epoch,
        ),
        latest_block_header=pre.latest_block_header,
        block_roots=pre.block_roots,
        state_roots=pre.state_roots,
        historical_roots=pre.historical_roots,
        eth1_data=pre.eth1_data,
        eth1_data_votes=pre.eth1_data_votes,
        eth1_deposit_index=pre.eth1_deposit_index,
        validators=pre.validators,
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
        # [New in Gloas:EIP7732]
        # Removed `latest_execution_payload_header`
        latest_execution_payload_bid=ExecutionPayloadBid(),
        next_withdrawal_index=pre.next_withdrawal_index,
        next_withdrawal_validator_index=pre.next_withdrawal_validator_index,
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
        proposer_lookahead=pre.proposer_lookahead,
        # [New in Gloas:EIP7732]
        execution_payload_availability=[0b1 for _ in range(SLOTS_PER_HISTORICAL_ROOT)],
        # [New in Gloas:EIP7732]
        builder_pending_payments=[BuilderPendingPayment() for _ in range(2 * SLOTS_PER_EPOCH)],
        # [New in Gloas:EIP7732]
        builder_pending_withdrawals=[],
        # [New in Gloas:EIP7732]
        latest_block_hash=pre.latest_execution_payload_header.block_hash,
        # [New in Gloas:EIP7732]
        latest_withdrawals_root=Root(),
    )

    return post
```
