# Capella Light Client -- Fork Logic

<!-- mdformat-toc start --slug=github --no-anchors --maxlevel=6 --minlevel=2 -->

- [Introduction](#introduction)
- [Upgrading light client data](#upgrading-light-client-data)
- [Upgrading the store](#upgrading-the-store)

<!-- mdformat-toc end -->

## Introduction

This document describes how to upgrade existing light client objects based on
the [Altair specification](../../altair/light-client/sync-protocol.md) to
Capella. This is necessary when processing pre-Capella data with a post-Capella
`LightClientStore`. Note that the data being exchanged over the network
protocols uses the original format.

## Upgrading light client data

A Capella `LightClientStore` can still process earlier light client data. In
order to do so, that pre-Capella data needs to be locally upgraded to Capella
before processing.

```python
def upgrade_lc_header_to_capella(pre: altair.LightClientHeader) -> LightClientHeader:
    return LightClientHeader(
        beacon=pre.beacon,
        execution=ExecutionPayloadHeader(),
        execution_branch=ExecutionBranch(),
    )
```

```python
def upgrade_lc_bootstrap_to_capella(pre: altair.LightClientBootstrap) -> LightClientBootstrap:
    return LightClientBootstrap(
        header=upgrade_lc_header_to_capella(pre.header),
        current_sync_committee=pre.current_sync_committee,
        current_sync_committee_branch=pre.current_sync_committee_branch,
    )
```

```python
def upgrade_lc_update_to_capella(pre: altair.LightClientUpdate) -> LightClientUpdate:
    return LightClientUpdate(
        attested_header=upgrade_lc_header_to_capella(pre.attested_header),
        next_sync_committee=pre.next_sync_committee,
        next_sync_committee_branch=pre.next_sync_committee_branch,
        finalized_header=upgrade_lc_header_to_capella(pre.finalized_header),
        finality_branch=pre.finality_branch,
        sync_aggregate=pre.sync_aggregate,
        signature_slot=pre.signature_slot,
    )
```

```python
def upgrade_lc_finality_update_to_capella(
    pre: altair.LightClientFinalityUpdate,
) -> LightClientFinalityUpdate:
    return LightClientFinalityUpdate(
        attested_header=upgrade_lc_header_to_capella(pre.attested_header),
        finalized_header=upgrade_lc_header_to_capella(pre.finalized_header),
        finality_branch=pre.finality_branch,
        sync_aggregate=pre.sync_aggregate,
        signature_slot=pre.signature_slot,
    )
```

```python
def upgrade_lc_optimistic_update_to_capella(
    pre: altair.LightClientOptimisticUpdate,
) -> LightClientOptimisticUpdate:
    return LightClientOptimisticUpdate(
        attested_header=upgrade_lc_header_to_capella(pre.attested_header),
        sync_aggregate=pre.sync_aggregate,
        signature_slot=pre.signature_slot,
    )
```

## Upgrading the store

Existing `LightClientStore` objects based on Altair MUST be upgraded to Capella
before Capella based light client data can be processed. The `LightClientStore`
upgrade MAY be performed before `CAPELLA_FORK_EPOCH`.

```python
def upgrade_lc_store_to_capella(pre: altair.LightClientStore) -> LightClientStore:
    if pre.best_valid_update is None:
        best_valid_update = None
    else:
        best_valid_update = upgrade_lc_update_to_capella(pre.best_valid_update)
    return LightClientStore(
        finalized_header=upgrade_lc_header_to_capella(pre.finalized_header),
        current_sync_committee=pre.current_sync_committee,
        next_sync_committee=pre.next_sync_committee,
        best_valid_update=best_valid_update,
        optimistic_header=upgrade_lc_header_to_capella(pre.optimistic_header),
        previous_max_active_participants=pre.previous_max_active_participants,
        current_max_active_participants=pre.current_max_active_participants,
    )
```
