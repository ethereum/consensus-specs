# Gloas Light Client -- Fork Logic

<!-- mdformat-toc start --slug=github --no-anchors --maxlevel=6 --minlevel=2 -->

- [Introduction](#introduction)
- [Upgrading light client data](#upgrading-light-client-data)
- [Upgrading the store](#upgrading-the-store)

<!-- mdformat-toc end -->

## Introduction

This document describes how to upgrade existing light client objects based on
the [Electra specification](../../electra/light-client/sync-protocol.md) to
Gloas. This is necessary when processing pre-Gloas data with a post-Gloas
`LightClientStore`. Note that the data being exchanged over the network
protocols uses the original format.

## Upgrading light client data

A Gloas `LightClientStore` can still process earlier light client data. In order
to do so, that pre-Gloas data needs to be locally upgraded to Gloas before
processing.

```python
def upgrade_lc_header_to_gloas(pre: electra.LightClientHeader) -> LightClientHeader:
    if pre == electra.LightClientHeader():
        return LightClientHeader()

    epoch = compute_epoch_at_slot(pre.beacon.slot)

    if epoch >= DENEB_FORK_EPOCH:
        BLOCK_HASH_GINDEX = get_generalized_index(deneb.ExecutionPayloadHeader, "block_hash")
        return LightClientHeader(
            beacon=pre.beacon,
            execution_block_hash=pre.execution.block_hash,
            execution_branch=ExecutionBranch(
                normalize_merkle_branch(
                    list(compute_merkle_proof(pre.execution, BLOCK_HASH_GINDEX))
                    + list(pre.execution_branch),
                    EXECUTION_BLOCK_HASH_GINDEX_GLOAS,
                )
            ),
        )

    if epoch >= CAPELLA_FORK_EPOCH:
        execution_header = capella.ExecutionPayloadHeader(
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
        )
        BLOCK_HASH_GINDEX = get_generalized_index(capella.ExecutionPayloadHeader, "block_hash")
        return LightClientHeader(
            beacon=pre.beacon,
            execution_block_hash=pre.execution.block_hash,
            execution_branch=ExecutionBranch(
                normalize_merkle_branch(
                    list(compute_merkle_proof(execution_header, BLOCK_HASH_GINDEX))
                    + list(pre.execution_branch),
                    EXECUTION_BLOCK_HASH_GINDEX_GLOAS,
                )
            ),
        )

    return LightClientHeader(beacon=pre.beacon)
```

```python
def upgrade_lc_bootstrap_to_gloas(pre: electra.LightClientBootstrap) -> LightClientBootstrap:
    return LightClientBootstrap(
        header=upgrade_lc_header_to_gloas(pre.header),
        current_sync_committee=pre.current_sync_committee,
        current_sync_committee_branch=normalize_merkle_branch(
            pre.current_sync_committee_branch, CURRENT_SYNC_COMMITTEE_GINDEX_GLOAS
        ),
    )
```

```python
def upgrade_lc_update_to_gloas(pre: electra.LightClientUpdate) -> LightClientUpdate:
    return LightClientUpdate(
        attested_header=upgrade_lc_header_to_gloas(pre.attested_header),
        next_sync_committee=pre.next_sync_committee,
        next_sync_committee_branch=normalize_merkle_branch(
            pre.next_sync_committee_branch, NEXT_SYNC_COMMITTEE_GINDEX_GLOAS
        ),
        finalized_header=upgrade_lc_header_to_gloas(pre.finalized_header),
        finality_branch=normalize_merkle_branch(pre.finality_branch, FINALIZED_ROOT_GINDEX_GLOAS),
        sync_aggregate=pre.sync_aggregate,
        signature_slot=pre.signature_slot,
    )
```

```python
def upgrade_lc_finality_update_to_gloas(
    pre: electra.LightClientFinalityUpdate,
) -> LightClientFinalityUpdate:
    return LightClientFinalityUpdate(
        attested_header=upgrade_lc_header_to_gloas(pre.attested_header),
        finalized_header=upgrade_lc_header_to_gloas(pre.finalized_header),
        finality_branch=normalize_merkle_branch(pre.finality_branch, FINALIZED_ROOT_GINDEX_GLOAS),
        sync_aggregate=pre.sync_aggregate,
        signature_slot=pre.signature_slot,
    )
```

```python
def upgrade_lc_optimistic_update_to_gloas(
    pre: electra.LightClientOptimisticUpdate,
) -> LightClientOptimisticUpdate:
    return LightClientOptimisticUpdate(
        attested_header=upgrade_lc_header_to_gloas(pre.attested_header),
        sync_aggregate=pre.sync_aggregate,
        signature_slot=pre.signature_slot,
    )
```

## Upgrading the store

Existing `LightClientStore` objects based on Electra MUST be upgraded to Gloas
before Gloas based light client data can be processed. The `LightClientStore`
upgrade MAY be performed before `GLOAS_FORK_EPOCH`.

```python
def upgrade_lc_store_to_gloas(pre: electra.LightClientStore) -> LightClientStore:
    if pre.best_valid_update is None:
        best_valid_update = None
    else:
        best_valid_update = upgrade_lc_update_to_gloas(pre.best_valid_update)
    return LightClientStore(
        finalized_header=upgrade_lc_header_to_gloas(pre.finalized_header),
        current_sync_committee=pre.current_sync_committee,
        next_sync_committee=pre.next_sync_committee,
        best_valid_update=best_valid_update,
        optimistic_header=upgrade_lc_header_to_gloas(pre.optimistic_header),
        previous_max_active_participants=pre.previous_max_active_participants,
        current_max_active_participants=pre.current_max_active_participants,
    )
```
