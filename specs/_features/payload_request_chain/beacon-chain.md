# Deferred Payload Verification -- The Beacon Chain

*Note*: This document is a work-in-progress for researchers and implementers.

## Table of contents

<!-- mdformat-toc start --slug=github --no-anchors --maxlevel=6 --minlevel=2 -->

- [Table of contents](#table-of-contents)
- [Introduction](#introduction)
  - [Why `block_hash` suffices for the rest of the payload](#why-block_hash-suffices-for-the-rest-of-the-payload)
  - [Computable without execution](#computable-without-execution)
  - [Anchoring](#anchoring)
- [Constants](#constants)
- [Containers](#containers)
  - [New containers](#new-containers)
    - [New `ExecutionPayloadCommitment`](#new-executionpayloadcommitment)
    - [New `NewPayloadRequestCommitment`](#new-newpayloadrequestcommitment)
  - [Modified containers](#modified-containers)
    - [Modified `BeaconState`](#modified-beaconstate)
- [Helpers](#helpers)
  - [New `compute_execution_payload_commitment`](#new-compute_execution_payload_commitment)
  - [Modified `get_execution_requests_list`](#modified-get_execution_requests_list)
  - [New `compute_requests_hash`](#new-compute_requests_hash)
  - [New `compute_new_payload_request_commitment`](#new-compute_new_payload_request_commitment)
  - [New `compute_payload_request_root`](#new-compute_payload_request_root)
  - [New `compute_payload_request_chain_root`](#new-compute_payload_request_chain_root)
- [Engine APIs](#engine-apis)
  - [New `verify_payload_request_chain_root`](#new-verify_payload_request_chain_root)
- [Beacon chain state transition function](#beacon-chain-state-transition-function)
  - [Block processing](#block-processing)
    - [Modified `process_parent_execution_payload`](#modified-process_parent_execution_payload)

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

This mechanism is orthogonal to payload validity. It adds no execution-layer
header field, no execution-layer block validity rule, and no change to what
makes a payload valid. The chain root is derived metadata that each layer
maintains while verifying blocks, compared over the engine API. A mismatch means
the beacon chain committed to something the execution chain does not contain —
an invalidity of the *beacon* chain, concluded by the consensus client, not of
any execution block.

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

`versioned_hashes` and `requests_hash` are carried explicitly even though the
block hash commits to the same data, because it does so under forms the
consensus layer cannot invert: blob hashes live inside `transactions_root`, and
requests are committed as `requests_hash`. The consensus layer re-derives
`requests_hash` from the same `execution_requests_list` it already produces for
`is_valid_block_hash`, and the execution layer reads it straight from the
header.

### Computable without execution

Every input is available from block data alone:

| Input                                                                                             | Source                                 |
| ------------------------------------------------------------------------------------------------- | -------------------------------------- |
| `parent_hash`, `prev_randao`, `gas_limit`, `timestamp`, `slot_number`, `parent_beacon_block_root` | execution header                       |
| `block_hash`                                                                                      | the header's own hash                  |
| `withdrawals`                                                                                     | block body                             |
| `versioned_hashes`                                                                                | block body, from the blob transactions |
| `requests_hash`                                                                                   | execution header                       |

No field requires executing the block. An execution client can therefore
maintain the chain over any range it holds block data for, including blocks
backfilled after a snap sync that it will never execute. This is deliberately
weaker than requiring an executed chain, and is what keeps the mechanism usable
on a freshly bootstrapped node.

Two inputs do require the block **body**: `withdrawals`, and `versioned_hashes`
via the blob transactions. An execution client should therefore extend the chain
where the body is validated against the header, not during header validation
alone, since clients sync headers ahead of bodies.

This is not a meaningful constraint in practice. The chain covers the range from
the anchor forward, which is the range the node follows live and therefore holds
bodies for; and [EIP-4444](https://eips.ethereum.org/EIPS/eip-4444) scopes
execution-layer history pruning to "older than the consensus-layer block
retention window", so body retention and the anchored range are bounded by the
same window. Blocks whose bodies have expired are blocks before the anchor,
which the chain does not cover.

This is also why `requests_hash` is used in place of the bid's
`execution_requests_root`: execution requests are *produced by* execution, so
their SSZ root is unavailable to a client that has not executed the block, while
`requests_hash` is a header field.

### Anchoring

`payload_request_chain_root` is part of `BeaconState`, so it is carried by a
weak-subjectivity checkpoint. A consensus client that checkpoint-syncs trusts
the anchor's value exactly as it trusts the rest of the anchor state, and
supplies it to the execution client as the base to fold from. An execution
client with no chain of its own MUST adopt a supplied base rather than starting
from `PAYLOAD_REQUEST_CHAIN_ROOT_GENESIS`, which it could not otherwise
reproduce.

The guarantee is therefore anchored at the checkpoint, not at the fork: the
chain attests that the beacon chain and the execution chain agree over the range
since the anchor, and everything before it rests on weak subjectivity, as it
already does.

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
    requests_hash: Hash32
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

### Modified `get_execution_requests_list`

*Note*: `ExecutionRequests` gained `builder_deposits` and `builder_exits` in
Gloas via [EIP-8282](https://eips.ethereum.org/EIPS/eip-8282), which states that
the execution layer includes their `0x03` and `0x04` type bytes in the block
requests list committed by `requests_hash`. The Electra helper predates them and
emits only the first three types, so it is restated here in full. Without this
the consensus layer's re-derivation would diverge from the execution header
whenever a builder deposit or exit occurs.

```python
def get_execution_requests_list(execution_requests: ExecutionRequests) -> Sequence[bytes]:
    requests: Sequence[Tuple[Bytes1, ProgressiveList]] = [
        (DEPOSIT_REQUEST_TYPE, execution_requests.deposits),
        (WITHDRAWAL_REQUEST_TYPE, execution_requests.withdrawals),
        (CONSOLIDATION_REQUEST_TYPE, execution_requests.consolidations),
        # [New in Gloas:EIP8282]
        (BUILDER_DEPOSIT_REQUEST_TYPE, execution_requests.builder_deposits),
        # [New in Gloas:EIP8282]
        (BUILDER_EXIT_REQUEST_TYPE, execution_requests.builder_exits),
    ]

    return [
        request_type + ssz_serialize(request_data)
        for request_type, request_data in requests
        if len(request_data) != 0
    ]
```

### New `compute_requests_hash`

The [EIP-7685](https://eips.ethereum.org/EIPS/eip-7685) commitment that the
execution header already stores, re-derived here from the same
`execution_requests_list` the consensus layer hands the execution layer for
`is_valid_block_hash`.

```python
def compute_requests_hash(execution_requests_list: Sequence[bytes]) -> Hash32:
    """
    Return the SHA256 commitment over an ordered list of type-prefixed requests.
    """
    return Hash32(sha256(b"".join(sha256(request) for request in execution_requests_list)))
```

### New `compute_new_payload_request_commitment`

```python
def compute_new_payload_request_commitment(
    state: BeaconState, bid: ExecutionPayloadBid, requests: ExecutionRequests
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
        requests_hash=compute_requests_hash(get_execution_requests_list(requests)),
    )
```

### New `compute_payload_request_root`

```python
def compute_payload_request_root(
    state: BeaconState, bid: ExecutionPayloadBid, requests: ExecutionRequests
) -> Root:
    """
    Return the payload request root committed to by ``bid``.
    """
    return hash_tree_root(compute_new_payload_request_commitment(state, bid, requests))
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

### New `verify_payload_request_chain_root`

`engine_newPayload` gains an optional `payloadRequestChainRoot` request
parameter and a corresponding optional response field. The result is reported
**separately from `PayloadStatus`**: payload validity is determined by exactly
today's rules, and this comparison neither strengthens nor weakens it.

The execution client folds the payload request root of `new_payload_request`
into the chain it has accumulated over the ancestry and compares. The supplied
value therefore covers the chain **through this payload**, not through its
parent.

Three outcomes, and the distinction between the last two is the whole mechanism:

- **`True`** — the chains agree. The consensus client MAY consider every block
  in the range covered by the chain to correspond to the payloads the execution
  client holds.
- **`None`** — the execution client does not hold block data for the ancestry,
  or has no base to fold from, and therefore did not compare. This is not a
  disagreement. The consensus client continues delivering payloads as its head
  advances; the comparison resolves once the gap closes.
- **`False`** — the execution client held the ancestry, compared, and the roots
  differ. Some bid in the range committed to values the corresponding payload
  does not carry. The consensus client MUST NOT treat the range as verified and
  MUST treat its chain as invalid.

A consensus client whose execution client returns `None` simply keeps
delivering; there is nothing to recover and no divergence to locate. A `False`
result is terminal for that chain, and ordinary per-payload validation localises
the offending block through `latestValidHash` as payloads arrive.

```python
def verify_payload_request_chain_root(
    self: ExecutionEngine,
    new_payload_request: NewPayloadRequest,
    payload_request_chain_root: Bytes32,
) -> Optional[bool]:
    """
    Return ``True`` if the execution client's own payload request chain root
    through ``new_payload_request`` equals ``payload_request_chain_root``,
    ``False`` if it differs, and ``None`` if the client cannot compare.
    """
```

## Beacon chain state transition function

### Block processing

#### Modified `process_parent_execution_payload`

`process_parent_execution_payload` is modified to extend the payload request
chain. This is the correct point, for two independent reasons.

First, it is where a payload is known to be **FULL**. A bid is processed for
every block, but its payload may never be revealed; extending the chain when the
bid is processed would fold in payloads the execution layer never produced,
desynchronising the two chains on an entirely honest chain. Here the FULL/EMPTY
determination has already been made.

Second, it is where the parent's `ExecutionRequests` are available, as
`block.body.parent_execution_requests`.

Every other input is correct at this point in `process_block`, which runs this
function first: `state.latest_execution_payload_bid` is still the parent's bid,
`state.payload_expected_withdrawals` still holds the withdrawals that payload
had to honor (`process_withdrawals` has not yet run for this slot), and
`state.latest_block_header` is still the parent block's header, so its
`parent_root` is the parent payload's `parent_beacon_block_root`.

The chain therefore lags the beacon chain by one slot, which matches the
execution layer's own position.

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

    # [New in DeferredPayloadVerification]
    # The parent payload is now known to be FULL, so extend the chain with it
    state.payload_request_chain_root = compute_payload_request_chain_root(
        state.payload_request_chain_root,
        compute_payload_request_root(state, parent_bid, requests),
    )

    apply_parent_execution_payload(state, requests)
```
