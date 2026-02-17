# EIP-7805 -- Fork Logic

*Note*: This document is a work-in-progress for researchers and implementers.

<!-- mdformat-toc start --slug=github --no-anchors --maxlevel=6 --minlevel=2 -->

- [Introduction](#introduction)
- [Configuration](#configuration)
- [Fork to EIP-7805](#fork-to-eip-7805)
  - [Upgrading the state](#upgrading-the-state)

<!-- mdformat-toc end -->

## Introduction

This document describes the process of the EIP-7805 upgrade.

## Configuration

Warning: this configuration is not definitive.

| Name                   | Value                                 |
| ---------------------- | ------------------------------------- |
| `EIP7805_FORK_VERSION` | `Version('0xe7805000')`               |
| `EIP7805_FORK_EPOCH`   | `Epoch(18446744073709551615)` **TBD** |

## Fork to EIP-7805

### Upgrading the state

If `state.slot % SLOTS_PER_EPOCH == 0` and
`compute_epoch_at_slot(state.slot) == EIP7805_FORK_EPOCH`, an irregular state
change is made to upgrade to EIP-7805.

```python
def upgrade_to_eip7805(pre: gloas.BeaconState) -> BeaconState:
    epoch = gloas.get_current_epoch(pre)
    latest_execution_payload_bid = ExecutionPayloadBid(
        parent_block_hash=pre.latest_execution_payload_bid.parent_block_hash,
        parent_block_root=pre.latest_execution_payload_bid.parent_block_root,
        block_hash=pre.latest_execution_payload_bid.block_hash,
        prev_randao=pre.latest_execution_payload_bid.prev_randao,
        fee_recipient=pre.latest_execution_payload_bid.fee_recipient,
        gas_limit=pre.latest_execution_payload_bid.gas_limit,
        builder_index=pre.latest_execution_payload_bid.builder_index,
        slot=pre.latest_execution_payload_bid.slot,
        value=pre.latest_execution_payload_bid.value,
        execution_payment=pre.latest_execution_payload_bid.execution_payment,
        blob_kzg_commitments=pre.latest_execution_payload_bid.blob_kzg_commitments,
        # [New in EIP7805]
        inclusion_list_bits=Bitvector[INCLUSION_LIST_COMMITTEE_SIZE](),
    )

    post = BeaconState(
        genesis_time=pre.genesis_time,
        genesis_validators_root=pre.genesis_validators_root,
        slot=pre.slot,
        fork=Fork(
            previous_version=pre.fork.current_version,
            # [Modified in EIP7805]
            current_version=EIP7805_FORK_VERSION,
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
        # [Modified in EIP7805]
        latest_execution_payload_bid=latest_execution_payload_bid,
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
        latest_block_hash=pre.latest_block_hash,
        payload_expected_withdrawals=pre.payload_expected_withdrawals,
    )

    return post
```
