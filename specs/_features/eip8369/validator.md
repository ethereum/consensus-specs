# EIP-8369 -- Honest Validator

*Note*: This document is a work-in-progress for researchers and implementers.

<!-- mdformat-toc start --slug=github --no-anchors --maxlevel=6 --minlevel=2 -->

- [Introduction](#introduction)
- [Beacon chain responsibilities](#beacon-chain-responsibilities)
  - [Block and sidecar proposal](#block-and-sidecar-proposal)
    - [Constructing the `BeaconBlockBody`](#constructing-the-beaconblockbody)
      - [ExecutionPayload](#executionpayload)

<!-- mdformat-toc end -->

## Introduction

This document represents the changes to be made in the code of an "honest
validator" to implement EIP-8369.

## Beacon chain responsibilities

### Block and sidecar proposal

#### Constructing the `BeaconBlockBody`

##### ExecutionPayload

*Note*: The only change to `prepare_execution_payload` is to provide the
inclusion lists grouped per committee member.

```python
def prepare_execution_payload(
    store: Store,
    head: ForkChoiceNode,
    state: BeaconState,
    safe_block_hash: Hash32,
    finalized_block_hash: Hash32,
    suggested_fee_recipient: ExecutionAddress,
    target_gas_limit: Uint64,
    execution_engine: ExecutionEngine,
) -> PayloadId | None:
    parent_bid = state.latest_execution_payload_bid
    if should_build_on_full(store, head, get_current_slot(store)):
        envelope = store.payloads[head.root]
        # Make a copy of the state to avoid mutability issues
        state = state.copy()
        # Apply parent payload before computing withdrawals
        apply_parent_execution_payload(state, envelope.execution_requests)
        withdrawals = get_expected_withdrawals(state).withdrawals
        head_block_hash = parent_bid.block_hash
    else:
        withdrawals = state.payload_expected_withdrawals
        head_block_hash = parent_bid.parent_block_hash

    # Set the forkchoice head and initiate the payload build process
    payload_attributes = PayloadAttributes(
        timestamp=compute_time_at_slot(state.genesis_time, state.slot),
        prev_randao=get_randao_mix(state, get_current_epoch(state)),
        suggested_fee_recipient=suggested_fee_recipient,
        withdrawals=withdrawals,
        parent_beacon_block_root=hash_tree_root(state.latest_block_header),
        slot_number=state.slot,
        target_gas_limit=target_gas_limit,
        # [Modified in EIP8369]
        inclusion_lists=get_inclusion_list_transactions_by_member(
            get_inclusion_list_store(),
            state.slot - 1,
            get_shuffling_dependent_root(store, head.root, compute_epoch_at_slot(state.slot - 1)),
            only_timely=False,
        ),
    )
    return execution_engine.notify_forkchoice_updated(
        head_block_hash=head_block_hash,
        safe_block_hash=safe_block_hash,
        finalized_block_hash=finalized_block_hash,
        payload_attributes=payload_attributes,
        custody_columns=None,
    )
```
