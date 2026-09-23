# Deferred Payload Verification -- Fork Logic

*Note*: This document is a work-in-progress for researchers and implementers.

## Table of contents

<!-- mdformat-toc start --slug=github --no-anchors --maxlevel=6 --minlevel=2 -->

- [Table of contents](#table-of-contents)
- [Introduction](#introduction)
- [Configuration](#configuration)
- [Fork to Deferred Payload Verification](#fork-to-deferred-payload-verification)

<!-- mdformat-toc end -->

## Introduction

This document describes the process of the Deferred Payload Verification
upgrade. Only `BeaconState` changes, so the upgrade carries every field across
unchanged and initializes the new one.

## Configuration

Warning: this configuration is not definitive.

| Name                                 | Value                                 |
| ------------------------------------ | ------------------------------------- |
| `PAYLOAD_REQUEST_CHAIN_FORK_VERSION` | `Version('0x9c1a1000')`               |
| `PAYLOAD_REQUEST_CHAIN_FORK_EPOCH`   | `Epoch(18446744073709551615)` **TBD** |

## Fork to Deferred Payload Verification

If `state.slot % SLOTS_PER_EPOCH == 0` and
`compute_epoch_at_slot(state.slot) == PAYLOAD_REQUEST_CHAIN_FORK_EPOCH`, an
irregular state change is made to upgrade to this feature.

The upgrade occurs after the completion of the inner loop of `process_slots`
that sets `state.slot` equal to
`PAYLOAD_REQUEST_CHAIN_FORK_EPOCH * SLOTS_PER_EPOCH`.

The payload request chain starts empty at the fork boundary. The first full
payload after the fork extends `PAYLOAD_REQUEST_CHAIN_ROOT_GENESIS`, so a
consensus client reconciling a range that crosses the fork MUST NOT expect the
execution client to account for pre-fork blocks.

```python
def upgrade_to_payload_request_chain(pre: gloas.BeaconState) -> BeaconState:
    epoch = gloas.get_current_epoch(pre)

    post = BeaconState(
        genesis_time=pre.genesis_time,
        genesis_validators_root=pre.genesis_validators_root,
        slot=pre.slot,
        fork=Fork(
            previous_version=pre.fork.current_version,
            # [New in DeferredPayloadVerification]
            current_version=PAYLOAD_REQUEST_CHAIN_FORK_VERSION,
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
        # [New in DeferredPayloadVerification]
        payload_request_chain_root=PAYLOAD_REQUEST_CHAIN_ROOT_GENESIS,
    )

    return post
```
