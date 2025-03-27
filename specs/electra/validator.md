# Electra -- Honest Validator

*Note*: This document is a work-in-progress for researchers and implementers.

## Table of contents

<!-- TOC -->
<!-- START doctoc generated TOC please keep comment here to allow auto update -->
<!-- DON'T EDIT THIS SECTION, INSTEAD RE-RUN doctoc TO UPDATE -->

- [Introduction](#introduction)
- [Prerequisites](#prerequisites)
- [Helpers](#helpers)
  - [Modified `GetPayloadResponse`](#modified-getpayloadresponse)
- [Containers](#containers)
  - [Modified Containers](#modified-containers)
    - [`AggregateAndProof`](#aggregateandproof)
    - [`SignedAggregateAndProof`](#signedaggregateandproof)
- [Protocol](#protocol)
  - [`ExecutionEngine`](#executionengine)
    - [Modified `get_payload`](#modified-get_payload)
- [Block proposal](#block-proposal)
  - [Constructing the `BeaconBlockBody`](#constructing-the-beaconblockbody)
    - [Attester slashings](#attester-slashings)
    - [Attestations](#attestations)
    - [Deposits](#deposits)
    - [Execution payload](#execution-payload)
    - [Execution Requests](#execution-requests)
  - [Constructing the `BlobSidecar`s](#constructing-the-blobsidecars)
    - [Sidecar](#sidecar)
- [Attesting](#attesting)
  - [Construct attestation](#construct-attestation)
- [Attestation aggregation](#attestation-aggregation)
  - [Construct aggregate](#construct-aggregate)

<!-- END doctoc generated TOC please keep comment here to allow auto update -->
<!-- /TOC -->

## Introduction

This document represents the changes to be made in the code of an "honest validator" to implement Electra.

## Prerequisites

This document is an extension of the [Deneb -- Honest Validator](../deneb/validator.md) guide.
All behaviors and definitions defined in this document, and documents it extends, carry over unless explicitly noted or overridden.

All terminology, constants, functions, and protocol mechanics defined in the updated Beacon Chain doc of [Electra](./beacon-chain.md) are requisite for this document and used throughout.
Please see related Beacon Chain doc before continuing and use them as a reference throughout.

## Helpers

### Modified `GetPayloadResponse`

```python
@dataclass
class GetPayloadResponse(object):
    execution_payload: ExecutionPayload
    block_value: uint256
    blobs_bundle: BlobsBundle
    execution_requests: Sequence[bytes]  # [New in Electra]
```

## Containers

### Modified Containers

#### `AggregateAndProof`

```python
class AggregateAndProof(Container):
    aggregator_index: ValidatorIndex
    aggregate: Attestation  # [Modified in Electra:EIP7549]
    selection_proof: BLSSignature
```

#### `SignedAggregateAndProof`

```python
class SignedAggregateAndProof(Container):
    message: AggregateAndProof   # [Modified in Electra:EIP7549]
    signature: BLSSignature
```

## Protocol

### `ExecutionEngine`

#### Modified `get_payload`

Given the `payload_id`, `get_payload` returns the most recent version of the execution payload that
has been built since the corresponding call to `notify_forkchoice_updated` method.

```python
def get_payload(self: ExecutionEngine, payload_id: PayloadId) -> GetPayloadResponse:
    """
    Return ExecutionPayload, uint256, BlobsBundle and execution requests (as Sequence[bytes]) objects.
    """
    # pylint: disable=unused-argument
    ...
```

## Block proposal

### Constructing the `BeaconBlockBody`

#### Attester slashings

Changed the max attester slashings size to `MAX_ATTESTER_SLASHINGS_ELECTRA`.

#### Attestations

Changed the max attestations size to `MAX_ATTESTATIONS_ELECTRA`.

The network attestation aggregates contain only the assigned committee attestations.
Attestation aggregates received by the block proposer from the committee aggregators with disjoint `committee_bits` sets and equal `AttestationData` SHOULD be consolidated into a single `Attestation` object.
The proposer should run the following function to construct an on chain final aggregate from a list of network aggregates with equal `AttestationData`:

```python
def compute_on_chain_aggregate(network_aggregates: Sequence[Attestation]) -> Attestation:
    aggregates = sorted(network_aggregates, key=lambda a: get_committee_indices(a.committee_bits)[0])

    data = aggregates[0].data
    aggregation_bits = Bitlist[MAX_VALIDATORS_PER_COMMITTEE * MAX_COMMITTEES_PER_SLOT]()
    for a in aggregates:
        for b in a.aggregation_bits:
            aggregation_bits.append(b)

    signature = bls.Aggregate([a.signature for a in aggregates])

    committee_indices = [get_committee_indices(a.committee_bits)[0] for a in aggregates]
    committee_flags = [(index in committee_indices) for index in range(0, MAX_COMMITTEES_PER_SLOT)]
    committee_bits = Bitvector[MAX_COMMITTEES_PER_SLOT](committee_flags)

    return Attestation(
        aggregation_bits=aggregation_bits,
        data=data,
        committee_bits=committee_bits,
        signature=signature,
    )
```

#### Deposits

*[New in Electra:EIP6110]* The expected number of deposits MUST be changed from `min(MAX_DEPOSITS, eth1_data.deposit_count - state.eth1_deposit_index)` to the result of the following function:

```python
def get_eth1_pending_deposit_count(state: BeaconState) -> uint64:
    eth1_deposit_index_limit = min(state.eth1_data.deposit_count, state.deposit_requests_start_index)
    if state.eth1_deposit_index < eth1_deposit_index_limit:
        return min(MAX_DEPOSITS, eth1_deposit_index_limit - state.eth1_deposit_index)
    else:
        return uint64(0)
```

*Note*: Clients will be able to remove the `Eth1Data` polling mechanism in an uncoordinated fashion once the transition period is finished. The transition period is considered finished when a network reaches the point where `state.eth1_deposit_index == state.deposit_requests_start_index`.

```python
def get_eth1_vote(state: BeaconState, eth1_chain: Sequence[Eth1Block]) -> Eth1Data:
    # [New in Electra:EIP6110]
    if state.eth1_deposit_index == state.deposit_requests_start_index:
        return state.eth1_data

    period_start = voting_period_start_time(state)
    # `eth1_chain` abstractly represents all blocks in the eth1 chain sorted by ascending block height
    votes_to_consider = [
        get_eth1_data(block) for block in eth1_chain
        if (
            is_candidate_block(block, period_start)
            # Ensure cannot move back to earlier deposit contract states
            and get_eth1_data(block).deposit_count >= state.eth1_data.deposit_count
        )
    ]

    # Valid votes already cast during this period
    valid_votes = [vote for vote in state.eth1_data_votes if vote in votes_to_consider]

    # Default vote on latest eth1 block data in the period range unless eth1 chain is not live
    # Non-substantive casting for linter
    state_eth1_data: Eth1Data = state.eth1_data
    default_vote = votes_to_consider[len(votes_to_consider) - 1] if any(votes_to_consider) else state_eth1_data

    return max(
        valid_votes,
        key=lambda v: (valid_votes.count(v), -valid_votes.index(v)),  # Tiebreak by smallest distance
        default=default_vote
    )
```

#### Execution payload

`prepare_execution_payload` is updated from the Deneb specs.

*Note*: In this section, `state` is the state of the slot for the block proposal _without_ the block yet applied.
That is, `state` is the `previous_state` processed through any empty slots up to the assigned slot using `process_slots(previous_state, slot)`.

*Note*: The only change to `prepare_execution_payload` is the new definition of `get_expected_withdrawals`.

```python
def prepare_execution_payload(state: BeaconState,
                              safe_block_hash: Hash32,
                              finalized_block_hash: Hash32,
                              suggested_fee_recipient: ExecutionAddress,
                              execution_engine: ExecutionEngine) -> Optional[PayloadId]:
    # Verify consistency of the parent hash with respect to the previous execution payload header
    parent_hash = state.latest_execution_payload_header.block_hash

    # Set the forkchoice head and initiate the payload build process
    withdrawals, _ = get_expected_withdrawals(state)  # [Modified in EIP-7251]

    payload_attributes = PayloadAttributes(
        timestamp=compute_timestamp_at_slot(state, state.slot),
        prev_randao=get_randao_mix(state, get_current_epoch(state)),
        suggested_fee_recipient=suggested_fee_recipient,
        withdrawals=withdrawals,
        parent_beacon_block_root=hash_tree_root(state.latest_block_header),
    )
    return execution_engine.notify_forkchoice_updated(
        head_block_hash=parent_hash,
        safe_block_hash=safe_block_hash,
        finalized_block_hash=finalized_block_hash,
        payload_attributes=payload_attributes,
    )
```

#### Execution Requests

*[New in Electra]*

1. The execution payload is obtained from the execution engine as defined above using `payload_id`. The response also includes a `execution_requests` entry containing a list of bytes. Each element on the list corresponds to one SSZ list of requests as defined in [EIP-7685](https://eips.ethereum.org/EIPS/eip-7685). The first byte of each request is used to determine the request type. Requests must be ordered by request type in ascending order. As a result, there can only be at most one instance of each request type.
2. Set `block.body.execution_requests = get_execution_requests(execution_requests)`, where:

```python
def get_execution_requests(execution_requests_list: Sequence[bytes]) -> ExecutionRequests:
    deposits = []
    withdrawals = []
    consolidations = []

    request_types = [
        DEPOSIT_REQUEST_TYPE,
        WITHDRAWAL_REQUEST_TYPE,
        CONSOLIDATION_REQUEST_TYPE,
    ]

    prev_request_type = None
    for request in execution_requests_list:
        request_type, request_data = request[0:1], request[1:]

        # Check that the request type is valid
        assert request_type in request_types
        # Check that the request data is not empty
        assert len(request_data) != 0
        # Check that requests are in strictly ascending order
        # Each successive type must be greater than the last with no duplicates
        assert prev_request_type is None or prev_request_type < request_type
        prev_request_type = request_type

        if request_type == DEPOSIT_REQUEST_TYPE:
            deposits = ssz_deserialize(
                List[DepositRequest, MAX_DEPOSIT_REQUESTS_PER_PAYLOAD],
                request_data
            )
        elif request_type == WITHDRAWAL_REQUEST_TYPE:
            withdrawals = ssz_deserialize(
                List[WithdrawalRequest, MAX_WITHDRAWAL_REQUESTS_PER_PAYLOAD],
                request_data
            )
        elif request_type == CONSOLIDATION_REQUEST_TYPE:
            consolidations = ssz_deserialize(
                List[ConsolidationRequest, MAX_CONSOLIDATION_REQUESTS_PER_PAYLOAD],
                request_data
            )

    return ExecutionRequests(
        deposits=deposits,
        withdrawals=withdrawals,
        consolidations=consolidations,
    )
```

### Constructing the `BlobSidecar`s

#### Sidecar

*[Modified in Electra:EIP7691]*

```python
def compute_subnet_for_blob_sidecar(blob_index: BlobIndex) -> SubnetID:
    return SubnetID(blob_index % BLOB_SIDECAR_SUBNET_COUNT_ELECTRA)
```

## Attesting

### Construct attestation

The validator creates `attestation` as a `SingleAttestation` container
with updated field assignments:

- Set `attestation_data.index = 0`.
- Set `attestation.committee_index` to the index associated with the validator's committee.
- Set `attestation.attester_index` to the index of the validator.

## Attestation aggregation

### Construct aggregate

- Set `attestation_data.index = 0`.
- Let `aggregation_bits` be a `Bitlist[MAX_VALIDATORS_PER_COMMITTEE * MAX_COMMITTEES_PER_SLOT]` of length `len(committee)`, where each bit set from each individual attestation is set to `0b1`.
- Set `attestation.committee_bits = committee_bits`, where `committee_bits` has the bit set corresponding to `committee_index` in each individual attestation.
