# EIP-9999 -- The Beacon Chain

*Note*: This document is a work-in-progress for researchers and implementers.

## Table of contents

<!-- mdformat-toc start --slug=github --no-anchors --maxlevel=6 --minlevel=2 -->

- [Table of contents](#table-of-contents)
- [Introduction](#introduction)
- [Constants](#constants)
- [Containers](#containers)
  - [New `ExecutionPayloadCommitment`](#new-executionpayloadcommitment)
  - [New `NewPayloadRequestCommitment`](#new-newpayloadrequestcommitment)
  - [Modified `BeaconState`](#modified-beaconstate)
- [Helpers](#helpers)
  - [New `compute_payload_request_chain_root`](#new-compute_payload_request_chain_root)
- [Engine APIs](#engine-apis)
  - [Modified `verify_and_notify_new_payload`](#modified-verify_and_notify_new_payload)
- [Beacon chain state transition function](#beacon-chain-state-transition-function)
  - [Block processing](#block-processing)
    - [Modified `process_parent_execution_payload`](#modified-process_parent_execution_payload)

<!-- mdformat-toc end -->

## Introduction

`payload_request_chain_root` is an accumulator over a per-payload commitment
that both layers compute independently: the consensus layer from the
`ExecutionPayloadBid`, beacon state and the block body, the execution layer from
the block it holds. Comparing the two over `engine_newPayload` establishes that
the payloads an execution client holds are the ones the beacon chain committed
to, for the whole chain prefix, which lets a consensus client range sync without
downloading execution payload envelopes.

The commitment carries only the fields the consensus layer verifies directly.
The rest of the payload is bound through `block_hash` and left to ordinary
execution-layer validity. No input requires executing the block, so an execution
client can extend the chain over blocks it never executes.

*Note*: This specification is built upon [Heze](../../heze/beacon-chain.md).

## Constants

| Name                                 | Value       |
| ------------------------------------ | ----------- |
| `PAYLOAD_REQUEST_CHAIN_ROOT_GENESIS` | `Bytes32()` |

## Containers

### New `ExecutionPayloadCommitment`

```python
class ExecutionPayloadCommitment(ProgressiveContainer):
    ACTIVE_FIELDS = active_fields(width=7)

    parent_hash: Hash32
    prev_randao: Bytes32
    gas_limit: Uint64
    timestamp: Uint64
    block_hash: Hash32
    withdrawals: Withdrawals
    slot_number: Uint64
```

### New `NewPayloadRequestCommitment`

```python
class NewPayloadRequestCommitment(ProgressiveContainer):
    ACTIVE_FIELDS = active_fields(width=4)

    execution_payload: ExecutionPayloadCommitment
    versioned_hashes: VersionedHashes
    parent_beacon_block_root: Root
    requests_hash: Hash32
```

### Modified `BeaconState`

```python
class BeaconState(ProgressiveContainer):
    ACTIVE_FIELDS = active_fields(width=47)

    genesis_time: Uint64
    genesis_validators_root: Root
    slot: Slot
    fork: Fork
    latest_block_header: BeaconBlockHeader
    block_roots: BlockRoots
    state_roots: StateRoots
    historical_roots: HistoricalRoots
    eth1_data: Eth1Data
    eth1_data_votes: Eth1DataVotes
    eth1_deposit_index: Uint64
    validators: Validators
    balances: Balances
    randao_mixes: RandaoMixes
    slashings: Slashings
    previous_epoch_participation: EpochParticipation
    current_epoch_participation: EpochParticipation
    justification_bits: JustificationBits
    previous_justified_checkpoint: Checkpoint
    current_justified_checkpoint: Checkpoint
    finalized_checkpoint: Checkpoint
    inactivity_scores: InactivityScores
    current_sync_committee: SyncCommittee
    next_sync_committee: SyncCommittee
    latest_block_hash: Hash32
    next_withdrawal_index: WithdrawalIndex
    next_withdrawal_validator_index: ValidatorIndex
    historical_summaries: HistoricalSummaries
    deposit_requests_start_index: Uint64
    deposit_balance_to_consume: Gwei
    exit_balance_to_consume: Gwei
    earliest_exit_epoch: Epoch
    consolidation_balance_to_consume: Gwei
    earliest_consolidation_epoch: Epoch
    pending_deposits: PendingDeposits
    pending_partial_withdrawals: PendingPartialWithdrawals
    pending_consolidations: PendingConsolidations
    proposer_lookahead: ProposerLookahead
    builders: Builders
    next_withdrawal_builder_index: BuilderIndex
    execution_payload_availability: ExecutionPayloadAvailability
    builder_pending_payments: BuilderPendingPayments
    builder_pending_withdrawals: BuilderPendingWithdrawals
    latest_execution_payload_bid: ExecutionPayloadBid
    payload_expected_withdrawals: Withdrawals
    ptc_window: PayloadTimelinessCommitteeWindow
    # [New in EIP9999]
    payload_request_chain_root: Bytes32
```

## Helpers

### New `compute_payload_request_chain_root`

```python
def compute_payload_request_chain_root(
    state: BeaconState, bid: ExecutionPayloadBid, requests: ExecutionRequests
) -> Bytes32:
    """
    Return ``state.payload_request_chain_root`` extended by the payload that
    ``bid`` commits to.
    """
    requests_list = get_execution_requests_list(requests)
    commitment = NewPayloadRequestCommitment(
        execution_payload=ExecutionPayloadCommitment(
            parent_hash=bid.parent_block_hash,
            prev_randao=bid.prev_randao,
            gas_limit=bid.gas_limit,
            timestamp=compute_time_at_slot(state.genesis_time, bid.slot),
            block_hash=bid.block_hash,
            withdrawals=state.payload_expected_withdrawals,
            slot_number=bid.slot,
        ),
        versioned_hashes=VersionedHashes(
            data=[
                kzg_commitment_to_versioned_hash(commitment)
                for commitment in bid.blob_kzg_commitments
            ]
        ),
        parent_beacon_block_root=state.latest_block_header.parent_root,
        requests_hash=Hash32(sha256(b"".join(sha256(request) for request in requests_list))),
    )
    return sha256(state.payload_request_chain_root + hash_tree_root(commitment))
```

## Engine APIs

### Modified `verify_and_notify_new_payload`

`engine_newPayload` gains a required `payload_request_chain_root` argument
carrying the consensus client's chain root **through this payload**. The
execution client compares it against its own:

- It MUST return `True` only if the payload is valid and the two are consistent.
  On the wire this is `VALID`.
- It MUST return `False` if the two are inconsistent. On the wire this is
  `INVALID`, distinguished from a payload that failed validation by
  `validationError`.
- It MUST return `False` if it cannot yet determine consistency. On the wire
  this is `SYNCING`, which is not a disagreement. A client holding no chain of
  its own adopts the supplied value as its own.

```python
def verify_and_notify_new_payload(
    self: ExecutionEngine,
    new_payload_request: NewPayloadRequest,
    # [New in EIP9999]
    payload_request_chain_root: Bytes32,
) -> bool:
    """
    Return ``True`` if and only if ``new_payload_request`` is valid with respect
    to ``self.execution_state``, and ``payload_request_chain_root``, when the
    execution client is able to compare it, equals its own chain root through
    this payload.
    """
```

## Beacon chain state transition function

### Block processing

#### Modified `process_parent_execution_payload`

The chain is extended here rather than at bid processing, because a bid is
processed for every block but its payload may never be revealed, and because
this is where the parent's `ExecutionRequests` are available.

```python
def process_parent_execution_payload(state: BeaconState, block: BeaconBlock) -> None:
    bid = block.body.signed_execution_payload_bid.message
    parent_bid = state.latest_execution_payload_bid
    requests = block.body.parent_execution_requests

    if bid.parent_block_hash != parent_bid.block_hash:
        # Parent was EMPTY -- no execution requests expected
        assert requests == ExecutionRequests.empty()
        return

    # Parent was FULL -- verify the bid commitment and apply the payload
    assert hash_tree_root(requests) == parent_bid.execution_requests_root

    # [New in EIP9999]
    # The parent payload is now known to be FULL, so extend the chain with it
    state.payload_request_chain_root = compute_payload_request_chain_root(
        state, parent_bid, requests
    )

    apply_parent_execution_payload(state, requests)
```
