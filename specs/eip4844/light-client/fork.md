# EIP4844 Light Client -- Fork Logic

## Table of contents

<!-- TOC -->
<!-- START doctoc generated TOC please keep comment here to allow auto update -->
<!-- DON'T EDIT THIS SECTION, INSTEAD RE-RUN doctoc TO UPDATE -->

- [Introduction](#introduction)
  - [Upgrading light client data](#upgrading-light-client-data)
  - [Upgrading the store](#upgrading-the-store)

<!-- END doctoc generated TOC please keep comment here to allow auto update -->
<!-- /TOC -->

## Introduction

This document describes how to upgrade existing light client objects based on the [Capella specification](../../capella/light-client/sync-protocol.md) to EIP4844. This is necessary when processing pre-EIP4844 data with a post-EIP4844 `LightClientStore`. Note that the data being exchanged over the network protocols uses the original format.

### Upgrading light client data

A EIP4844 `LightClientStore` can still process earlier light client data. In order to do so, that pre-EIP4844 data needs to be locally upgraded to EIP4844 before processing.

```python
def upgrade_lc_header_to_eip4844(pre: capella.LightClientHeader) -> LightClientHeader:
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
        ),
        execution_branch=pre.execution_branch,
    )
```

```python
def upgrade_lc_bootstrap_to_eip4844(pre: capella.LightClientBootstrap) -> LightClientBootstrap:
    return LightClientBootstrap(
        header=upgrade_lc_header_to_eip4844(pre.header),
        current_sync_committee=pre.current_sync_committee,
        current_sync_committee_branch=pre.current_sync_committee_branch,
    )
```

```python
def upgrade_lc_update_to_eip4844(pre: capella.LightClientUpdate) -> LightClientUpdate:
    return LightClientUpdate(
        attested_header=upgrade_lc_header_to_eip4844(pre.attested_header),
        next_sync_committee=pre.next_sync_committee,
        next_sync_committee_branch=pre.next_sync_committee_branch,
        finalized_header=upgrade_lc_header_to_eip4844(pre.finalized_header),
        finality_branch=pre.finality_branch,
        sync_aggregate=pre.sync_aggregate,
        signature_slot=pre.signature_slot,
    )
```

```python
def upgrade_lc_finality_update_to_eip4844(pre: capella.LightClientFinalityUpdate) -> LightClientFinalityUpdate:
    return LightClientFinalityUpdate(
        attested_header=upgrade_lc_header_to_eip4844(pre.attested_header),
        finalized_header=upgrade_lc_header_to_eip4844(pre.finalized_header),
        finality_branch=pre.finality_branch,
        sync_aggregate=pre.sync_aggregate,
        signature_slot=pre.signature_slot,
    )
```

```python
def upgrade_lc_optimistic_update_to_eip4844(pre: capella.LightClientOptimisticUpdate) -> LightClientOptimisticUpdate:
    return LightClientOptimisticUpdate(
        attested_header=upgrade_lc_header_to_eip4844(pre.attested_header),
        sync_aggregate=pre.sync_aggregate,
        signature_slot=pre.signature_slot,
    )
```

### Upgrading the store

Existing `LightClientStore` objects based on Capella MUST be upgraded to EIP4844 before EIP4844 based light client data can be processed. The `LightClientStore` upgrade MAY be performed before `EIP4844_FORK_EPOCH`.

```python
def upgrade_lc_store_to_eip4844(pre: capella.LightClientStore) -> LightClientStore:
    if pre.best_valid_update is None:
        best_valid_update = None
    else:
        best_valid_update = upgrade_lc_update_to_eip4844(pre.best_valid_update)
    return LightClientStore(
        finalized_header=upgrade_lc_header_to_eip4844(pre.finalized_header),
        current_sync_committee=pre.current_sync_committee,
        next_sync_committee=pre.next_sync_committee,
        best_valid_update=best_valid_update,
        optimistic_header=upgrade_lc_header_to_eip4844(pre.optimistic_header),
        previous_max_active_participants=pre.previous_max_active_participants,
        current_max_active_participants=pre.current_max_active_participants,
    )
```
