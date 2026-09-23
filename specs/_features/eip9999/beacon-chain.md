# EIP-9999 -- The Beacon Chain

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
  - [New `compute_payload_request_chain_root`](#new-compute_payload_request_chain_root)
- [Engine APIs](#engine-apis)
  - [Modified `verify_and_notify_new_payload`](#modified-verify_and_notify_new_payload)
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
over a subset of the fields of `NewPayloadRequest`: those the consensus layer
either derives from its own state or reads from the `ExecutionPayloadBid`, plus
`block_hash`, through which the execution block hash binds every remaining
payload field. Chaining those roots across blocks yields the **payload request
chain root**, which lets an entire sync range be reconciled between the two
layers in a single comparison.

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
weak-subjectivity checkpoint, and a consensus client that checkpoint-syncs holds
the correct value without having derived it.

The only value a consensus client ever sends is the current one, through the
payload being delivered. An execution client that holds no accumulator of its
own has nothing to compare that value against, and MUST adopt it as its own and
continue from there. It cannot instead begin from
`PAYLOAD_REQUEST_CHAIN_ROOT_GENESIS`, since the history the value covers is
history it never held.

*Note*: This specification is built upon [Gloas](../../gloas/beacon-chain.md).

## Constants

| Name                                 | Value       |
| ------------------------------------ | ----------- |
| `PAYLOAD_REQUEST_CHAIN_ROOT_GENESIS` | `Bytes32()` |

## Containers

### New containers

#### New `ExecutionPayloadCommitment`

The payload-derived inputs to `engine_newPayload` that the consensus layer holds
without the payload. This is a subset of `ExecutionPayload`; the fields it omits
are bound through `block_hash`. Fields appear in their `ExecutionPayload`
relative order.

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

### Modified containers

#### Modified `BeaconState`

One field is added: the running chain over the payload request root of every
full payload.

```python
class BeaconState(ProgressiveContainer):
    # [Modified in EIP9999]
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
    # Removed `latest_execution_payload_header`
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

One helper does the whole job: build the commitment from the bid, beacon state
and block body, and fold it into the running chain.

Every input is either carried by the bid or derived from state; none requires
the execution payload. `requests_hash` is the
[EIP-7685](https://eips.ethereum.org/EIPS/eip-7685) digest that the execution
header already stores, re-derived from the same `execution_requests_list` the
consensus layer produces for `is_valid_block_hash`.

The chain advances once per **full** payload, never per slot. A slot whose
payload is not revealed produces no execution block, so it contributes nothing.

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
            timestamp=compute_time_at_slot(state, bid.slot),
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

`engine_newPayload` gains a `payload_request_chain_root` argument carrying the
consensus client's chain root **through this payload**. No new engine method is
introduced.

The argument is **required**, following `parent_beacon_block_root` and
`execution_requests`, which were likewise added as required parameters of a new
method version. Compatibility comes from versioning: clients that do not
implement this EIP continue to use the previous method version. Making the
argument omissible would instead create a silent downgrade, in which a consensus
client that never supplies it is never verified and nothing reports that.

The execution client compares the supplied value against its own payload request
chain root:

- It MUST return `True` only if the payload is valid and the two are consistent.
  On the wire this is `VALID`.
- It MUST return `False` if the two are inconsistent. The beacon chain has
  committed to a payload the execution chain does not contain. On the wire this
  is `INVALID`, distinguished from a payload that failed validation by
  `validationError`.
- It MUST return `False` if it cannot yet determine consistency, because it does
  not hold the block data for the ancestry or holds no chain of its own. On the
  wire this is `SYNCING`, which is not a disagreement and resolves as the
  consensus client continues delivering payloads. A client with no chain of its
  own adopts the supplied value as its own.
- It MUST NOT require the block to have been executed in order to compute its
  own value. Every input is drawn from the execution header or the block body.

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

    # [New in EIP9999]
    # The parent payload is now known to be FULL, so extend the chain with it
    state.payload_request_chain_root = compute_payload_request_chain_root(
        state, parent_bid, requests
    )

    apply_parent_execution_payload(state, requests)
```
