# Deneb -- Networking

<!-- mdformat-toc start --slug=github --no-anchors --maxlevel=6 --minlevel=2 -->

- [Introduction](#introduction)
- [Modifications in Deneb](#modifications-in-deneb)
  - [Preset](#preset)
  - [Configuration](#configuration)
  - [Containers](#containers)
    - [`BlobSidecar`](#blobsidecar)
    - [`BlobIdentifier`](#blobidentifier)
  - [Helpers](#helpers)
    - [Modified `Seen`](#modified-seen)
    - [Modified `compute_fork_version`](#modified-compute_fork_version)
    - [New `compute_max_request_blob_sidecars`](#new-compute_max_request_blob_sidecars)
    - [`verify_blob_sidecar_inclusion_proof`](#verify_blob_sidecar_inclusion_proof)
  - [The gossip domain: gossipsub](#the-gossip-domain-gossipsub)
    - [Topics and messages](#topics-and-messages)
      - [Global topics](#global-topics)
        - [`beacon_block`](#beacon_block)
        - [`beacon_aggregate_and_proof`](#beacon_aggregate_and_proof)
        - [`voluntary_exit`](#voluntary_exit)
      - [Blob subnets](#blob-subnets)
        - [`blob_sidecar_{subnet_id}`](#blob_sidecar_subnet_id)
        - [Blob retrieval via local execution-layer client](#blob-retrieval-via-local-execution-layer-client)
      - [Attestation subnets](#attestation-subnets)
        - [`beacon_attestation_{subnet_id}`](#beacon_attestation_subnet_id)
    - [Transitioning the gossip](#transitioning-the-gossip)
  - [The Req/Resp domain](#the-reqresp-domain)
    - [Messages](#messages)
      - [BeaconBlocksByRange v2](#beaconblocksbyrange-v2)
      - [BeaconBlocksByRoot v2](#beaconblocksbyroot-v2)
      - [BlobSidecarsByRange v1](#blobsidecarsbyrange-v1)
      - [BlobSidecarsByRoot v1](#blobsidecarsbyroot-v1)
- [Design decision rationale](#design-decision-rationale)
  - [Why are blobs relayed as a sidecar, separate from beacon blocks?](#why-are-blobs-relayed-as-a-sidecar-separate-from-beacon-blocks)

<!-- mdformat-toc end -->

## Introduction

This document contains the consensus-layer networking specifications for Deneb.

The specification of these changes continues in the same format as the network
specifications of previous upgrades, and assumes them as pre-requisite.

## Modifications in Deneb

### Preset

*[New in Deneb:EIP4844]*

| Name                                   | Value                                                                                                                                     | Description                                                                 |
| -------------------------------------- | ----------------------------------------------------------------------------------------------------------------------------------------- | --------------------------------------------------------------------------- |
| `KZG_COMMITMENT_INCLUSION_PROOF_DEPTH` | `uint64(floorlog2(get_generalized_index(BeaconBlockBody, 'blob_kzg_commitments')) + 1 + ceillog2(MAX_BLOB_COMMITMENTS_PER_BLOCK))` (= 17) | <!-- predefined --> Merkle proof depth for `blob_kzg_commitments` list item |

### Configuration

*[New in Deneb:EIP4844]*

| Name                                    | Value                    | Description                                                        |
| --------------------------------------- | ------------------------ | ------------------------------------------------------------------ |
| `MAX_REQUEST_BLOCKS_DENEB`              | `2**7` (= 128)           | Maximum number of blocks in a single request                       |
| `MIN_EPOCHS_FOR_BLOB_SIDECARS_REQUESTS` | `2**12` (= 4,096 epochs) | The minimum epoch range over which a node must serve blob sidecars |
| `BLOB_SIDECAR_SUBNET_COUNT`             | `6`                      | The number of blob sidecar subnets used in the gossipsub protocol  |

### Containers

#### `BlobSidecar`

*[New in Deneb:EIP4844]*

*Note*: `index` is the index of the blob in the block.

```python
class BlobSidecar(Container):
    index: BlobIndex
    blob: Blob
    kzg_commitment: KZGCommitment
    kzg_proof: KZGProof
    signed_block_header: SignedBeaconBlockHeader
    kzg_commitment_inclusion_proof: Vector[Bytes32, KZG_COMMITMENT_INCLUSION_PROOF_DEPTH]
```

#### `BlobIdentifier`

*[New in Deneb:EIP4844]*

```python
class BlobIdentifier(Container):
    block_root: Root
    index: BlobIndex
```

### Helpers

#### Modified `Seen`

```python
@dataclass
class Seen(object):
    proposer_slots: Set[Tuple[ValidatorIndex, Slot]]
    aggregator_epochs: Set[Tuple[ValidatorIndex, Epoch]]
    aggregate_data_roots: Dict[Root, Set[Tuple[boolean, ...]]]
    voluntary_exit_indices: Set[ValidatorIndex]
    proposer_slashing_indices: Set[ValidatorIndex]
    attester_slashing_indices: Set[ValidatorIndex]
    attestation_validator_epochs: Set[Tuple[ValidatorIndex, Epoch]]
    sync_contribution_aggregator_slots: Set[Tuple[ValidatorIndex, Slot, uint64]]
    sync_contribution_data: Dict[Tuple[Slot, Root, uint64], Set[Tuple[boolean, ...]]]
    sync_message_validator_slots: Set[Tuple[Slot, ValidatorIndex, uint64]]
    bls_to_execution_change_indices: Set[ValidatorIndex]
    # [New in Deneb]
    blob_sidecar_tuples: Set[Tuple[Slot, ValidatorIndex, BlobIndex]]
```

#### Modified `compute_fork_version`

```python
def compute_fork_version(epoch: Epoch) -> Version:
    """
    Return the fork version at the given ``epoch``.
    """
    if epoch >= DENEB_FORK_EPOCH:
        return DENEB_FORK_VERSION
    if epoch >= CAPELLA_FORK_EPOCH:
        return CAPELLA_FORK_VERSION
    if epoch >= BELLATRIX_FORK_EPOCH:
        return BELLATRIX_FORK_VERSION
    if epoch >= ALTAIR_FORK_EPOCH:
        return ALTAIR_FORK_VERSION
    return GENESIS_FORK_VERSION
```

#### New `compute_max_request_blob_sidecars`

```python
def compute_max_request_blob_sidecars() -> uint64:
    """
    Return the maximum number of blob sidecars in a single request.
    """
    return uint64(MAX_REQUEST_BLOCKS_DENEB * MAX_BLOBS_PER_BLOCK)
```

#### `verify_blob_sidecar_inclusion_proof`

```python
def verify_blob_sidecar_inclusion_proof(blob_sidecar: BlobSidecar) -> bool:
    gindex = get_subtree_index(
        get_generalized_index(BeaconBlockBody, "blob_kzg_commitments", blob_sidecar.index)
    )
    return is_valid_merkle_branch(
        leaf=blob_sidecar.kzg_commitment.hash_tree_root(),
        branch=blob_sidecar.kzg_commitment_inclusion_proof,
        depth=KZG_COMMITMENT_INCLUSION_PROOF_DEPTH,
        index=gindex,
        root=blob_sidecar.signed_block_header.message.body_root,
    )
```

### The gossip domain: gossipsub

Some gossip meshes are upgraded in Deneb to support upgraded types.

#### Topics and messages

Topics follow the same specification as in prior upgrades.

The `beacon_block` topic is modified to also support Deneb blocks and new topics
are added per table below.

The `voluntary_exit` topic is implicitly modified despite the lock-in use of
`CAPELLA_FORK_VERSION` for this message signature validation for EIP-7044.

The `beacon_aggregate_and_proof` and `beacon_attestation_{subnet_id}` topics are
modified to support the gossip of attestations created in epoch `N` throughout
all of epoch `N+1`, rather than only through
`ATTESTATION_PROPAGATION_SLOT_RANGE` slots, for EIP-7045.

The specification around the creation, validation, and dissemination of messages
has not changed from the Capella document unless explicitly noted here.

The derivation of the `message-id` remains stable.

The new topics along with the type of the `data` field of a gossipsub message
are given in this table:

| Name                       | Message Type                         |
| -------------------------- | ------------------------------------ |
| `blob_sidecar_{subnet_id}` | `BlobSidecar` [New in Deneb:EIP4844] |

##### Global topics

###### `beacon_block`

*Note*: This function is modified to validate the number of blob kzg commitments
included in the beacon block body.

```python
def validate_beacon_block_gossip(
    seen: Seen,
    store: Store,
    state: BeaconState,
    signed_beacon_block: SignedBeaconBlock,
    current_time_ms: uint64,
    block_payload_statuses: Dict[Root, PayloadValidationStatus] = {},
) -> None:
    """
    Validate a SignedBeaconBlock for gossip propagation.
    Raises GossipIgnore or GossipReject on validation failure.
    """
    block = signed_beacon_block.message
    execution_payload = block.body.execution_payload

    # [IGNORE] The block is not from a future slot
    # (MAY be queued for processing at the appropriate slot)
    if not is_not_from_future_slot(state, block.slot, current_time_ms):
        raise GossipIgnore("block is from a future slot")

    # [IGNORE] The block is from a slot greater than the latest finalized slot
    # (MAY choose to validate and store such blocks for additional purposes
    # -- e.g. slashing detection, archive nodes, etc)
    finalized_slot = compute_start_slot_at_epoch(store.finalized_checkpoint.epoch)
    if block.slot <= finalized_slot:
        raise GossipIgnore("block is not from a slot greater than the latest finalized slot")

    # [IGNORE] The block is the first block with valid signature received for the proposer for the slot
    if (block.proposer_index, block.slot) in seen.proposer_slots:
        raise GossipIgnore("block is not the first valid block for this proposer and slot")

    # [REJECT] The proposer index is a valid validator index
    if block.proposer_index >= len(state.validators):
        raise GossipReject("proposer index out of range")

    # [REJECT] The proposer signature is valid
    proposer = state.validators[block.proposer_index]
    domain = get_domain(state, DOMAIN_BEACON_PROPOSER, compute_epoch_at_slot(block.slot))
    signing_root = compute_signing_root(block, domain)
    if not bls.Verify(proposer.pubkey, signing_root, signed_beacon_block.signature):
        raise GossipReject("invalid proposer signature")

    # [IGNORE] The block's parent has been seen (via gossip or non-gossip sources)
    # (MAY be queued until parent is retrieved)
    if block.parent_root not in store.blocks:
        raise GossipIgnore("block's parent has not been seen")

    # [REJECT] The block's execution payload timestamp is correct with respect to the slot
    if execution_payload.timestamp != compute_time_at_slot(state, block.slot):
        raise GossipReject("incorrect execution payload timestamp")

    parent_payload_status = PAYLOAD_STATUS_NOT_VALIDATED
    if block.parent_root in block_payload_statuses:
        parent_payload_status = block_payload_statuses[block.parent_root]

    if block.parent_root not in store.block_states:
        if parent_payload_status == PAYLOAD_STATUS_NOT_VALIDATED:
            # [REJECT] The block's parent passes validation
            raise GossipReject("block's parent is invalid and EL result is unknown")

        # [IGNORE] The block's parent passes validation
        raise GossipIgnore("block's parent is invalid and EL result is known")

    # [IGNORE] The block's parent's execution payload passes validation
    if parent_payload_status == PAYLOAD_STATUS_INVALIDATED:
        raise GossipIgnore("block's parent is valid and EL result is invalid")

    # [REJECT] The block is from a higher slot than its parent
    if block.slot <= store.blocks[block.parent_root].slot:
        raise GossipReject("block is not from a higher slot than its parent")

    # [REJECT] The current finalized checkpoint is an ancestor of the block
    checkpoint_block = get_checkpoint_block(
        store, block.parent_root, store.finalized_checkpoint.epoch
    )
    if checkpoint_block != store.finalized_checkpoint.root:
        raise GossipReject("finalized checkpoint is not an ancestor of block")

    # [New in Deneb:EIP4844]
    # [REJECT] The length of KZG commitments is less than or equal to the limit
    if len(block.body.blob_kzg_commitments) > MAX_BLOBS_PER_BLOCK:
        raise GossipReject("too many blob kzg commitments")

    # [REJECT] The block is proposed by the expected proposer for the slot
    # (if shuffling is not available, IGNORE instead and MAY be queued for later)
    parent_state = store.block_states[block.parent_root].copy()
    process_slots(parent_state, block.slot)
    expected_proposer = get_beacon_proposer_index(parent_state)
    if block.proposer_index != expected_proposer:
        raise GossipReject("block proposer_index does not match expected proposer")

    # Mark this block as seen
    seen.proposer_slots.add((block.proposer_index, block.slot))
```

###### `beacon_aggregate_and_proof`

*Note*: This function is modified to ignore aggregate attestations from future
slots and ignore aggregate attestations whose epoch is not the current or
previous epoch relative to `current_time_ms`.

```python
def validate_beacon_aggregate_and_proof_gossip(
    seen: Seen,
    store: Store,
    state: BeaconState,
    signed_aggregate_and_proof: SignedAggregateAndProof,
    current_time_ms: uint64,
) -> None:
    """
    Validate a SignedAggregateAndProof for gossip propagation.
    Raises GossipIgnore or GossipReject on validation failure.
    """
    aggregate_and_proof = signed_aggregate_and_proof.message
    aggregate = aggregate_and_proof.aggregate
    index = aggregate.data.index
    aggregation_bits = aggregate.aggregation_bits

    # [REJECT] The committee index is within the expected range
    committee_count = get_committee_count_per_slot(state, aggregate.data.target.epoch)
    if index >= committee_count:
        raise GossipReject("committee index out of range")

    # [New in Deneb:EIP7045]
    # [IGNORE] The aggregate attestation's slot is not from a future slot
    # (MAY be queued for processing at the appropriate slot)
    if not is_not_from_future_slot(state, aggregate.data.slot, current_time_ms):
        raise GossipIgnore("aggregate slot is from a future slot")

    # [Modified in Deneb:EIP7045]
    # [IGNORE] The aggregate attestation's epoch is either the current or previous epoch
    attestation_epoch = compute_epoch_at_slot(aggregate.data.slot)
    is_previous_epoch_attestation = is_within_slot_range(
        state,
        compute_start_slot_at_epoch(Epoch(attestation_epoch + 1)),
        SLOTS_PER_EPOCH - 1,
        current_time_ms,
    )
    is_current_epoch_attestation = is_within_slot_range(
        state,
        compute_start_slot_at_epoch(attestation_epoch),
        SLOTS_PER_EPOCH - 1,
        current_time_ms,
    )
    if not (is_previous_epoch_attestation or is_current_epoch_attestation):
        raise GossipIgnore("aggregate epoch is not previous or current epoch")

    # [REJECT] The aggregate attestation's epoch matches its target
    if aggregate.data.target.epoch != compute_epoch_at_slot(aggregate.data.slot):
        raise GossipReject("attestation epoch does not match target epoch")

    # [REJECT] The number of aggregation bits matches the committee size
    committee = get_beacon_committee(state, aggregate.data.slot, index)
    if len(aggregation_bits) != len(committee):
        raise GossipReject("aggregation bits length does not match committee size")

    # [REJECT] The aggregate attestation has participants
    attesting_indices = get_attesting_indices(state, aggregate)
    if len(attesting_indices) < 1:
        raise GossipReject("aggregate has no participants")

    # [IGNORE] A valid aggregate with a superset of aggregation bits has not already been seen
    aggregate_data_root = hash_tree_root(aggregate.data)
    aggregate_bits = tuple(bool(bit) for bit in aggregation_bits)
    seen_bits = seen.aggregate_data_roots.get(aggregate_data_root, set())
    if is_non_strict_superset(seen_bits, aggregate_bits):
        raise GossipIgnore("already seen aggregate for this data")

    # [IGNORE] This is the first valid aggregate for this aggregator in this epoch
    aggregator_index = aggregate_and_proof.aggregator_index
    target_epoch = aggregate.data.target.epoch
    if (aggregator_index, target_epoch) in seen.aggregator_epochs:
        raise GossipIgnore("already seen aggregate from this aggregator for this epoch")

    # [REJECT] The selection proof selects the validator as an aggregator
    if not is_aggregator(state, aggregate.data.slot, index, aggregate_and_proof.selection_proof):
        raise GossipReject("validator is not selected as aggregator")

    # [REJECT] The aggregator's validator index is within the committee
    if aggregator_index not in committee:
        raise GossipReject("aggregator index not in committee")

    # [REJECT] The selection proof signature is valid
    aggregator = state.validators[aggregator_index]
    domain = get_domain(state, DOMAIN_SELECTION_PROOF, target_epoch)
    signing_root = compute_signing_root(aggregate.data.slot, domain)
    if not bls.Verify(aggregator.pubkey, signing_root, aggregate_and_proof.selection_proof):
        raise GossipReject("invalid selection proof signature")

    # [REJECT] The aggregator signature is valid
    domain = get_domain(state, DOMAIN_AGGREGATE_AND_PROOF, target_epoch)
    signing_root = compute_signing_root(aggregate_and_proof, domain)
    if not bls.Verify(aggregator.pubkey, signing_root, signed_aggregate_and_proof.signature):
        raise GossipReject("invalid aggregator signature")

    # [REJECT] The aggregate signature is valid
    if not is_valid_indexed_attestation(state, get_indexed_attestation(state, aggregate)):
        raise GossipReject("invalid aggregate signature")

    # [IGNORE] The block being voted for has been seen (via gossip or non-gossip sources)
    # (MAY be queued until block is retrieved)
    if aggregate.data.beacon_block_root not in store.blocks:
        raise GossipIgnore("block being voted for has not been seen")

    # [REJECT] The block being voted for passes validation
    if aggregate.data.beacon_block_root not in store.block_states:
        raise GossipReject("block being voted for failed validation")

    # [REJECT] The target block is an ancestor of the LMD vote block
    checkpoint_block = get_checkpoint_block(
        store, aggregate.data.beacon_block_root, aggregate.data.target.epoch
    )
    if checkpoint_block != aggregate.data.target.root:
        raise GossipReject("target block is not an ancestor of LMD vote block")

    # [IGNORE] The finalized checkpoint is an ancestor of the block
    finalized_checkpoint_block = get_checkpoint_block(
        store, aggregate.data.beacon_block_root, store.finalized_checkpoint.epoch
    )
    if finalized_checkpoint_block != store.finalized_checkpoint.root:
        raise GossipIgnore("finalized checkpoint is not an ancestor of block")

    # Mark this aggregate as seen
    seen.aggregator_epochs.add((aggregator_index, target_epoch))
    if aggregate_data_root not in seen.aggregate_data_roots:
        seen.aggregate_data_roots[aggregate_data_root] = set()
    seen.aggregate_data_roots[aggregate_data_root].add(aggregate_bits)
```

###### `voluntary_exit`

*Note*: This function is modified to use `CAPELLA_FORK_VERSION` in the signature
domain computation so that voluntary exits remain valid across fork boundaries.

```python
def validate_voluntary_exit_gossip(
    seen: Seen,
    state: BeaconState,
    signed_voluntary_exit: SignedVoluntaryExit,
) -> None:
    """
    Validate a SignedVoluntaryExit for gossip propagation.
    Raises GossipIgnore or GossipReject on validation failure.
    """
    voluntary_exit = signed_voluntary_exit.message
    validator_index = voluntary_exit.validator_index

    # [IGNORE] The voluntary exit is the first valid voluntary exit received for the validator
    if validator_index in seen.voluntary_exit_indices:
        raise GossipIgnore("already seen voluntary exit for this validator")

    # [REJECT] The validator index is valid
    if validator_index >= len(state.validators):
        raise GossipReject("validator index out of range")

    validator = state.validators[validator_index]
    current_epoch = get_current_epoch(state)

    # [REJECT] The validator is active
    if not is_active_validator(validator, current_epoch):
        raise GossipReject("validator is not active")

    # [REJECT] The validator has not already initiated exit
    if validator.exit_epoch != FAR_FUTURE_EPOCH:
        raise GossipReject("validator has already initiated exit")

    # [REJECT] The voluntary exit epoch is not in the future
    if current_epoch < voluntary_exit.epoch:
        raise GossipReject("voluntary exit epoch is in the future")

    # [REJECT] The validator has been active long enough
    if current_epoch < validator.activation_epoch + SHARD_COMMITTEE_PERIOD:
        raise GossipReject("validator has not been active long enough")

    # [Modified in Deneb:EIP7044]
    # [REJECT] The signature is valid
    domain = compute_domain(
        DOMAIN_VOLUNTARY_EXIT, CAPELLA_FORK_VERSION, state.genesis_validators_root
    )
    signing_root = compute_signing_root(voluntary_exit, domain)
    if not bls.Verify(validator.pubkey, signing_root, signed_voluntary_exit.signature):
        raise GossipReject("invalid voluntary exit signature")

    # Mark this voluntary exit as seen
    seen.voluntary_exit_indices.add(validator_index)
```

##### Blob subnets

###### `blob_sidecar_{subnet_id}`

The `blob_sidecar_{subnet_id}` topics, where each blob index maps to some
`subnet_id`, are used solely for propagating new blob sidecars to all nodes on
the networks. BlobSidecars are sent in their entirety. The `state` parameter is
the head state.

```python
def validate_blob_sidecar_gossip(
    seen: Seen,
    store: Store,
    state: BeaconState,
    blob_sidecar: BlobSidecar,
    subnet_id: SubnetID,
    current_time_ms: uint64,
) -> None:
    """
    Validate a BlobSidecar for gossip propagation on a subnet.
    Raises GossipIgnore or GossipReject on validation failure.
    """
    block_header = blob_sidecar.signed_block_header.message

    # [REJECT] The sidecar's index is consistent with MAX_BLOBS_PER_BLOCK
    if blob_sidecar.index >= MAX_BLOBS_PER_BLOCK:
        raise GossipReject("blob index out of range")

    # [REJECT] The sidecar is for the correct subnet
    if compute_subnet_for_blob_sidecar(blob_sidecar.index) != subnet_id:
        raise GossipReject("blob sidecar is for wrong subnet")

    # [IGNORE] The sidecar is not from a future slot
    # (MAY be queued for processing at the appropriate slot)
    if not is_not_from_future_slot(state, block_header.slot, current_time_ms):
        raise GossipIgnore("blob sidecar is from a future slot")

    # [IGNORE] The sidecar is from a slot greater than the latest finalized slot
    finalized_slot = compute_start_slot_at_epoch(store.finalized_checkpoint.epoch)
    if block_header.slot <= finalized_slot:
        raise GossipIgnore("blob sidecar is not from a slot greater than the latest finalized slot")

    # [REJECT] The proposer index is a valid validator index
    if block_header.proposer_index >= len(state.validators):
        raise GossipReject("proposer index out of range")

    # [REJECT] The proposer signature of blob_sidecar.signed_block_header is valid
    proposer = state.validators[block_header.proposer_index]
    domain = get_domain(state, DOMAIN_BEACON_PROPOSER, compute_epoch_at_slot(block_header.slot))
    signing_root = compute_signing_root(block_header, domain)
    if not bls.Verify(proposer.pubkey, signing_root, blob_sidecar.signed_block_header.signature):
        raise GossipReject("invalid proposer signature on blob sidecar block header")

    # [IGNORE] The sidecar's block's parent has been seen
    # (MAY be queued for processing once the parent block is retrieved)
    if block_header.parent_root not in store.blocks:
        raise GossipIgnore("blob sidecar's parent has not been seen")

    # [REJECT] The sidecar's block's parent passes validation
    if block_header.parent_root not in store.block_states:
        raise GossipReject("blob sidecar's parent failed validation")

    # [REJECT] The sidecar is from a higher slot than the sidecar's block's parent
    if block_header.slot <= store.blocks[block_header.parent_root].slot:
        raise GossipReject("blob sidecar is not from a higher slot than its parent")

    # [REJECT] The current finalized_checkpoint is an ancestor of the sidecar's block
    checkpoint_block = get_checkpoint_block(
        store, block_header.parent_root, store.finalized_checkpoint.epoch
    )
    if checkpoint_block != store.finalized_checkpoint.root:
        raise GossipReject("finalized checkpoint is not an ancestor of blob sidecar's block")

    # [REJECT] The sidecar's inclusion proof is valid as verified by verify_blob_sidecar_inclusion_proof
    if not verify_blob_sidecar_inclusion_proof(blob_sidecar):
        raise GossipReject("invalid blob sidecar inclusion proof")

    # [REJECT] The sidecar's blob is valid as verified by verify_blob_kzg_proof
    if not verify_blob_kzg_proof(
        blob_sidecar.blob, blob_sidecar.kzg_commitment, blob_sidecar.kzg_proof
    ):
        raise GossipReject("invalid blob kzg proof")

    # [IGNORE] The sidecar is the first sidecar for the tuple
    # (block_header.slot, block_header.proposer_index, blob_sidecar.index)
    sidecar_tuple = (block_header.slot, block_header.proposer_index, blob_sidecar.index)
    if sidecar_tuple in seen.blob_sidecar_tuples:
        raise GossipIgnore("already seen blob sidecar from this proposer for this slot and index")

    # [REJECT] The sidecar is proposed by the expected proposer_index
    # (if shuffling is not available, IGNORE instead and MAY be queued for later)
    parent_state = store.block_states[block_header.parent_root].copy()
    process_slots(parent_state, block_header.slot)
    expected_proposer = get_beacon_proposer_index(parent_state)
    if block_header.proposer_index != expected_proposer:
        raise GossipReject("blob sidecar proposer_index does not match expected proposer")

    # Mark this blob sidecar as seen
    seen.blob_sidecar_tuples.add(sidecar_tuple)
```

The `ForkDigest` context epoch is determined by
`compute_epoch_at_slot(blob_sidecar.signed_block_header.message.slot)`.

Per `fork_version = compute_fork_version(epoch)`:

<!-- eth_consensus_specs: skip -->

| `fork_version`                 | Chunk SSZ type      |
| ------------------------------ | ------------------- |
| `DENEB_FORK_VERSION` and later | `deneb.BlobSidecar` |

###### Blob retrieval via local execution-layer client

In addition to `BlobSidecarsByRoot` requests, recent blobs MAY be retrieved by
querying the execution layer (i.e. via `engine_getBlobsV1`). Honest nodes SHOULD
query `engine_getBlobsV1` as soon as they receive a valid gossip block that
contains data, and import the returned blobs.

When clients use the local execution layer to retrieve blobs, they MUST behave
as if the corresponding `blob_sidecar` had been received via gossip. In
particular they MUST:

- Publish the corresponding `blob_sidecar` on the `blob_sidecar_{subnet_id}`
  subnet.
- Update gossip rule related data structures (i.e. update the anti-equivocation
  cache).

##### Attestation subnets

###### `beacon_attestation_{subnet_id}`

*[Modified in Deneb:EIP7045]* Attestations from the previous epoch are now
propagated through the entire current epoch rather than only the next
`ATTESTATION_PROPAGATION_SLOT_RANGE` slots.

*Note*: This function is modified to ignore attestations from future slots and
ignore attestations whose epoch is not the current or previous epoch relative to
`current_time_ms`.

```python
def validate_beacon_attestation_gossip(
    seen: Seen,
    store: Store,
    state: BeaconState,
    attestation: Attestation,
    subnet_id: uint64,
    current_time_ms: uint64,
) -> None:
    """
    Validate an Attestation for gossip propagation on a subnet.
    Raises GossipIgnore or GossipReject on validation failure.
    """
    data = attestation.data
    committee_index = data.index
    target_epoch = data.target.epoch
    aggregation_bits = attestation.aggregation_bits

    # [REJECT] The committee index is within the expected range
    committees_per_slot = get_committee_count_per_slot(state, target_epoch)
    if committee_index >= committees_per_slot:
        raise GossipReject("committee index out of range")

    # [REJECT] The attestation is for the correct subnet
    expected_subnet = compute_subnet_for_attestation(
        committees_per_slot, data.slot, committee_index
    )
    if expected_subnet != subnet_id:
        raise GossipReject("attestation is for wrong subnet")

    # [Modified in Deneb:EIP7045]
    # [IGNORE] The attestation's slot is not from a future slot
    # (MAY be queued for processing at the appropriate slot)
    if not is_not_from_future_slot(state, data.slot, current_time_ms):
        raise GossipIgnore("attestation slot is from a future slot")

    # [Modified in Deneb:EIP7045]
    # [IGNORE] The attestation's epoch is either the current or previous epoch
    attestation_epoch = compute_epoch_at_slot(data.slot)
    is_previous_epoch_attestation = is_within_slot_range(
        state,
        compute_start_slot_at_epoch(Epoch(attestation_epoch + 1)),
        SLOTS_PER_EPOCH - 1,
        current_time_ms,
    )
    is_current_epoch_attestation = is_within_slot_range(
        state,
        compute_start_slot_at_epoch(attestation_epoch),
        SLOTS_PER_EPOCH - 1,
        current_time_ms,
    )
    if not (is_previous_epoch_attestation or is_current_epoch_attestation):
        raise GossipIgnore("attestation epoch is not previous or current epoch")

    # [REJECT] The attestation's epoch matches its target
    if target_epoch != compute_epoch_at_slot(data.slot):
        raise GossipReject("attestation epoch does not match target epoch")

    # [REJECT] The attestation is unaggregated (exactly one bit set)
    num_bits_set = sum(1 for bit in aggregation_bits if bit)
    if num_bits_set != 1:
        raise GossipReject("attestation is not unaggregated")

    # [REJECT] The number of aggregation bits matches the committee size
    committee = get_beacon_committee(state, data.slot, committee_index)
    if len(aggregation_bits) != len(committee):
        raise GossipReject("aggregation bits length does not match committee size")

    # [IGNORE] No other valid attestation seen for this validator and target epoch
    participant_index = committee[aggregation_bits.index(True)]
    if (participant_index, target_epoch) in seen.attestation_validator_epochs:
        raise GossipIgnore("already seen attestation from this validator for this epoch")

    # [REJECT] The attestation signature is valid
    indexed_attestation = get_indexed_attestation(state, attestation)
    if not is_valid_indexed_attestation(state, indexed_attestation):
        raise GossipReject("invalid attestation signature")

    # [IGNORE] The block being voted for has been seen (via gossip or non-gossip sources)
    # (MAY be queued until block is retrieved)
    beacon_block_root = data.beacon_block_root
    if beacon_block_root not in store.blocks:
        raise GossipIgnore("block being voted for has not been seen")

    # [REJECT] The block being voted for passes validation
    if beacon_block_root not in store.block_states:
        raise GossipReject("block being voted for failed validation")

    # [REJECT] The attestation's target block is an ancestor of the LMD vote block
    target_checkpoint_block = get_checkpoint_block(store, beacon_block_root, target_epoch)
    if target_checkpoint_block != data.target.root:
        raise GossipReject("target block is not an ancestor of LMD vote block")

    # [IGNORE] The current finalized_checkpoint is an ancestor of the block
    finalized_checkpoint_block = get_checkpoint_block(
        store, beacon_block_root, store.finalized_checkpoint.epoch
    )
    if finalized_checkpoint_block != store.finalized_checkpoint.root:
        raise GossipIgnore("finalized checkpoint is not an ancestor of block")

    # Mark this attestation as seen
    seen.attestation_validator_epochs.add((participant_index, target_epoch))
```

#### Transitioning the gossip

See gossip transition details found in the
[Altair document](../altair/p2p-interface.md#transitioning-the-gossip) for
details on how to handle transitioning gossip topics for this upgrade.

### The Req/Resp domain

#### Messages

##### BeaconBlocksByRange v2

**Protocol ID:** `/eth2/beacon_chain/req/beacon_blocks_by_range/2/`

Request Content:

```
(
  start_slot: Slot
  count: uint64
  step: uint64 # Deprecated, must be set to 1
)
```

Response Content:

```
(
  List[SignedBeaconBlock, MAX_REQUEST_BLOCKS_DENEB]
)
```

The Deneb fork-digest is introduced to the `context` enum to specify Deneb
beacon block type.

<!-- eth_consensus_specs: skip -->

| `fork_version`           | Chunk SSZ type                |
| ------------------------ | ----------------------------- |
| `GENESIS_FORK_VERSION`   | `phase0.SignedBeaconBlock`    |
| `ALTAIR_FORK_VERSION`    | `altair.SignedBeaconBlock`    |
| `BELLATRIX_FORK_VERSION` | `bellatrix.SignedBeaconBlock` |
| `CAPELLA_FORK_VERSION`   | `capella.SignedBeaconBlock`   |
| `DENEB_FORK_VERSION`     | `deneb.SignedBeaconBlock`     |

No more than `MAX_REQUEST_BLOCKS_DENEB` may be requested at a time.

##### BeaconBlocksByRoot v2

**Protocol ID:** `/eth2/beacon_chain/req/beacon_blocks_by_root/2/`

Request Content:

```
(
  List[Root, MAX_REQUEST_BLOCKS_DENEB]
)
```

Response Content:

```
(
  List[SignedBeaconBlock, MAX_REQUEST_BLOCKS_DENEB]
)
```

<!-- eth_consensus_specs: skip -->

| `fork_version`           | Chunk SSZ type                |
| ------------------------ | ----------------------------- |
| `GENESIS_FORK_VERSION`   | `phase0.SignedBeaconBlock`    |
| `ALTAIR_FORK_VERSION`    | `altair.SignedBeaconBlock`    |
| `BELLATRIX_FORK_VERSION` | `bellatrix.SignedBeaconBlock` |
| `CAPELLA_FORK_VERSION`   | `capella.SignedBeaconBlock`   |
| `DENEB_FORK_VERSION`     | `deneb.SignedBeaconBlock`     |

No more than `MAX_REQUEST_BLOCKS_DENEB` may be requested at a time.

*[Modified in Deneb:EIP4844]* Clients SHOULD include a block in the response as
soon as it passes the gossip validation rules. Clients SHOULD NOT respond with
blocks that fail the beacon-chain state transition.

##### BlobSidecarsByRange v1

**Protocol ID:** `/eth2/beacon_chain/req/blob_sidecars_by_range/1/`

*[New in Deneb:EIP4844]*

Request Content:

```
(
  start_slot: Slot
  count: uint64
)
```

Response Content:

```
(
  List[BlobSidecar, compute_max_request_blob_sidecars()]
)
```

Requests blob sidecars in the slot range `[start_slot, start_slot + count)`,
leading up to the current head block as selected by fork choice.

Before consuming the next response chunk, the response reader SHOULD verify the
blob sidecar is well-formatted, has valid inclusion proof, and is correct w.r.t.
the expected KZG commitments through `verify_blob_kzg_proof`.

`BlobSidecarsByRange` is primarily used to sync blobs that may have been missed
on gossip and to sync within the `MIN_EPOCHS_FOR_BLOB_SIDECARS_REQUESTS` window.

The request MUST be encoded as an SSZ-container.

The response MUST consist of zero or more `response_chunk`. Each _successful_
`response_chunk` MUST contain a single `BlobSidecar` payload.

Let `blob_serve_range` be
`[max(current_epoch - MIN_EPOCHS_FOR_BLOB_SIDECARS_REQUESTS, DENEB_FORK_EPOCH), current_epoch]`.
Clients MUST keep a record of blob sidecars seen on the epoch range
`blob_serve_range` where `current_epoch` is defined by the current wall-clock
time, and clients MUST support serving requests of blobs on this range.

Peers that are unable to reply to blob sidecar requests within the range
`blob_serve_range` SHOULD respond with error code `3: ResourceUnavailable`. Such
peers that are unable to successfully reply to this range of requests MAY get
descored or disconnected at any time.

*Note*: The above requirement implies that nodes that start from a recent weak
subjectivity checkpoint MUST backfill the local blobs database to at least the
range `blob_serve_range` to be fully compliant with `BlobSidecarsByRange`
requests.

*Note*: Although clients that bootstrap from a weak subjectivity checkpoint can
begin participating in the networking immediately, other peers MAY disconnect
and/or temporarily ban such an un-synced or semi-synced client.

Clients MUST respond with at least the blob sidecars of the first blob-carrying
block that exists in the range, if they have it, and no more than
`compute_max_request_blob_sidecars()` sidecars.

Clients MUST include all blob sidecars of each block from which they include
blob sidecars.

The following blob sidecars, where they exist, MUST be sent in consecutive
`(slot, index)` order.

Slots that do not contain known blobs MUST be skipped, mimicking the behaviour
of the `BlocksByRange` request. Only response chunks with known blobs should
therefore be sent.

Clients MAY limit the number of blob sidecars in the response.

The response MUST contain no more than `count * MAX_BLOBS_PER_BLOCK` blob
sidecars.

Clients MUST respond with blob sidecars from their view of the current fork
choice -- that is, blob sidecars as included by blocks from the single chain
defined by the current head. Of note, blocks from slots before the finalization
MUST lead to the finalized block reported in the `Status` handshake.

Clients MUST respond with blob sidecars that are consistent from a single chain
within the context of the request.

After the initial blob sidecar, clients MAY stop in the process of responding if
their fork choice changes the view of the chain in the context of the request.

For each successful `response_chunk`, the `ForkDigest` context epoch is
determined by
`compute_epoch_at_slot(blob_sidecar.signed_block_header.message.slot)`.

Per `fork_version = compute_fork_version(epoch)`:

<!-- eth_consensus_specs: skip -->

| `fork_version`                 | Chunk SSZ type      |
| ------------------------------ | ------------------- |
| `DENEB_FORK_VERSION` and later | `deneb.BlobSidecar` |

##### BlobSidecarsByRoot v1

**Protocol ID:** `/eth2/beacon_chain/req/blob_sidecars_by_root/1/`

*[New in Deneb:EIP4844]*

Request Content:

```
(
  List[BlobIdentifier, compute_max_request_blob_sidecars()]
)
```

Response Content:

```
(
  List[BlobSidecar, compute_max_request_blob_sidecars()]
)
```

Requests sidecars by block root and index. The response is a list of
`BlobSidecar` whose length is less than or equal to the number of requests. It
may be less in the case that the responding peer is missing blocks or sidecars.

Before consuming the next response chunk, the response reader SHOULD verify the
blob sidecar is well-formatted, has valid inclusion proof, and is correct w.r.t.
the expected KZG commitments through `verify_blob_kzg_proof`.

No more than `compute_max_request_blob_sidecars()` may be requested at a time.

`BlobSidecarsByRoot` is primarily used to recover recent blobs (e.g. when
receiving a block with a transaction whose corresponding blob is missing).

The response MUST consist of zero or more `response_chunk`. Each _successful_
`response_chunk` MUST contain a single `BlobSidecar` payload.

Clients MUST support requesting sidecars since `minimum_request_epoch`, where
`minimum_request_epoch = max(current_epoch - MIN_EPOCHS_FOR_BLOB_SIDECARS_REQUESTS, DENEB_FORK_EPOCH)`.
If any root in the request content references a block earlier than
`minimum_request_epoch`, peers MAY respond with error code
`3: ResourceUnavailable` or not include the blob sidecar in the response.

Clients MUST respond with at least one sidecar, if they have it. Clients MAY
limit the number of blocks and sidecars in the response.

Clients SHOULD include a sidecar in the response as soon as it passes the gossip
validation rules. Clients SHOULD NOT respond with sidecars related to blocks
that fail gossip validation rules. Clients SHOULD NOT respond with sidecars
related to blocks that fail the beacon-chain state transition

For each successful `response_chunk`, the `ForkDigest` context epoch is
determined by
`compute_epoch_at_slot(blob_sidecar.signed_block_header.message.slot)`.

Per `fork_version = compute_fork_version(epoch)`:

<!-- eth_consensus_specs: skip -->

| `fork_version`                 | Chunk SSZ type      |
| ------------------------------ | ------------------- |
| `DENEB_FORK_VERSION` and later | `deneb.BlobSidecar` |

## Design decision rationale

### Why are blobs relayed as a sidecar, separate from beacon blocks?

This "sidecar" design provides forward compatibility for further data increases
by black-boxing `is_data_available()`: with full sharding `is_data_available()`
can be replaced by data-availability-sampling (DAS) thus avoiding all blobs
being downloaded by all beacon nodes on the network.

Such sharding design may introduce an updated `BlobSidecar` to identify the
shard, but does not affect the `BeaconBlock` structure.
