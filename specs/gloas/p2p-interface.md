# Gloas -- Networking

*Note*: This document is a work-in-progress for researchers and implementers.

<!-- mdformat-toc start --slug=github --no-anchors --maxlevel=6 --minlevel=2 -->

- [Introduction](#introduction)
- [Modification in Gloas](#modification-in-gloas)
  - [Configuration](#configuration)
  - [Containers](#containers)
    - [Modified `DataColumnSidecar`](#modified-datacolumnsidecar)
    - [New `ProposerPreferences`](#new-proposerpreferences)
    - [New `SignedProposerPreferences`](#new-signedproposerpreferences)
  - [Helpers](#helpers)
    - [Modified `Seen`](#modified-seen)
    - [Modified `compute_fork_version`](#modified-compute_fork_version)
    - [Modified `verify_data_column_sidecar_kzg_proofs`](#modified-verify_data_column_sidecar_kzg_proofs)
    - [Modified `verify_data_column_sidecar`](#modified-verify_data_column_sidecar)
    - [New `is_current_or_next_slot`](#new-is_current_or_next_slot)
    - [New `is_gas_limit_target_compatible`](#new-is_gas_limit_target_compatible)
    - [New `is_valid_proposal_slot`](#new-is_valid_proposal_slot)
    - [New `get_proposer_dependent_root`](#new-get_proposer_dependent_root)
  - [The gossip domain: gossipsub](#the-gossip-domain-gossipsub)
    - [Topics and messages](#topics-and-messages)
      - [Global topics](#global-topics)
        - [Modified `beacon_aggregate_and_proof`](#modified-beacon_aggregate_and_proof)
        - [Modified `beacon_block`](#modified-beacon_block)
        - [New `execution_payload`](#new-execution_payload)
        - [New `payload_attestation_message`](#new-payload_attestation_message)
        - [New `execution_payload_bid`](#new-execution_payload_bid)
        - [New `proposer_preferences`](#new-proposer_preferences)
      - [Blob subnets](#blob-subnets)
        - [Modified `data_column_sidecar_{subnet_id}`](#modified-data_column_sidecar_subnet_id)
      - [Attestation subnets](#attestation-subnets)
        - [Modified `beacon_attestation_{subnet_id}`](#modified-beacon_attestation_subnet_id)
  - [The Req/Resp domain](#the-reqresp-domain)
    - [Messages](#messages)
      - [BeaconBlocksByRange v2](#beaconblocksbyrange-v2)
      - [BeaconBlocksByRoot v2](#beaconblocksbyroot-v2)
      - [ExecutionPayloadEnvelopesByRange v1](#executionpayloadenvelopesbyrange-v1)
      - [ExecutionPayloadEnvelopesByRoot v1](#executionpayloadenvelopesbyroot-v1)

<!-- mdformat-toc end -->

## Introduction

This document contains the consensus-layer networking specifications for Gloas.

The specification of these changes continues in the same format as the network
specifications of previous upgrades, and assumes them as pre-requisite.

## Modification in Gloas

### Configuration

| Name                   | Value          | Description                                                       |
| ---------------------- | -------------- | ----------------------------------------------------------------- |
| `MAX_REQUEST_PAYLOADS` | `2**7` (= 128) | Maximum number of execution payload envelopes in a single request |

### Containers

#### Modified `DataColumnSidecar`

*Note*: The `signed_block_header`, `kzg_commitments`, and
`kzg_commitments_inclusion_proof` fields have been removed from
`DataColumnSidecar` in Gloas as header and inclusion proof verifications are no
longer required in Gloas. The KZG commitments are now located at
`block.body.signed_execution_payload_bid.message.blob_kzg_commitments` where
`block` is the `BeaconBlock` associated with `beacon_block_root`.

```python
class DataColumnSidecar(Container):
    index: ColumnIndex
    column: List[Cell, MAX_BLOB_COMMITMENTS_PER_BLOCK]
    # [Modified in Gloas:EIP7732]
    # Removed `kzg_commitments`
    kzg_proofs: List[KZGProof, MAX_BLOB_COMMITMENTS_PER_BLOCK]
    # [Modified in Gloas:EIP7732]
    # Removed `signed_block_header`
    # [Modified in Gloas:EIP7732]
    # Removed `kzg_commitments_inclusion_proof`
    # [New in Gloas:EIP7732]
    slot: Slot
    # [New in Gloas:EIP7732]
    beacon_block_root: Root
```

#### New `ProposerPreferences`

*[New in Gloas:EIP7732]*

```python
class ProposerPreferences(Container):
    dependent_root: Root
    proposal_slot: Slot
    validator_index: ValidatorIndex
    fee_recipient: ExecutionAddress
    target_gas_limit: uint64
```

#### New `SignedProposerPreferences`

*[New in Gloas:EIP7732]*

```python
class SignedProposerPreferences(Container):
    message: ProposerPreferences
    signature: BLSSignature
```

### Helpers

#### Modified `Seen`

```python
@dataclass
class Seen:
    proposer_slots: Set[Tuple[ValidatorIndex, Slot]]
    aggregator_epochs: Set[Tuple[ValidatorIndex, Epoch]]
    aggregate_data_roots: Dict[Tuple[Root, CommitteeIndex], Set[Tuple[boolean, ...]]]
    voluntary_exit_indices: Set[ValidatorIndex]
    proposer_slashing_indices: Set[ValidatorIndex]
    attester_slashing_indices: Set[ValidatorIndex]
    attestation_validator_epochs: Set[Tuple[ValidatorIndex, Epoch]]
    sync_contribution_aggregator_slots: Set[Tuple[ValidatorIndex, Slot, uint64]]
    sync_contribution_data: Dict[Tuple[Slot, Root, uint64], Set[Tuple[boolean, ...]]]
    sync_message_validator_slots: Set[Tuple[Slot, ValidatorIndex, uint64]]
    bls_to_execution_change_indices: Set[ValidatorIndex]
    # [Modified in Gloas:EIP7732]
    data_column_sidecar_tuples: Set[Tuple[Root, ColumnIndex]]
    # [Modified in Gloas:EIP7732]
    # Removed `partial_data_column_headers`
    # [New in Gloas:EIP7732]
    execution_payloads: Dict[Hash32, ExecutionPayload]
    # [New in Gloas:EIP7732]
    execution_payload_envelopes: Set[Tuple[Root, BuilderIndex]]
    # [New in Gloas:EIP7732]
    payload_attestation_validators: Set[Tuple[Slot, ValidatorIndex]]
    # [New in Gloas:EIP7732]
    execution_payload_bids: Set[Tuple[BuilderIndex, Slot]]
    # [New in Gloas:EIP7732]
    best_execution_payload_bid: Dict[Tuple[Slot, Hash32, Root], Gwei]
    # [New in Gloas:EIP7732]
    proposer_preferences: Dict[Tuple[Root, Slot], ProposerPreferences]
```

#### Modified `compute_fork_version`

```python
def compute_fork_version(epoch: Epoch) -> Version:
    """
    Return the fork version at the given ``epoch``.
    """
    if epoch >= GLOAS_FORK_EPOCH:
        return GLOAS_FORK_VERSION
    if epoch >= FULU_FORK_EPOCH:
        return FULU_FORK_VERSION
    if epoch >= ELECTRA_FORK_EPOCH:
        return ELECTRA_FORK_VERSION
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

#### Modified `verify_data_column_sidecar_kzg_proofs`

```python
def verify_data_column_sidecar_kzg_proofs(
    sidecar: DataColumnSidecar,
    # [New in Gloas:EIP7732]
    kzg_commitments: List[KZGCommitment, MAX_BLOB_COMMITMENTS_PER_BLOCK],
) -> bool:
    """
    Verify if the KZG proofs are correct.
    """
    # The column index also represents the cell index
    cell_indices = [CellIndex(sidecar.index)] * len(sidecar.column)

    # Batch verify that the cells match the corresponding commitments and proofs
    return verify_cell_kzg_proof_batch(
        # [Modified in Gloas:EIP7732]
        commitments_bytes=kzg_commitments,
        cell_indices=cell_indices,
        cells=sidecar.column,
        proofs_bytes=sidecar.kzg_proofs,
    )
```

#### Modified `verify_data_column_sidecar`

```python
def verify_data_column_sidecar(
    sidecar: DataColumnSidecar,
    # [New in Gloas:EIP7732]
    kzg_commitments: List[KZGCommitment, MAX_BLOB_COMMITMENTS_PER_BLOCK],
) -> bool:
    """
    Verify if the data column sidecar is valid.
    """
    # The sidecar index must be within the valid range
    if sidecar.index >= NUMBER_OF_COLUMNS:
        return False

    # [Modified in Gloas:EIP7732]
    # A sidecar for zero blobs is invalid
    if len(sidecar.column) == 0:
        return False

    # [Modified in Gloas:EIP7732]
    # The column length must be equal to the number of commitments/proofs
    if len(sidecar.column) != len(kzg_commitments) or len(sidecar.column) != len(
        sidecar.kzg_proofs
    ):
        return False

    return True
```

#### New `is_current_or_next_slot`

```python
def is_current_or_next_slot(
    state: BeaconState,
    slot: Slot,
    current_time_ms: uint64,
) -> bool:
    """
    Check if ``slot`` is the current slot or the next slot
    (with MAXIMUM_GOSSIP_CLOCK_DISPARITY allowance).
    """
    return is_within_slot_range(state, slot, 1, current_time_ms + SLOT_DURATION_MS)
```

#### New `is_gas_limit_target_compatible`

```python
def is_gas_limit_target_compatible(
    parent_gas_limit: uint64, gas_limit: uint64, target_gas_limit: uint64
) -> bool:
    """
    Check if ``gas_limit`` is compatible with ``target_gas_limit`` under the
    EIP-1559 transition rule from ``parent_gas_limit``.
    """
    max_gas_limit_difference = max(parent_gas_limit // 1024, 1) - 1
    min_gas_limit = parent_gas_limit - max_gas_limit_difference
    max_gas_limit = parent_gas_limit + max_gas_limit_difference

    if target_gas_limit >= min_gas_limit and target_gas_limit <= max_gas_limit:
        return gas_limit == target_gas_limit
    if target_gas_limit > max_gas_limit:
        return gas_limit == max_gas_limit
    return gas_limit == min_gas_limit
```

#### New `is_valid_proposal_slot`

```python
def is_valid_proposal_slot(state: BeaconState, preferences: ProposerPreferences) -> bool:
    """
    Check if the validator is the proposer for the given slot within the
    proposer lookahead.
    """
    current_epoch = get_current_epoch(state)
    proposal_epoch = compute_epoch_at_slot(preferences.proposal_slot)
    if proposal_epoch < current_epoch:
        return False
    if proposal_epoch > current_epoch + Epoch(MIN_SEED_LOOKAHEAD):
        return False

    index = (proposal_epoch - current_epoch) * SLOTS_PER_EPOCH
    index += preferences.proposal_slot % SLOTS_PER_EPOCH
    return state.proposer_lookahead[index] == preferences.validator_index
```

#### New `get_proposer_dependent_root`

```python
def get_proposer_dependent_root(state: BeaconState, epoch: Epoch) -> Root:
    """
    Return the dependent root for the proposer lookahead at ``epoch``.
    """
    return get_block_root_at_slot(
        state, Slot(compute_start_slot_at_epoch(Epoch(epoch - MIN_SEED_LOOKAHEAD)) - 1)
    )
```

### The gossip domain: gossipsub

Some gossip meshes are upgraded in Gloas to support upgraded types.

#### Topics and messages

Topics follow the same specification as in prior upgrades.

The `beacon_block` topic is updated to support the modified type

| Name           | Message Type        |
| -------------- | ------------------- |
| `beacon_block` | `SignedBeaconBlock` |

The new topics along with the type of the `data` field of a gossipsub message
are given in this table:

| Name                          | Message Type                     |
| ----------------------------- | -------------------------------- |
| `execution_payload_bid`       | `SignedExecutionPayloadBid`      |
| `execution_payload`           | `SignedExecutionPayloadEnvelope` |
| `payload_attestation_message` | `PayloadAttestationMessage`      |
| `proposer_preferences`        | `SignedProposerPreferences`      |

##### Global topics

###### Modified `beacon_aggregate_and_proof`

*Note*: This function is modified per EIP-7732. `aggregate.data.index` is now
restricted to `{0, 1}`, encoding whether the execution payload was present at
the slot. Same-slot aggregates MUST attest with `index == 0`. Aggregates with
`index == 1` require that the corresponding execution payload envelope has been
seen and passes execution-layer validation.

```python
def validate_beacon_aggregate_and_proof_gossip(
    seen: Seen,
    store: Store,
    state: BeaconState,
    signed_aggregate_and_proof: SignedAggregateAndProof,
    current_time_ms: uint64,
    # [New in Gloas:EIP7732]
    block_payload_statuses: Dict[Root, PayloadValidationStatus],
) -> None:
    """
    Validate a SignedAggregateAndProof for gossip propagation.
    Raises GossipIgnore or GossipReject on validation failure.
    """
    aggregate_and_proof = signed_aggregate_and_proof.message
    aggregate = aggregate_and_proof.aggregate
    aggregation_bits = aggregate.aggregation_bits

    # [New in Gloas:EIP7732]
    # [REJECT] The aggregate attestation's data index is 0 or 1
    if aggregate.data.index > 1:
        raise GossipReject("aggregate data index must be 0 or 1")

    # [REJECT] Exactly one committee is specified by the committee bits
    committee_indices = get_committee_indices(aggregate.committee_bits)
    if len(committee_indices) != 1:
        raise GossipReject("aggregate committee bits must specify exactly one committee")
    index = committee_indices[0]

    # [REJECT] The committee index is within the expected range
    committee_count = get_committee_count_per_slot(state, aggregate.data.target.epoch)
    if index >= committee_count:
        raise GossipReject("committee index out of range")

    # [IGNORE] The aggregate attestation's slot is not from a future slot
    # (MAY be queued for processing at the appropriate slot)
    if not is_not_from_future_slot(state, aggregate.data.slot, current_time_ms):
        raise GossipIgnore("aggregate slot is from a future slot")

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
    aggregate_cache_key = (aggregate_data_root, index)
    aggregate_bits = tuple(bool(bit) for bit in aggregation_bits)
    seen_bits = seen.aggregate_data_roots.get(aggregate_cache_key, set())
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
    block_root = aggregate.data.beacon_block_root
    if block_root not in store.blocks:
        raise GossipIgnore("block being voted for has not been seen")

    # [REJECT] The block being voted for passes validation
    if block_root not in store.block_states:
        raise GossipReject("block being voted for failed validation")

    block = store.blocks[block_root]

    # [New in Gloas:EIP7732]
    # [REJECT] For same-slot aggregates, the payload cannot yet be present
    if block.slot == aggregate.data.slot and aggregate.data.index != 0:
        raise GossipReject("same-slot aggregate must attest with index 0")

    if aggregate.data.index == 1:
        # [New in Gloas:EIP7732]
        # [IGNORE] The corresponding execution payload envelope has been seen
        # (MAY queue attestations for processing once the payload is retrieved and
        # SHOULD request the payload envelope via ExecutionPayloadEnvelopesByRoot
        # using aggregate.data.beacon_block_root)
        payload_status = block_payload_statuses.get(block_root)
        if payload_status is None:
            raise GossipIgnore("execution payload envelope has not been seen")

        # [New in Gloas:EIP7732]
        # [IGNORE] The corresponding execution payload has been validated
        if payload_status == PAYLOAD_STATUS_NOT_VALIDATED:
            raise GossipIgnore("execution payload pending EL validation")

        # [New in Gloas:EIP7732]
        # [REJECT] The corresponding execution payload passes EL validation
        if payload_status == PAYLOAD_STATUS_INVALIDATED:
            raise GossipReject("execution payload failed EL validation")

    # [REJECT] The target block is an ancestor of the LMD vote block
    checkpoint_block = get_checkpoint_block(store, block_root, aggregate.data.target.epoch)
    if checkpoint_block != aggregate.data.target.root:
        raise GossipReject("target block is not an ancestor of LMD vote block")

    # [IGNORE] The finalized checkpoint is an ancestor of the block
    finalized_checkpoint_block = get_checkpoint_block(
        store, block_root, store.finalized_checkpoint.epoch
    )
    if finalized_checkpoint_block != store.finalized_checkpoint.root:
        raise GossipIgnore("finalized checkpoint is not an ancestor of block")

    # Mark this aggregate as seen
    seen.aggregator_epochs.add((aggregator_index, target_epoch))
    if aggregate_cache_key not in seen.aggregate_data_roots:
        seen.aggregate_data_roots[aggregate_cache_key] = set()
    seen.aggregate_data_roots[aggregate_cache_key].add(aggregate_bits)
```

###### Modified `beacon_block`

*Note*: This function is modified per EIP-7732. The execution payload is no
longer carried inside `BeaconBlock`. As a result, all validations referring to
`block.body.execution_payload` are removed and replaced with validations of the
bid carried at `block.body.signed_execution_payload_bid.message`.

```python
def validate_beacon_block_gossip(
    seen: Seen,
    store: Store,
    state: BeaconState,
    signed_beacon_block: SignedBeaconBlock,
    current_time_ms: uint64,
    # [Modified in Gloas:EIP7732]
    # Removed `block_payload_statuses`
) -> None:
    """
    Validate a SignedBeaconBlock for gossip propagation.
    Raises GossipIgnore or GossipReject on validation failure.
    """
    block = signed_beacon_block.message
    # [New in Gloas:EIP7732]
    bid = block.body.signed_execution_payload_bid.message

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

    # [REJECT] The block is from a higher slot than its parent
    if block.slot <= store.blocks[block.parent_root].slot:
        raise GossipReject("block is not from a higher slot than its parent")

    # [REJECT] The current finalized checkpoint is an ancestor of the block
    checkpoint_block = get_checkpoint_block(
        store, block.parent_root, store.finalized_checkpoint.epoch
    )
    if checkpoint_block != store.finalized_checkpoint.root:
        raise GossipReject("finalized checkpoint is not an ancestor of block")

    # [Modified in Gloas:EIP7732]
    # [REJECT] The bid's blob KZG commitment count is within the per-epoch limit
    max_blobs = get_blob_parameters(get_current_epoch(state)).max_blobs_per_block
    if len(bid.blob_kzg_commitments) > max_blobs:
        raise GossipReject("too many blob kzg commitments")

    # [Modified in Gloas:EIP7732]
    # [REJECT] The bid's parent equals the block's parent
    if bid.parent_block_root != block.parent_root:
        raise GossipReject("bid's parent does not equal block's parent")

    # [New in Gloas:EIP7732]
    # [IGNORE] The block's parent state is available
    # (MAY be queued until state transition is complete)
    if block.parent_root not in store.block_states:
        raise GossipIgnore("block's parent state is unavailable")

    # [REJECT] The block is proposed by the expected proposer for the slot
    parent_state = store.block_states[block.parent_root].copy()
    process_slots(parent_state, block.slot)
    expected_proposer = get_beacon_proposer_index(parent_state)
    if block.proposer_index != expected_proposer:
        raise GossipReject("block proposer does not match the expected proposer")

    # Mark this block as seen
    seen.proposer_slots.add((block.proposer_index, block.slot))
```

###### New `execution_payload`

This topic is used to propagate execution payload messages as
`SignedExecutionPayloadEnvelope`.

```python
def validate_execution_payload_envelope_gossip(
    seen: Seen,
    store: Store,
    state: BeaconState,
    signed_execution_payload_envelope: SignedExecutionPayloadEnvelope,
) -> None:
    """
    Validate a SignedExecutionPayloadEnvelope for gossip propagation.
    Raises GossipIgnore or GossipReject on validation failure.
    """
    envelope = signed_execution_payload_envelope.message
    payload = envelope.payload
    block_root = envelope.beacon_block_root

    # [IGNORE] The envelope's block root has been seen (via gossip or non-gossip sources)
    # (MAY be queued until block is retrieved)
    if block_root not in store.blocks:
        raise GossipIgnore("envelope's block has not been seen")

    # [IGNORE] The node has not seen another valid envelope for this block root from this builder
    envelope_key = (block_root, envelope.builder_index)
    if envelope_key in seen.execution_payload_envelopes:
        raise GossipIgnore("already seen envelope for this block root from this builder")

    # [IGNORE] The envelope is from a slot greater than or equal to the latest finalized slot
    finalized_slot = compute_start_slot_at_epoch(store.finalized_checkpoint.epoch)
    if payload.slot_number < finalized_slot:
        raise GossipIgnore("envelope is from a slot before the latest finalized slot")

    # [REJECT] The envelope's block passes validation
    if block_root not in store.block_states:
        raise GossipReject("envelope's block failed validation")

    block = store.blocks[block_root]
    bid = block.body.signed_execution_payload_bid.message

    # [REJECT] The block's slot matches the payload's slot number
    if block.slot != payload.slot_number:
        raise GossipReject("block's slot does not match payload's slot number")

    # [REJECT] The envelope is from the builder committed to by the bid
    if envelope.builder_index != bid.builder_index:
        raise GossipReject("envelope's builder index does not match the bid's builder index")

    # [REJECT] The payload's block hash matches the bid's block hash
    if payload.block_hash != bid.block_hash:
        raise GossipReject("payload's block hash does not match the bid's block hash")

    # [REJECT] The envelope's execution requests root matches the bid's execution requests root
    if hash_tree_root(envelope.execution_requests) != bid.execution_requests_root:
        raise GossipReject("envelope's execution requests root does not match the bid")

    # [REJECT] The envelope signature is valid
    if not verify_execution_payload_envelope_signature(state, signed_execution_payload_envelope):
        raise GossipReject("invalid envelope signature")

    # Mark this envelope as seen and store its payload
    seen.execution_payload_envelopes.add(envelope_key)
    seen.execution_payloads[payload.block_hash] = payload
```

###### New `payload_attestation_message`

This topic is used to propagate signed payload attestation message.

```python
def validate_payload_attestation_message_gossip(
    seen: Seen,
    store: Store,
    state: BeaconState,
    payload_attestation_message: PayloadAttestationMessage,
    current_time_ms: uint64,
) -> None:
    """
    Validate a PayloadAttestationMessage for gossip propagation.
    Raises GossipIgnore or GossipReject on validation failure.
    """
    data = payload_attestation_message.data
    validator_index = payload_attestation_message.validator_index

    # [IGNORE] The message's slot is the current slot
    if not is_current_slot(state, data.slot, current_time_ms):
        raise GossipIgnore("payload attestation message slot is not the current slot")

    # [IGNORE] The message is the first valid message from this validator index
    seen_key = (data.slot, validator_index)
    if seen_key in seen.payload_attestation_validators:
        raise GossipIgnore("already seen payload attestation message from this validator")

    # [IGNORE] The message's block has been seen (via gossip or non-gossip sources)
    # (MAY be queued until block is retrieved)
    if data.beacon_block_root not in store.blocks:
        raise GossipIgnore("message's block has not been seen")

    # [IGNORE] The message's block is at the assigned slot
    if store.blocks[data.beacon_block_root].slot != data.slot:
        raise GossipIgnore("message's block is not at the assigned slot")

    # [REJECT] The message's block passes validation
    if data.beacon_block_root not in store.block_states:
        raise GossipReject("message's block failed validation")

    # [REJECT] The validator index is valid
    if validator_index >= len(state.validators):
        raise GossipReject("validator index out of range")

    # [REJECT] The validator is a member of the payload committee
    if validator_index not in get_ptc(state, data.slot):
        raise GossipReject("validator is not in the payload timeliness committee")

    # [REJECT] The signature is valid with respect to the validator's public key
    validator = state.validators[validator_index]
    domain = get_domain(state, DOMAIN_PTC_ATTESTER, compute_epoch_at_slot(data.slot))
    signing_root = compute_signing_root(data, domain)
    if not bls.Verify(validator.pubkey, signing_root, payload_attestation_message.signature):
        raise GossipReject("invalid payload attestation message signature")

    # Mark this message as seen
    seen.payload_attestation_validators.add(seen_key)
```

###### New `execution_payload_bid`

This topic is used to propagate signed bids as `SignedExecutionPayloadBid`.

```python
def validate_execution_payload_bid_gossip(
    seen: Seen,
    store: Store,
    state: BeaconState,
    signed_execution_payload_bid: SignedExecutionPayloadBid,
    current_time_ms: uint64,
) -> None:
    """
    Validate a SignedExecutionPayloadBid for gossip propagation.
    Raises GossipIgnore or GossipReject on validation failure.
    """
    bid = signed_execution_payload_bid.message

    # [IGNORE] The bid's slot is the current slot or the next slot
    if not is_current_or_next_slot(state, bid.slot, current_time_ms):
        raise GossipIgnore("bid slot is not the current or next slot")

    # [IGNORE] This is the first bid from this builder for this slot
    bid_key = (bid.builder_index, bid.slot)
    if bid_key in seen.execution_payload_bids:
        raise GossipIgnore("already seen valid bid from this builder for this slot")

    # [IGNORE] This is the highest value bid seen for the slot and parent
    best_bid_key = (bid.slot, bid.parent_block_hash, bid.parent_block_root)
    best_bid_value = seen.best_execution_payload_bid.get(best_bid_key, Gwei(0))
    if bid.value <= best_bid_value:
        raise GossipIgnore("bid is not the highest value bid seen for this slot and parent")

    # [REJECT] The builder index is valid
    if bid.builder_index >= len(state.builders):
        raise GossipReject("builder index out of range")

    # [IGNORE] The builder can cover the bid
    if not can_builder_cover_bid(state, bid.builder_index, bid.value):
        raise GossipIgnore("builder cannot cover bid value")

    # [REJECT] The bid's execution payment is zero
    if bid.execution_payment != 0:
        raise GossipReject("bid's execution payment must be zero")

    # [REJECT] The builder is active
    if not is_active_builder(state, bid.builder_index):
        raise GossipReject("builder is not active")

    # [REJECT] The bid's blob KZG commitment count is within the per-epoch limit
    proposal_epoch = compute_epoch_at_slot(bid.slot)
    max_blobs = get_blob_parameters(proposal_epoch).max_blobs_per_block
    if len(bid.blob_kzg_commitments) > max_blobs:
        raise GossipReject("too many blob kzg commitments")

    # [IGNORE] The bid's parent block root is a known beacon block
    # (MAY be queued until parent is retrieved)
    if bid.parent_block_root not in store.blocks:
        raise GossipIgnore("bid's parent block root is not a known beacon block")

    # [IGNORE] The bid's parent block hash is the hash of a known execution payload
    if bid.parent_block_hash not in seen.execution_payloads:
        raise GossipIgnore("bid's parent block hash is not a known execution payload")

    # [IGNORE] The bid's parent block state has been seen
    if bid.parent_block_root not in store.block_states:
        raise GossipIgnore("bid's parent block state is unavailable")

    # [IGNORE] The matching proposer preferences have been seen
    parent_state = store.block_states[bid.parent_block_root]
    dependent_root = get_proposer_dependent_root(parent_state, proposal_epoch)
    prefs_key = (dependent_root, bid.slot)
    if prefs_key not in seen.proposer_preferences:
        raise GossipIgnore("matching proposer preferences have not been seen")

    proposer_preferences = seen.proposer_preferences[prefs_key]

    # [REJECT] The bid's fee recipient matches the proposer's preference
    if bid.fee_recipient != proposer_preferences.fee_recipient:
        raise GossipReject("bid's fee recipient does not match the proposer's preference")

    # [IGNORE] The bid's gas limit is compatible with the proposer's target gas limit
    parent_gas_limit = seen.execution_payloads[bid.parent_block_hash].gas_limit
    if not is_gas_limit_target_compatible(
        parent_gas_limit, bid.gas_limit, proposer_preferences.target_gas_limit
    ):
        raise GossipIgnore("bid gas limit is not compatible with the proposer's target")

    # [REJECT] The bid signature is valid
    if not verify_execution_payload_bid_signature(state, signed_execution_payload_bid):
        raise GossipReject("invalid bid signature")

    # Mark this bid as seen and update the highest-value bid for this slot/parent
    seen.execution_payload_bids.add(bid_key)
    seen.best_execution_payload_bid[best_bid_key] = bid.value
```

*Note*: Implementations SHOULD include DoS prevention measures to mitigate spam
from malicious builders submitting numerous bids with minimal value increments.
Possible strategies include: (1) only forwarding bids that exceed the current
highest bid by a minimum threshold, or (2) forwarding only the highest observed
bid at regular time intervals.

###### New `proposer_preferences`

*[New in Gloas:EIP7732]*

This topic is used to propagate signed proposer preferences as
`SignedProposerPreferences`. These messages allow validators to communicate
their preferred `fee_recipient` and `target_gas_limit` to builders.

*Note*: Nodes SHOULD subscribe to this topic at least one epoch before the fork
activation. Proposers SHOULD broadcast their preferences in the epoch before the
fork.

```python
def validate_proposer_preferences_gossip(
    seen: Seen,
    store: Store,
    state: BeaconState,
    signed_proposer_preferences: SignedProposerPreferences,
    current_time_ms: uint64,
) -> None:
    """
    Validate a SignedProposerPreferences for gossip propagation.
    Raises GossipIgnore or GossipReject on validation failure.
    """
    preferences = signed_proposer_preferences.message

    # [IGNORE] The proposal slot's epoch is at or after the current epoch
    current_epoch = get_current_epoch(state)
    proposal_epoch = compute_epoch_at_slot(preferences.proposal_slot)
    if proposal_epoch < current_epoch:
        raise GossipIgnore("proposal slot is before the current epoch")

    # [IGNORE] The proposal slot's epoch is within the proposer lookahead
    if proposal_epoch > current_epoch + Epoch(MIN_SEED_LOOKAHEAD):
        raise GossipIgnore("proposal slot is past the proposer lookahead")

    # [IGNORE] The proposal slot has not already passed
    if is_not_from_future_slot(state, preferences.proposal_slot, current_time_ms):
        raise GossipIgnore("proposal slot has already passed")

    # [IGNORE] The dependent block has been seen (via gossip or non-gossip sources)
    # (MAY be queued until block is retrieved)
    if preferences.dependent_root not in store.blocks:
        raise GossipIgnore("dependent root block has not been seen")

    # [IGNORE] These are the first valid preferences seen for this dependent root and slot
    prefs_key = (preferences.dependent_root, preferences.proposal_slot)
    if prefs_key in seen.proposer_preferences:
        raise GossipIgnore("already seen preferences for this dependent root and proposal slot")

    # [IGNORE] The dependent root's state has been seen
    if preferences.dependent_root not in store.block_states:
        raise GossipIgnore("dependent root state is unavailable")

    # [REJECT] The validator is the proposer for the given slot in the proposer lookahead
    checkpoint_state = store.block_states[preferences.dependent_root].copy()
    checkpoint_epoch = Epoch(proposal_epoch - MIN_SEED_LOOKAHEAD)
    process_slots(checkpoint_state, compute_start_slot_at_epoch(checkpoint_epoch))
    if not is_valid_proposal_slot(checkpoint_state, preferences):
        raise GossipReject("validator is not the proposer for the given slot")

    # [REJECT] The validator index is valid
    if preferences.validator_index >= len(state.validators):
        raise GossipReject("validator index out of range")

    # [REJECT] The signature is valid with respect to the validator's public key
    validator = state.validators[preferences.validator_index]
    domain = get_domain(state, DOMAIN_PROPOSER_PREFERENCES, proposal_epoch)
    signing_root = compute_signing_root(preferences, domain)
    if not bls.Verify(validator.pubkey, signing_root, signed_proposer_preferences.signature):
        raise GossipReject("invalid proposer preferences signature")

    # Mark these preferences as seen
    seen.proposer_preferences[prefs_key] = preferences
```

##### Blob subnets

###### Modified `data_column_sidecar_{subnet_id}`

The KZG commitments needed to verify a sidecar are now carried by the bid at
`block.body.signed_execution_payload_bid.message.blob_kzg_commitments`, where
`block` is the `BeaconBlock` with root `sidecar.beacon_block_root`.

*Note*: If the sidecar fails deferred validation, its forwarding peers MUST be
downscored retroactively. If validation succeeds, the client MUST re-broadcast
the sidecar.

```python
def validate_data_column_sidecar_gossip(
    seen: Seen,
    store: Store,
    # [Modified in Gloas:EIP7732]
    # Removed `state`
    sidecar: DataColumnSidecar,
    # [Modified in Gloas:EIP7732]
    # Removed `current_time_ms`
    subnet_id: SubnetID,
) -> None:
    """
    Validate a DataColumnSidecar for gossip propagation on a subnet.
    Raises GossipIgnore or GossipReject on validation failure.
    """
    # [IGNORE] This is the first sidecar seen for this block root and column index
    sidecar_tuple = (sidecar.beacon_block_root, sidecar.index)
    if sidecar_tuple in seen.data_column_sidecar_tuples:
        raise GossipIgnore("already seen sidecar for this block root and index")

    # [REJECT] The sidecar is for the correct subnet
    if compute_subnet_for_data_column_sidecar(sidecar.index) != subnet_id:
        raise GossipReject("sidecar is for wrong subnet")

    # [IGNORE] A valid block for the sidecar has been seen (via gossip or non-gossip sources)
    # (MAY be queued until block is retrieved)
    # (SHOULD queue at least one sidecar per peer per subnet)
    if sidecar.beacon_block_root not in store.blocks:
        raise GossipIgnore("block for sidecar's beacon block root has not been seen")

    block = store.blocks[sidecar.beacon_block_root]

    # [REJECT] The sidecar's slot matches the slot of the block
    if sidecar.slot != block.slot:
        raise GossipReject("sidecar's slot does not match block's slot")

    bid = block.body.signed_execution_payload_bid.message

    # [REJECT] The sidecar passes structural validation
    if not verify_data_column_sidecar(sidecar, bid.blob_kzg_commitments):
        raise GossipReject("invalid sidecar")

    # [REJECT] The sidecar's column data passes KZG verification
    if not verify_data_column_sidecar_kzg_proofs(sidecar, bid.blob_kzg_commitments):
        raise GossipReject("invalid sidecar kzg proofs")

    # Mark this data column sidecar as seen
    seen.data_column_sidecar_tuples.add(sidecar_tuple)
```

##### Attestation subnets

###### Modified `beacon_attestation_{subnet_id}`

*Note*: This function is modified per EIP-7732. `attestation.data.index` is now
restricted to `{0, 1}`, encoding whether the execution payload was present at
the slot. Same-slot attestations MUST attest with `index == 0`. Attestations
with `index == 1` require that the corresponding execution payload envelope has
been seen and passes execution-layer validation.

```python
def validate_beacon_attestation_gossip(
    seen: Seen,
    store: Store,
    state: BeaconState,
    attestation: SingleAttestation,
    current_time_ms: uint64,
    subnet_id: SubnetID,
    # [New in Gloas:EIP7732]
    block_payload_statuses: Dict[Root, PayloadValidationStatus],
) -> None:
    """
    Validate a SingleAttestation for gossip propagation on a subnet.
    Raises GossipIgnore or GossipReject on validation failure.
    """
    data = attestation.data
    committee_index = attestation.committee_index
    attester_index = attestation.attester_index
    target_epoch = data.target.epoch

    # [New in Gloas:EIP7732]
    # [REJECT] The attestation's data index is 0 or 1
    if data.index > 1:
        raise GossipReject("attestation data index must be 0 or 1")

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

    # [IGNORE] The attestation's slot is not from a future slot
    # (MAY be queued for processing at the appropriate slot)
    if not is_not_from_future_slot(state, data.slot, current_time_ms):
        raise GossipIgnore("attestation slot is from a future slot")

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

    # [REJECT] The attester is a member of the committee
    committee = get_beacon_committee(state, data.slot, committee_index)
    if attester_index not in committee:
        raise GossipReject("attester is not a member of the committee")

    # [IGNORE] No other valid attestation seen for this validator and target epoch
    if (attester_index, target_epoch) in seen.attestation_validator_epochs:
        raise GossipIgnore("already seen attestation from this validator for this epoch")

    # [REJECT] The attestation signature is valid
    attester = state.validators[attester_index]
    domain = get_domain(state, DOMAIN_BEACON_ATTESTER, target_epoch)
    signing_root = compute_signing_root(data, domain)
    if not bls.Verify(attester.pubkey, signing_root, attestation.signature):
        raise GossipReject("invalid attestation signature")

    # [IGNORE] The block being voted for has been seen (via gossip or non-gossip sources)
    # (MAY be queued until block is retrieved)
    beacon_block_root = data.beacon_block_root
    if beacon_block_root not in store.blocks:
        raise GossipIgnore("block being voted for has not been seen")

    # [REJECT] The block being voted for passes validation
    if beacon_block_root not in store.block_states:
        raise GossipReject("block being voted for failed validation")

    block = store.blocks[beacon_block_root]

    # [New in Gloas:EIP7732]
    # [REJECT] For same-slot attestations, the payload cannot yet be present
    if block.slot == data.slot and data.index != 0:
        raise GossipReject("same-slot attestation must attest with index 0")

    if data.index == 1:
        # [New in Gloas:EIP7732]
        # [IGNORE] The corresponding execution payload envelope has been seen
        # (MAY queue attestations for processing once the payload is retrieved and
        # SHOULD request the payload envelope via ExecutionPayloadEnvelopesByRoot
        # using data.beacon_block_root)
        payload_status = block_payload_statuses.get(beacon_block_root)
        if payload_status is None:
            raise GossipIgnore("execution payload envelope has not been seen")

        # [New in Gloas:EIP7732]
        # [IGNORE] The corresponding execution payload has been validated
        if payload_status == PAYLOAD_STATUS_NOT_VALIDATED:
            raise GossipIgnore("execution payload pending EL validation")

        # [New in Gloas:EIP7732]
        # [REJECT] The corresponding execution payload passes EL validation
        if payload_status == PAYLOAD_STATUS_INVALIDATED:
            raise GossipReject("execution payload failed EL validation")

    # [REJECT] The attestation's target block is an ancestor of the LMD vote block
    target_checkpoint_block = get_checkpoint_block(store, beacon_block_root, target_epoch)
    if target_checkpoint_block != data.target.root:
        raise GossipReject("target block is not an ancestor of LMD vote block")

    # [IGNORE] The current finalized checkpoint is an ancestor of the block
    finalized_checkpoint_block = get_checkpoint_block(
        store, beacon_block_root, store.finalized_checkpoint.epoch
    )
    if finalized_checkpoint_block != store.finalized_checkpoint.root:
        raise GossipIgnore("finalized checkpoint is not an ancestor of block")

    # Mark this attestation as seen
    seen.attestation_validator_epochs.add((attester_index, target_epoch))
```

### The Req/Resp domain

#### Messages

##### BeaconBlocksByRange v2

**Protocol ID:** `/eth2/beacon_chain/req/beacon_blocks_by_range/2/`

<!-- eth_consensus_specs: skip -->

| `fork_version`           | Chunk SSZ type                |
| ------------------------ | ----------------------------- |
| `GENESIS_FORK_VERSION`   | `phase0.SignedBeaconBlock`    |
| `ALTAIR_FORK_VERSION`    | `altair.SignedBeaconBlock`    |
| `BELLATRIX_FORK_VERSION` | `bellatrix.SignedBeaconBlock` |
| `CAPELLA_FORK_VERSION`   | `capella.SignedBeaconBlock`   |
| `DENEB_FORK_VERSION`     | `deneb.SignedBeaconBlock`     |
| `ELECTRA_FORK_VERSION`   | `electra.SignedBeaconBlock`   |
| `FULU_FORK_VERSION`      | `fulu.SignedBeaconBlock`      |
| `GLOAS_FORK_VERSION`     | `gloas.SignedBeaconBlock`     |

##### BeaconBlocksByRoot v2

**Protocol ID:** `/eth2/beacon_chain/req/beacon_blocks_by_root/2/`

<!-- eth_consensus_specs: skip -->

| `fork_version`           | Chunk SSZ type                |
| ------------------------ | ----------------------------- |
| `GENESIS_FORK_VERSION`   | `phase0.SignedBeaconBlock`    |
| `ALTAIR_FORK_VERSION`    | `altair.SignedBeaconBlock`    |
| `BELLATRIX_FORK_VERSION` | `bellatrix.SignedBeaconBlock` |
| `CAPELLA_FORK_VERSION`   | `capella.SignedBeaconBlock`   |
| `DENEB_FORK_VERSION`     | `deneb.SignedBeaconBlock`     |
| `ELECTRA_FORK_VERSION`   | `electra.SignedBeaconBlock`   |
| `FULU_FORK_VERSION`      | `fulu.SignedBeaconBlock`      |
| `GLOAS_FORK_VERSION`     | `gloas.SignedBeaconBlock`     |

##### ExecutionPayloadEnvelopesByRange v1

**Protocol ID:**
`/eth2/beacon_chain/req/execution_payload_envelopes_by_range/1/`

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
  List[SignedExecutionPayloadEnvelope, MAX_REQUEST_BLOCKS_DENEB]
)
```

Specifications of req\\response methods are equivalent to
[BeaconBlocksByRange v2](#beaconblocksbyrange-v2), with the only difference
being the response content type.

For each successful `response_chunk`, the `ForkDigest` context epoch is
determined by `compute_epoch_at_slot(beacon_block.slot)` based on the
`beacon_block` referred to by
`signed_execution_payload_envelope.message.beacon_block_root`.

Per `fork_version = compute_fork_version(epoch)`:

<!-- eth_consensus_specs: skip -->

| `fork_version`       | Chunk SSZ type                         |
| -------------------- | -------------------------------------- |
| `GLOAS_FORK_VERSION` | `gloas.SignedExecutionPayloadEnvelope` |

##### ExecutionPayloadEnvelopesByRoot v1

**Protocol ID:** `/eth2/beacon_chain/req/execution_payload_envelopes_by_root/1/`

For each successful `response_chunk`, the `ForkDigest` context epoch is
determined by `compute_epoch_at_slot(beacon_block.slot)` based on the
`beacon_block` referred to by
`signed_execution_payload_envelope.message.beacon_block_root`.

Per `fork_version = compute_fork_version(epoch)`:

<!-- eth_consensus_specs: skip -->

| `fork_version`       | Chunk SSZ type                         |
| -------------------- | -------------------------------------- |
| `GLOAS_FORK_VERSION` | `gloas.SignedExecutionPayloadEnvelope` |

Request Content:

```
(
  List[Root, MAX_REQUEST_PAYLOADS]
)
```

Response Content:

```
(
  List[SignedExecutionPayloadEnvelope, MAX_REQUEST_PAYLOADS]
)
```

Requests execution payload envelopes by
`signed_execution_payload_envelope.message.beacon_block_root`. The response is a
list of `SignedExecutionPayloadEnvelope` whose length is less than or equal to
the number of requested execution payload envelopes. It may be less in the case
that the responding peer is missing payload envelopes.

No more than `MAX_REQUEST_PAYLOADS` may be requested at a time.

ExecutionPayloadEnvelopesByRoot is primarily used to recover recent execution
payload envelopes and attestations (e.g. when receiving a payload attestation or
attestation with revealed status as true but never received a payload).

The request MUST be encoded as an SSZ-field.

The response MUST consist of zero or more `response_chunk`. Each successful
`response_chunk` MUST contain a single `SignedExecutionPayloadEnvelope` payload.

Clients MUST support requesting payload envelopes on the epoch range
`[max(GLOAS_FORK_EPOCH, current_epoch - compute_min_epochs_for_block_requests()), current_epoch]`.
If any root in the request content references a block earlier than this range,
peers MAY respond with error code `3: ResourceUnavailable` or not include the
payload envelope in the response.

Clients MUST respond with at least one payload envelope, if they have it.
Clients MAY limit the number of payload envelopes in the response.
