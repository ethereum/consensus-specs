# Deneb Light Client -- Sync Protocol

<!-- mdformat-toc start --slug=github --no-anchors --maxlevel=6 --minlevel=2 -->

- [Introduction](#introduction)
- [Helper functions](#helper-functions)
  - [Modified `get_lc_execution_root`](#modified-get_lc_execution_root)
  - [Modified `is_valid_light_client_header`](#modified-is_valid_light_client_header)

<!-- mdformat-toc end -->

## Introduction

This upgrade updates light client data to include the Deneb changes to the
[`ExecutionPayload`](../beacon-chain.md) structure. It extends the
[Capella Light Client specifications](../../capella/light-client/sync-protocol.md).
The [fork document](./fork.md) explains how to upgrade existing Capella based
deployments to Deneb.

Additional documents describes the impact of the upgrade on certain roles:

- [Full node](./full-node.md)
- [Networking](./p2p-interface.md)

## Helper functions

### Modified `get_lc_execution_root`

```python
def get_lc_execution_root(header: LightClientHeader) -> Root:
    epoch = compute_epoch_at_slot(header.beacon.slot)

    # [New in Deneb]
    if epoch >= DENEB_FORK_EPOCH:
        return hash_tree_root(header.execution)

    # [Modified in Deneb]
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

    # [New in Deneb:EIP4844]
    if epoch < DENEB_FORK_EPOCH:
        if header.execution.blob_gas_used != uint64(0):
            return False
        if header.execution.excess_blob_gas != uint64(0):
            return False

    if epoch < CAPELLA_FORK_EPOCH:
        return (
            header.execution == ExecutionPayloadHeader()
            and header.execution_branch == ExecutionBranch()
        )

    return is_valid_merkle_branch(
        leaf=get_lc_execution_root(header),
        branch=header.execution_branch,
        depth=floorlog2(EXECUTION_PAYLOAD_GINDEX),
        index=get_subtree_index(EXECUTION_PAYLOAD_GINDEX),
        root=header.beacon.body_root,
    )
```
