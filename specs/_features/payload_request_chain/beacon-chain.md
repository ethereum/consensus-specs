# Deferred Payload Verification -- The Beacon Chain

*Note*: This document is a work-in-progress for researchers and implementers.

## Table of contents

<!-- mdformat-toc start --slug=github --no-anchors --maxlevel=6 --minlevel=2 -->

- [Table of contents](#table-of-contents)
- [Introduction](#introduction)
  - [Why `block_hash` suffices for the rest of the payload](#why-block_hash-suffices-for-the-rest-of-the-payload)
- [Constants](#constants)
- [Containers](#containers)
  - [New containers](#new-containers)
    - [New `ExecutionPayloadCommitment`](#new-executionpayloadcommitment)
    - [New `NewPayloadRequestCommitment`](#new-newpayloadrequestcommitment)
  - [Modified containers](#modified-containers)
    - [Modified `BeaconState`](#modified-beaconstate)
- [Helpers](#helpers)
  - [New `compute_execution_payload_commitment`](#new-compute_execution_payload_commitment)
  - [New `compute_new_payload_request_commitment`](#new-compute_new_payload_request_commitment)
  - [New `compute_payload_request_root`](#new-compute_payload_request_root)
  - [New `compute_payload_request_chain_root`](#new-compute_payload_request_chain_root)
- [Engine APIs](#engine-apis)
  - [Modified `verify_and_notify_new_payload`](#modified-verify_and_notify_new_payload)
  - [New `get_payload_request_chain_root`](#new-get_payload_request_chain_root)
- [Beacon chain state transition function](#beacon-chain-state-transition-function)
  - [Block processing](#block-processing)
    - [Modified `process_execution_payload_bid`](#modified-process_execution_payload_bid)

<!-- mdformat-toc end -->

## Introduction

These are the beacon-chain specifications that allow a consensus client to
verify execution payload commitments during range sync **without downloading
execution payloads**.

Since [EIP-7732](../../gloas/beacon-chain.md), the beacon-chain state transition
no longer consumes the execution payload: execution requests arrive in the
following block as `parent_execution_requests`, and withdrawals are computed
from beacon state. The only remaining dependency is the *cross-layer equality*
check in `verify_execution_payload_envelope`, which confirms that the payload
the execution client executed is the payload the beacon chain committed to. That
check needs the payload in hand, so a consensus client performing range sync
must either download every payload or leave the range unverified.

This specification introduces the **payload request root**, an SSZ commitment
over the inputs to `engine_newPayload` that the consensus layer either derives
from its own state or reads from the `ExecutionPayloadBid`. Chaining those roots
across blocks yields the **payload request chain root**, which lets an entire
sync range be reconciled between the two layers in a single comparison.

Verification is *deferred*, not delegated. The consensus client still performs
the correspondence check itself; it simply performs it once at the end of a
range rather than once per block. Execution validity remains delegated to the
execution client exactly as before.

This proposal is purely additive. `verify_execution_payload_envelope` keeps its
existing per-field checks — those already establish correspondence whenever the
payload is in hand, and the commitment exists for the case where it is not.

No existing container is modified other than `BeaconState`. In particular
`ExecutionPayload` and `ExecutionPayloadBid` are untouched, so generalized
indices, serialization and the engine API container layouts are unaffected.

### Why `block_hash` suffices for the rest of the payload

The commitment carries only the payload fields the consensus layer can
independently determine, plus `block_hash`. It does not enumerate the remaining
payload fields, because the execution block hash already commits to all of them:
`state_root`, `receipts_root`, `logs_bloom`, `block_number`, `gas_used`,
`extra_data`, `base_fee_per_gas`, `blob_gas_used`, `excess_blob_gas`,
`fee_recipient` (as `coinbase`), `transactions` (as `transactions_root`) and
`block_access_list` (as `block_access_list_hash`) are all fields of the RLP
header that `block_hash` is the keccak of, and the execution layer enforces that
correspondence when it validates the payload.

*Note*: this relies on the invariant that **every `ExecutionPayload` field is
committed to by `block_hash`**, which holds for all current fields. A future
fork that adds a payload field not covered by the execution block hash MUST also
add it to `ExecutionPayloadCommitment`, or that field will not be bound.

`versioned_hashes` and `execution_requests_root` are carried explicitly even
though the block hash commits to the same data, because it does so under
different schemes — blob hashes inside `transactions_root`, and requests as
`requests_hash`, an SHA256 digest of the flat encodings rather than the SSZ root
the bid carries. The consensus layer cannot invert either, so both sides compute
the SSZ form.

*Note*: This specification is built upon [Gloas](../../gloas/beacon-chain.md).

## Constants

| Name                                 | Value       |
| ------------------------------------ | ----------- |
| `PAYLOAD_REQUEST_CHAIN_ROOT_GENESIS` | `Bytes32()` |

## Containers

### New containers

#### New `ExecutionPayloadCommitment`

The payload-derived inputs to `engine_newPayload` that the consensus layer holds
without the payload. Fields appear in their `ExecutionPayload` relative order.

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

#### New `NewPayloadRequestCommitment`

Mirrors `NewPayloadRequest` field for field, so that coverage can be checked by
inspection. The two groups are nested rather than flattened so that each keeps a
private index space: under [EIP-7495](https://eips.ethereum.org/EIPS/eip-7495)
field positions are permanent and new fields append at the end, so a flat
container would permanently interleave payload-derived and request-level inputs
the first time either gained a field.

```python
class NewPayloadRequestCommitment(ProgressiveContainer):
    ACTIVE_FIELDS = active_fields(width=4)

    execution_payload: ExecutionPayloadCommitment
    versioned_hashes: VersionedHashes
    parent_beacon_block_root: Root
    execution_requests_root: Root
```

*Note*: this is a commitment, not a header. Its root is **not** equal to
`hash_tree_root(NewPayloadRequest)`, and `ExecutionPayloadCommitment`'s root is
**not** equal to `hash_tree_root(ExecutionPayload)`. Under EIP-7495 equal roots
would require equal field counts, since `hash_tree_root` of a progressive
container mixes in its `active_fields` bitvector. Implementations MUST NOT
substitute one root for the other.

### Modified containers

#### Modified `BeaconState`

One field is added: the running chain over the payload request root of every
full payload.

```python
class BeaconState(ProgressiveContainer):
    # [Modified in DeferredPayloadVerification]
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
    # [Modified in Gloas:EIP7688]
    validators: Validators
    # [Modified in Gloas:EIP7688]
    balances: Balances
    randao_mixes: RandaoMixes
    slashings: Slashings
    # [Modified in Gloas:EIP7688]
    previous_epoch_participation: EpochParticipation
    # [Modified in Gloas:EIP7688]
    current_epoch_participation: EpochParticipation
    justification_bits: JustificationBits
    previous_justified_checkpoint: Checkpoint
    current_justified_checkpoint: Checkpoint
    finalized_checkpoint: Checkpoint
    # [Modified in Gloas:EIP7688]
    inactivity_scores: InactivityScores
    current_sync_committee: SyncCommittee
    next_sync_committee: SyncCommittee
    # [Modified in Gloas:EIP7732]
    # Removed `latest_execution_payload_header`
    # [New in Gloas:EIP7732]
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
    # [Modified in Gloas:EIP7688]
    pending_deposits: PendingDeposits
    # [Modified in Gloas:EIP7688]
    pending_partial_withdrawals: PendingPartialWithdrawals
    # [Modified in Gloas:EIP7688]
    pending_consolidations: PendingConsolidations
    proposer_lookahead: ProposerLookahead
    # [New in Gloas:EIP7732]
    builders: Builders
    # [New in Gloas:EIP7732]
    next_withdrawal_builder_index: BuilderIndex
    # [New in Gloas:EIP7732]
    execution_payload_availability: ExecutionPayloadAvailability
    # [New in Gloas:EIP7732]
    builder_pending_payments: BuilderPendingPayments
    # [New in Gloas:EIP7732]
    builder_pending_withdrawals: BuilderPendingWithdrawals
    # [New in Gloas:EIP7732]
    latest_execution_payload_bid: ExecutionPayloadBid
    # [New in Gloas:EIP7732]
    payload_expected_withdrawals: Withdrawals
    # [New in Gloas:EIP7732]
    ptc_window: PayloadTimelinessCommitteeWindow
    # [New in DeferredPayloadVerification]
    payload_request_chain_root: Bytes32
```

## Helpers

### New `compute_execution_payload_commitment`

Every field is either carried by the bid or derived from state; none requires
the payload.

```python
def compute_execution_payload_commitment(
    state: BeaconState, bid: ExecutionPayloadBid
) -> ExecutionPayloadCommitment:
    """
    Return the ``ExecutionPayloadCommitment`` committed to by ``bid``.
    """
    return ExecutionPayloadCommitment(
        parent_hash=bid.parent_block_hash,
        prev_randao=bid.prev_randao,
        gas_limit=bid.gas_limit,
        timestamp=compute_time_at_slot(state, bid.slot),
        block_hash=bid.block_hash,
        withdrawals=state.payload_expected_withdrawals,
        slot_number=bid.slot,
    )
```

### New `compute_new_payload_request_commitment`

```python
def compute_new_payload_request_commitment(
    state: BeaconState, bid: ExecutionPayloadBid
) -> NewPayloadRequestCommitment:
    """
    Return the ``NewPayloadRequestCommitment`` committed to by ``bid``.
    """
    versioned_hashes = VersionedHashes(
        data=[
            kzg_commitment_to_versioned_hash(commitment) for commitment in bid.blob_kzg_commitments
        ]
    )
    return NewPayloadRequestCommitment(
        execution_payload=compute_execution_payload_commitment(state, bid),
        versioned_hashes=versioned_hashes,
        parent_beacon_block_root=state.latest_block_header.parent_root,
        execution_requests_root=bid.execution_requests_root,
    )
```

### New `compute_payload_request_root`

```python
def compute_payload_request_root(state: BeaconState, bid: ExecutionPayloadBid) -> Root:
    """
    Return the payload request root committed to by ``bid``.
    """
    return hash_tree_root(compute_new_payload_request_commitment(state, bid))
```

### New `compute_payload_request_chain_root`

The chain advances once per **full** payload, never per slot. When a slot's
payload is missing the execution layer produces no block, so there is no payload
request root to fold in.

```python
def compute_payload_request_chain_root(
    previous_chain_root: Bytes32, payload_request_root: Root
) -> Bytes32:
    """
    Return the payload request chain root extended by ``payload_request_root``.
    """
    return sha256(previous_chain_root + payload_request_root)
```

## Engine APIs

### Modified `verify_and_notify_new_payload`

The consensus client MAY assert its expected chain root when delivering a
payload. This is the reconciliation point after a range sync.

When `payload_request_chain_root` is present, the execution client computes the
payload request root of `new_payload_request`, folds it into the chain it has
accumulated over the blocks it has executed, and compares the result against the
supplied value. The supplied value therefore covers the chain **through this
payload**, not through its parent.

If the execution client has not executed every ancestor — for example because
its state was acquired by snap sync — it cannot compute the chain and MUST
report that it is still syncing rather than reject the payload. Only a computed
mismatch is a rejection.

`payload_request_chain_root` is optional so that the method remains backwards
compatible and so that steady-state operation, where each payload is verified
individually, carries no additional data.

```python
def verify_and_notify_new_payload(
    self: ExecutionEngine,
    new_payload_request: NewPayloadRequest,
    # [New in DeferredPayloadVerification]
    payload_request_chain_root: Optional[Bytes32] = None,
) -> bool:
    """
    Return ``True`` if and only if ``new_payload_request`` is valid with respect
    to ``self.execution_state``, and, when ``payload_request_chain_root`` is
    present, the execution client's own payload request chain root through this
    payload equals it.
    """
```

After a range sync in which no payload envelopes were downloaded, a consensus
client holds a `payload_request_chain_root` covering every full payload in the
range, accumulated purely from beacon blocks. It reconciles that value with the
execution client the first time it delivers a payload, by passing
`state.payload_request_chain_root` to `verify_and_notify_new_payload`. A
negative result means the two layers do not agree on the range: the consensus
client MUST NOT treat the range as verified, and SHOULD locate the divergence
with `get_payload_request_chain_root` before discarding state.

### New `get_payload_request_chain_root`

A chained commitment reports *that* two chains diverged, never *where*. This
method lets a consensus client locate the divergence by binary search over the
range it synced.

The execution client can only answer for blocks it has **executed**. A block
whose state was acquired by other means, for example snap sync, has no payload
request chain root, and the method returns `None`.

```python
def get_payload_request_chain_root(self: ExecutionEngine, block_hash: Hash32) -> Optional[Bytes32]:
    """
    Return the payload request chain root at ``block_hash``, or ``None`` if the
    block is unknown, not canonical, or has not been executed.
    """
```

## Beacon chain state transition function

### Block processing

#### Modified `process_execution_payload_bid`

`process_execution_payload_bid` is modified to extend the payload request chain.
It already runs during range sync with no payload available, and it already runs
after `process_withdrawals` — so `state.payload_expected_withdrawals` holds the
withdrawals this slot's payload must honor — and after
`process_parent_execution_payload`, so `state.latest_block_hash` is current.

```python
def process_execution_payload_bid(
    state: BeaconState, signed_bid: SignedExecutionPayloadBid
) -> None:
    bid = signed_bid.message
    builder_index = bid.builder_index
    amount = bid.value

    # For self-builds, amount must be zero regardless of withdrawal credential prefix
    if builder_index == BUILDER_INDEX_SELF_BUILD:
        assert amount == 0
        assert signed_bid.signature == bls.G2_POINT_AT_INFINITY
    else:
        # Verify that the builder is active
        assert is_active_builder(state, builder_index)
        # Verify that the builder is a payload builder
        assert state.builders[builder_index].version == PAYLOAD_BUILDER_VERSION
        # Verify that the builder has funds to cover the bid
        assert can_builder_cover_bid(state, builder_index, amount)
        # Verify that the bid signature is valid
        assert verify_execution_payload_bid_signature(state, signed_bid)

    # Verify commitments are under limit
    assert (
        len(bid.blob_kzg_commitments)
        <= get_blob_parameters(get_current_epoch(state)).max_blobs_per_block
    )

    # Verify that the bid is for the current slot
    assert bid.slot == state.slot
    assert state.slot > GENESIS_SLOT
    # Verify that the bid is for the right parent block
    assert bid.parent_block_hash == state.latest_block_hash
    # Verify that the bid's block hash differs from its parent block hash
    assert bid.block_hash != bid.parent_block_hash
    assert bid.parent_block_root == get_block_root_at_slot(state, state.slot - 1)
    assert bid.prev_randao == get_randao_mix(state, get_current_epoch(state))

    # Record the pending payment if there is some payment
    if amount > 0:
        pending_payment = BuilderPendingPayment(
            weight=Gwei(0),
            withdrawal=BuilderPendingWithdrawal(
                fee_recipient=bid.fee_recipient,
                amount=amount,
                builder_index=builder_index,
            ),
            proposer_index=get_beacon_proposer_index(state),
        )
        state.builder_pending_payments[SLOTS_PER_EPOCH + bid.slot % SLOTS_PER_EPOCH] = (
            pending_payment
        )

    # [New in DeferredPayloadVerification]
    # Extend the payload request chain with this bid's commitment
    state.payload_request_chain_root = compute_payload_request_chain_root(
        state.payload_request_chain_root, compute_payload_request_root(state, bid)
    )

    # Cache the signed execution payload bid
    state.latest_execution_payload_bid = bid
```
