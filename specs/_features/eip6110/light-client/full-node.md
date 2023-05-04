# EIP-6110 Light Client -- Full Node

**Notice**: This document is a work-in-progress for researchers and implementers.

## Table of contents

<!-- TOC -->
<!-- START doctoc generated TOC please keep comment here to allow auto update -->
<!-- DON'T EDIT THIS SECTION, INSTEAD RE-RUN doctoc TO UPDATE -->

- [Introduction](#introduction)
- [Helper functions](#helper-functions)
  - [Modified `block_to_light_client_header`](#modified-block_to_light_client_header)

<!-- END doctoc generated TOC please keep comment here to allow auto update -->
<!-- /TOC -->

## Introduction

This upgrade adds information about the execution payload to light client data as part of the EIP-6110 upgrade.

## Helper functions

### Modified `block_to_light_client_header`

```python
def block_to_light_client_header(block: SignedBeaconBlock) -> LightClientHeader:
    epoch = compute_epoch_at_slot(block.message.slot)

    if epoch >= CAPELLA_FORK_EPOCH:
        payload = block.message.body.execution_payload
        execution_header = ExecutionPayloadHeader(
            parent_hash=payload.parent_hash,
            fee_recipient=payload.fee_recipient,
            state_root=payload.state_root,
            receipts_root=payload.receipts_root,
            logs_bloom=payload.logs_bloom,
            prev_randao=payload.prev_randao,
            block_number=payload.block_number,
            gas_limit=payload.gas_limit,
            gas_used=payload.gas_used,
            timestamp=payload.timestamp,
            extra_data=payload.extra_data,
            base_fee_per_gas=payload.base_fee_per_gas,
            block_hash=payload.block_hash,
            transactions_root=hash_tree_root(payload.transactions),
            withdrawals_root=hash_tree_root(payload.withdrawals),
        )

        if epoch >= DENEB_FORK_EPOCH:
            execution_header.excess_data_gas = payload.excess_data_gas

        # [New in EIP6110]
        if epoch >= EIP6110_FORK_EPOCH:
            execution_header.deposit_receipts_root = hash_tree_root(payload.deposit_receipts)

        execution_branch = compute_merkle_proof_for_block_body(block.message.body, EXECUTION_PAYLOAD_INDEX)
    else:
        # Note that during fork transitions, `finalized_header` may still point to earlier forks.
        # While Bellatrix blocks also contain an `ExecutionPayload` (minus `withdrawals_root`),
        # it was not included in the corresponding light client data. To ensure compatibility
        # with legacy data going through `upgrade_lc_header_to_capella`, leave out execution data.
        execution_header = ExecutionPayloadHeader()
        execution_branch = [Bytes32() for _ in range(floorlog2(EXECUTION_PAYLOAD_INDEX))]

    return LightClientHeader(
        beacon=BeaconBlockHeader(
            slot=block.message.slot,
            proposer_index=block.message.proposer_index,
            parent_root=block.message.parent_root,
            state_root=block.message.state_root,
            body_root=hash_tree_root(block.message.body),
        ),
        execution=execution_header,
        execution_branch=execution_branch,
    )
```
