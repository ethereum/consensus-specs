# EIP-6110 Light Client -- Sync Protocol

**Notice**: This document is a work-in-progress for researchers and implementers.

## Table of contents

<!-- TOC -->
<!-- START doctoc generated TOC please keep comment here to allow auto update -->
<!-- DON'T EDIT THIS SECTION, INSTEAD RE-RUN doctoc TO UPDATE -->

- [Introduction](#introduction)
- [Helper functions](#helper-functions)
  - [Modified `get_lc_execution_root`](#modified-get_lc_execution_root)
  - [Modified `is_valid_light_client_header`](#modified-is_valid_light_client_header)

<!-- END doctoc generated TOC please keep comment here to allow auto update -->
<!-- /TOC -->

## Introduction

This upgrade updates light client data to include the EIP-6110 changes to the [`ExecutionPayload`](../beacon-chain.md) structure. It extends the [Deneb Light Client specifications](../../deneb/light-client/sync-protocol.md). The [fork document](./fork.md) explains how to upgrade existing Deneb based deployments to EIP-6110.

Additional documents describes the impact of the upgrade on certain roles:
- [Full node](./full-node.md)
- [Networking](./p2p-interface.md)

## Helper functions

### Modified `get_lc_execution_root`

```python
def get_lc_execution_root(header: LightClientHeader) -> Root:
    epoch = compute_epoch_at_slot(header.beacon.slot)

    if epoch >= DENEB_FORK_EPOCH:
        return hash_tree_root(header.execution)

    if epoch >= CAPELLA_FORK_EPOCH:
        execution_header = capella.ExecutionPayloadHeader(
            parent_hash=header.execution.parent_hash,
            fee_recipient=header.execution.fee_recipient,
            state_root=header.execution.state_root,
            receipts_root=header.execution.receipts_root,
            logs_bloom=header.execution.logs_bloom,
            prev_randao=header.execution.prev_randao,
            block_number=header.execution.block_number,
            gas_limit=header.execution.gas_limit,
            gas_used=header.execution.gas_used,
            timestamp=header.execution.timestamp,
            extra_data=header.execution.extra_data,
            base_fee_per_gas=header.execution.base_fee_per_gas,
            block_hash=header.execution.block_hash,
            transactions_root=header.execution.transactions_root,
            withdrawals_root=header.execution.withdrawals_root,
        )
        return hash_tree_root(execution_header)

    return Root()
```

### Modified `is_valid_light_client_header`

```python
def is_valid_light_client_header(header: LightClientHeader) -> bool:
    epoch = compute_epoch_at_slot(header.beacon.slot)

    # [New in EIP-6110]
    if epoch < EIP6110_FORK_EPOCH:
        if header.execution.deposit_receipts_root != Root():
            return False

    if epoch < DENEB_FORK_EPOCH:
        if header.execution.excess_data_gas != uint256(0):
            return False

    if epoch < CAPELLA_FORK_EPOCH:
        return (
            header.execution == ExecutionPayloadHeader()
            and header.execution_branch == [Bytes32() for _ in range(floorlog2(EXECUTION_PAYLOAD_INDEX))]
        )

    return is_valid_merkle_branch(
        leaf=get_lc_execution_root(header),
        branch=header.execution_branch,
        depth=floorlog2(EXECUTION_PAYLOAD_INDEX),
        index=get_subtree_index(EXECUTION_PAYLOAD_INDEX),
        root=header.beacon.body_root,
    )
```
