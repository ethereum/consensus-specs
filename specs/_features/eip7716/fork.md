# EIP-7716 -- Fork Logic

*Note*: This document is a work-in-progress for researchers and implementers.

<!-- mdformat-toc start --slug=github --no-anchors --maxlevel=6 --minlevel=2 -->

- [Introduction](#introduction)
- [Configuration](#configuration)
- [Helper functions](#helper-functions)
  - [New `get_fork_initial_offline_balance_ema`](#new-get_fork_initial_offline_balance_ema)
- [Fork to EIP-7716](#fork-to-eip-7716)

<!-- mdformat-toc end -->

## Introduction

This document describes the process of the EIP-7716 upgrade.

## Configuration

Warning: this configuration is not definitive.

| Name                   | Value                                 |
| ---------------------- | ------------------------------------- |
| `EIP7716_FORK_VERSION` | `Version('0x77160000')`               |
| `EIP7716_FORK_EPOCH`   | `Epoch(18446744073709551615)` **TBD** |

## Helper functions

### New `get_fork_initial_offline_balance_ema`

The moving average is seeded with the observed mean per-slot offline balance of
the epoch preceding the fork, so that no spurious penalty factor occurs at
activation.

```python
def get_fork_initial_offline_balance_ema(state: BeaconState) -> Gwei:
    total = Gwei(0)
    start_slot = compute_start_slot_at_epoch(get_previous_epoch(state))
    for slot_offset in range(SLOTS_PER_EPOCH):
        slot = Slot(start_slot + slot_offset)
        total += get_slot_offline_balance(state, slot)
    return Gwei(total // SLOTS_PER_EPOCH)
```

## Fork to EIP-7716

If `state.slot % SLOTS_PER_EPOCH == 0` and
`compute_epoch_at_slot(state.slot) == EIP7716_FORK_EPOCH`, an irregular state
change is made to upgrade to EIP-7716.

The upgrade occurs after the completion of the inner loop of `process_slots`
that sets `state.slot` equal to `EIP7716_FORK_EPOCH * SLOTS_PER_EPOCH`.

```python
def upgrade_to_eip7716(pre: heze.BeaconState) -> BeaconState:
    epoch = get_current_epoch(pre)
    post = BeaconState(
        genesis_time=pre.genesis_time,
        genesis_validators_root=pre.genesis_validators_root,
        slot=pre.slot,
        fork=Fork(
            previous_version=pre.fork.current_version,
            # [New in EIP7716]
            current_version=EIP7716_FORK_VERSION,
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
        latest_block_hash=pre.latest_block_hash,
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
        builders=pre.builders,
        next_withdrawal_builder_index=pre.next_withdrawal_builder_index,
        execution_payload_availability=pre.execution_payload_availability,
        builder_pending_payments=pre.builder_pending_payments,
        builder_pending_withdrawals=pre.builder_pending_withdrawals,
        latest_execution_payload_bid=pre.latest_execution_payload_bid,
        payload_expected_withdrawals=pre.payload_expected_withdrawals,
        ptc_window=pre.ptc_window,
        # [New in EIP7716]
        offline_balance_ema=Gwei(0),
    )
    # [New in EIP7716]
    post.offline_balance_ema = get_fork_initial_offline_balance_ema(post)

    return post
```
