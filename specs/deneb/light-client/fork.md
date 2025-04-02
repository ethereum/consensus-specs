# Deneb Light Client -- Fork Logic

<!-- mdformat-toc start --slug=github --no-anchors --maxlevel=6 --minlevel=2 -->

- [Introduction](#introduction)
- [Upgrading light client data](#upgrading-light-client-data)
- [Upgrading the store](#upgrading-the-store)

<!-- mdformat-toc end -->

## Introduction

This document describes how to upgrade existing light client objects based on the [Capella specification](../../capella/light-client/sync-protocol.md) to Deneb. This is necessary when processing pre-Deneb data with a post-Deneb `LightClientStore`. Note that the data being exchanged over the network protocols uses the original format.

## Upgrading light client data

A Deneb `LightClientStore` can still process earlier light client data. In order to do so, that pre-Deneb data needs to be locally upgraded to Deneb before processing.

```python
def upgrade_lc_header_to_deneb(pre: capella.LightClientHeader) -> LightClientHeader:
    return LightClientHeader(
        beacon=pre.beacon,
        execution=ExecutionPayloadHeader(
            parent_hash=pre.execution.parent_hash,
            fee_recipient=pre.execution.fee_recipient,
            state_root=pre.execution.state_root,
            receipts_root=pre.execution.receipts_root,
            logs_bloom=pre.execution.logs_bloom,
            prev_randao=pre.execution.prev_randao,
            block_number=pre.execution.block_number,
            gas_limit=pre.execution.gas_limit,
            gas_used=pre.execution.gas_used,
            timestamp=pre.execution.timestamp,
            extra_data=pre.execution.extra_data,
            base_fee_per_gas=pre.execution.base_fee_per_gas,
            block_hash=pre.execution.block_hash,
            transactions_root=pre.execution.transactions_root,
            withdrawals_root=pre.execution.withdrawals_root,
            blob_gas_used=uint64(0),  # [New in Deneb:EIP4844]
            excess_blob_gas=uint64(0),  # [New in Deneb:EIP4844]
        ),
        execution_branch=pre.execution_branch,
    )
```

```python
def upgrade_lc_bootstrap_to_deneb(pre: capella.LightClientBootstrap) -> LightClientBootstrap:
    return LightClientBootstrap(
        header=upgrade_lc_header_to_deneb(pre.header),
        current_sync_committee=pre.current_sync_committee,
        current_sync_committee_branch=pre.current_sync_committee_branch,
    )
```

```python
def upgrade_lc_update_to_deneb(pre: capella.LightClientUpdate) -> LightClientUpdate:
    return LightClientUpdate(
        attested_header=upgrade_lc_header_to_deneb(pre.attested_header),
        next_sync_committee=pre.next_sync_committee,
        next_sync_committee_branch=pre.next_sync_committee_branch,
        finalized_header=upgrade_lc_header_to_deneb(pre.finalized_header),
        finality_branch=pre.finality_branch,
        sync_aggregate=pre.sync_aggregate,
        signature_slot=pre.signature_slot,
    )
```

```python
def upgrade_lc_finality_update_to_deneb(pre: capella.LightClientFinalityUpdate) -> LightClientFinalityUpdate:
    return LightClientFinalityUpdate(
        attested_header=upgrade_lc_header_to_deneb(pre.attested_header),
        finalized_header=upgrade_lc_header_to_deneb(pre.finalized_header),
        finality_branch=pre.finality_branch,
        sync_aggregate=pre.sync_aggregate,
        signature_slot=pre.signature_slot,
    )
```

```python
def upgrade_lc_optimistic_update_to_deneb(pre: capella.LightClientOptimisticUpdate) -> LightClientOptimisticUpdate:
    return LightClientOptimisticUpdate(
        attested_header=upgrade_lc_header_to_deneb(pre.attested_header),
        sync_aggregate=pre.sync_aggregate,
        signature_slot=pre.signature_slot,
    )
```

## Upgrading the store

Existing `LightClientStore` objects based on Capella MUST be upgraded to Deneb before Deneb based light client data can be processed. The `LightClientStore` upgrade MAY be performed before `DENEB_FORK_EPOCH`.

```python
def upgrade_lc_store_to_deneb(pre: capella.LightClientStore) -> LightClientStore:
    if pre.best_valid_update is None:
        best_valid_update = None
    else:
        best_valid_update = upgrade_lc_update_to_deneb(pre.best_valid_update)
    return LightClientStore(
        finalized_header=upgrade_lc_header_to_deneb(pre.finalized_header),
        current_sync_committee=pre.current_sync_committee,
        next_sync_committee=pre.next_sync_committee,
        best_valid_update=best_valid_update,
        optimistic_header=upgrade_lc_header_to_deneb(pre.optimistic_header),
        previous_max_active_participants=pre.previous_max_active_participants,
        current_max_active_participants=pre.current_max_active_participants,
    )
```
