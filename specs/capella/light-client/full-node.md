# Capella Light Client -- Full Node

**Notice**: This document is a work-in-progress for researchers and implementers.

## Table of contents

<!-- TOC -->
<!-- START doctoc generated TOC please keep comment here to allow auto update -->
<!-- DON'T EDIT THIS SECTION, INSTEAD RE-RUN doctoc TO UPDATE -->

- [Introduction](#introduction)
- [Helper functions](#helper-functions)
  - [`compute_merkle_proof_for_block_body`](#compute_merkle_proof_for_block_body)
  - [Modified `block_to_light_client_header`](#modified-block_to_light_client_header)

<!-- END doctoc generated TOC please keep comment here to allow auto update -->
<!-- /TOC -->

## Introduction

This upgrade adds information about the execution payload to light client data as part of the Capella upgrade.

## Helper functions

### `compute_merkle_proof_for_block_body`

```python
def compute_merkle_proof_for_block_body(body: BeaconBlockBody,
                                        index: GeneralizedIndex) -> Sequence[Bytes32]:
    ...
```

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

## Deriving light client data

### `create_light_client_update`

Full nodes SHOULD continue deriving the `LightClientUpdate` for each sync committee period as per the altair specs but with the modified or upgraded `attested_header` and `finalized_header` with the following considerations:

- Both `attested_header` and `finalized_header` are of the same fork types as `LightClientUpdate` and might need upgradation to bundle as update.
- Above implies that the first update of capella MIGHT have both `attested_header` and `finalized_header` upgraded (if capella hardfork coincides with a new period) as they might belong to pre-capella epochs. Post this `finalized_header` will need upgradation till a new finalization occurs in capella.
- Over the wire, the fork information of transmitted data might be available (like fork `version` in beacon-apis or fork `context` in req/resp or fork gossip `topics`)
- However `LightClientUpdate`'s base fork can be assumed belonging to `attested_header`'s slot and can be used to store data without loss of information.

### `create_light_client_finality_update`

Full nodes SHOULD continue deriving the `LightClientFinalityUpdate` as per the altair specs but with the modified or upgraded `attested_header` and `finalized_header` with the following considerations:

- Both `attested_header` and `finalized_header` are of the same fork types as `LightClientFinalityUpdate` and might need upgradation to bundle as update.
- Above implies that the first update of capella MIGHT have both `attested_header` and `finalized_header` upgraded (if capella hardfork coincides with a finalization event) as they might belong to pre-capella epochs. Post this `finalized_header` will be upgradation till a new finalization occurs in capella.
- Over the wire, the fork information of transmitted data might be available (like fork `version` in beacon-apis or fork `context` in req/resp or fork gossip `topics` )
 - However `LightClientFinalityUpdate`'s base fork can be assumed belonging to `attested_header`'s slot and can be used to store data without loss of information.

### `create_light_client_optimistic_update`

Full nodes should continue providing the `LightClientOptimisticUpdate` as per the altair specs but with the modified or upgraded `attested_header` with following considerations:

- `attested_header` is to be constructed/upgraded of the same fork type as `LightClientOptimisticUpdate` and WILL need upgradation on the first update of the capella hardfork as the header will belong to a previous epoch.
- Over the wire, the fork information of transmitted data might be available (like fork `version` in beacon-apis or fork `context` in req/resp or fork gossip `topics` )
- However `LightClientFinalityUpdate`'s base fork can be assumed belonging to `attested_header`'s slot and can be used to store data without loss of information.
