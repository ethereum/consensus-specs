# PQ -- Networking

*Note*: This document is a work-in-progress for researchers and implementers.

<!-- mdformat-toc start --slug=github --no-anchors --maxlevel=6 --minlevel=2 -->

- [Introduction](#introduction)
- [Configs](#configs)
- [Presets](#presets)
  - [Type-specific SSZ bounds](#type-specific-ssz-bounds)
- [Containers](#containers)
  - [Modified `SignedProposerPreferences`](#modified-signedproposerpreferences)
- [Helpers](#helpers)
  - [Modified `compute_fork_version`](#modified-compute_fork_version)
  - [Modified `verify_block_body_operation_limits`](#modified-verify_block_body_operation_limits)
  - [Modified `verify_execution_requests_limits`](#modified-verify_execution_requests_limits)
  - [Modified `compute_attestation_subnet_prefix_bits`](#modified-compute_attestation_subnet_prefix_bits)
  - [Modified `compute_subscribed_subnet`](#modified-compute_subscribed_subnet)
- [The gossip domain: gossipsub](#the-gossip-domain-gossipsub)
  - [Topics and messages](#topics-and-messages)
    - [Global topics](#global-topics)
      - [Modified `beacon_block`](#modified-beacon_block)
      - [Modified `beacon_aggregate_and_proof`](#modified-beacon_aggregate_and_proof)
      - [Modified `voluntary_exit`](#modified-voluntary_exit)
      - [Modified `proposer_slashing`](#modified-proposer_slashing)
      - [Removed `sync_committee_contribution_and_proof`](#removed-sync_committee_contribution_and_proof)
      - [Modified `payload_attestation_message`](#modified-payload_attestation_message)
      - [Modified `execution_payload_bid`](#modified-execution_payload_bid)
      - [Modified `proposer_preferences`](#modified-proposer_preferences)
    - [Attestation subnets](#attestation-subnets)
      - [Modified `beacon_attestation_{subnet_id}`](#modified-beacon_attestation_subnet_id)
    - [Sync committee subnets](#sync-committee-subnets)

<!-- mdformat-toc end -->

## Introduction

This document contains the consensus-layer networking specifications for PQ.

The specification of these changes continues in the same format as the network
specifications of previous upgrades, and assumes them as pre-requisite.

Sync committees are removed in PQ, and with them the light client protocol, so
the light client topics and request/response methods are no longer used.

## Configs

*[New in PQ]*

| Name                          | Value                 |
| ----------------------------- | --------------------- |
| `ATTESTATION_SUBNET_COUNT_PQ` | `Uint64(2**4)` (= 16) |

## Presets

### Type-specific SSZ bounds

*[New in PQ]*

These constants supersede the
[Gloas type-specific SSZ bounds](../../gloas/p2p-interface.md#type-specific-ssz-bounds),
which were sized for BLS signatures.

| Name                                       | Value                         |
| ------------------------------------------ | ----------------------------- |
| `MAX_SIGNED_AGGREGATE_AND_PROOF_SIZE_PQ`   | `Uint64(1068549)` (= ~1 MiB)  |
| `MAX_ATTESTER_SLASHING_SIZE_PQ`            | `Uint64(4194584)` (= ~4 MiB)  |
| `MAX_SIGNED_EXECUTION_PAYLOAD_BID_SIZE_PQ` | `Uint64(199240)` (= ~195 KiB) |

## Containers

### Modified `SignedProposerPreferences`

```python
class SignedProposerPreferences(Container):
    message: ProposerPreferences
    # [Modified in PQ]
    signature: XMSSSignature
```

## Helpers

### Modified `compute_fork_version`

```python
def compute_fork_version(epoch: Epoch) -> Version:
    """
    Return the fork version at the given ``epoch``.
    """
    if epoch >= PQ_FORK_EPOCH:
        return PQ_FORK_VERSION
    if epoch >= EIP8483_FORK_EPOCH:
        return EIP8483_FORK_VERSION
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

### Modified `verify_block_body_operation_limits`

*Note*: These checks MAY be performed when deserializing `BeaconBlockBody`.

```python
def verify_block_body_operation_limits(body: BeaconBlockBody) -> None:
    """
    Verify that each block body operation count is within its limit.
    Raises GossipReject on validation failure.
    """
    # [REJECT] The proposer slashing count is within the limit
    if len(body.proposer_slashings) > MAX_PROPOSER_SLASHINGS:
        raise GossipReject("too many proposer slashings")

    # [REJECT] The attester slashing count is within the limit
    if len(body.attester_slashings) > MAX_ATTESTER_SLASHINGS_ELECTRA:
        raise GossipReject("too many attester slashings")

    # [Modified in PQ]
    # [REJECT] The attestation count is within the limit
    if len(body.attestations) > MAX_ATTESTATIONS_PQ:
        raise GossipReject("too many attestations")

    # [REJECT] The block contains no deposits
    if len(body.deposits) != 0:
        raise GossipReject("block must not contain deposits")

    # [REJECT] The voluntary exit count is within the limit
    if len(body.voluntary_exits) > MAX_VOLUNTARY_EXITS:
        raise GossipReject("too many voluntary exits")

    # [Modified in PQ]
    # Removed the BLS to execution change limit

    # [Modified in PQ]
    # Removed the payload attestation limit
```

### Modified `verify_execution_requests_limits`

*Note*: These checks MAY be performed when deserializing `ExecutionRequests`.

```python
def verify_execution_requests_limits(execution_requests: ExecutionRequests) -> None:
    """
    Verify that each execution request count is within its limit.
    Raises GossipReject on validation failure.
    """
    # [REJECT] The withdrawal request count is within the limit
    if len(execution_requests.withdrawals) > MAX_WITHDRAWAL_REQUESTS_PER_PAYLOAD:
        raise GossipReject("too many withdrawal requests")

    # [REJECT] The consolidation request count is within the limit
    if len(execution_requests.consolidations) > MAX_CONSOLIDATION_REQUESTS_PER_PAYLOAD:
        raise GossipReject("too many consolidation requests")

    # [REJECT] The builder deposit request count is within the limit
    if len(execution_requests.builder_deposits) > MAX_BUILDER_DEPOSIT_REQUESTS_PER_PAYLOAD:
        raise GossipReject("too many builder deposit requests")

    # [REJECT] The builder exit request count is within the limit
    if len(execution_requests.builder_exits) > MAX_BUILDER_EXIT_REQUESTS_PER_PAYLOAD:
        raise GossipReject("too many builder exit requests")

    # [Modified in PQ]
    # Removed the validator and builder PQ registration request limits

    # [New in EIP8205]
    # [REJECT] The preregistration request count is within the limit
    if len(execution_requests.preregistrations) > MAX_PREREGISTRATION_REQUESTS_PER_PAYLOAD:
        raise GossipReject("too many preregistration requests")
```

### Modified `compute_attestation_subnet_prefix_bits`

```python
def compute_attestation_subnet_prefix_bits() -> Uint64:
    """
    Return the number of NodeId bits to use when mapping to a subscribed subnet.
    """
    # [Modified in PQ]
    return ceillog2(ATTESTATION_SUBNET_COUNT_PQ) + ATTESTATION_SUBNET_EXTRA_BITS
```

### Modified `compute_subscribed_subnet`

```python
def compute_subscribed_subnet(node_id: NodeID, epoch: Epoch, index: int) -> SubnetID:
    prefix_bits = int(compute_attestation_subnet_prefix_bits())
    node_id_prefix = node_id >> int(NODE_ID_BITS - prefix_bits)
    node_offset = Uint64(node_id % Uint256(EPOCHS_PER_SUBNET_SUBSCRIPTION))
    permutation_seed = sha256(
        uint_to_bytes(Uint64((epoch + node_offset) // EPOCHS_PER_SUBNET_SUBSCRIPTION))
    )
    permutated_prefix = compute_shuffled_index(
        Uint64(node_id_prefix),
        Uint64(1 << prefix_bits),
        permutation_seed,
    )
    # [Modified in PQ]
    return SubnetID((permutated_prefix + index) % ATTESTATION_SUBNET_COUNT_PQ)
```

## The gossip domain: gossipsub

### Topics and messages

Topics follow the same specification as in prior upgrades. Every topic whose
message holds a validator or builder signature is updated to the modified type,
which carries an XMSS signature instead. The `bls_to_execution_change` topic is
removed, because `BLSToExecutionChange` is disabled.

#### Global topics

##### Modified `beacon_block`

```python
def validate_beacon_block_gossip(
    seen: Seen,
    store: Store,
    signed_beacon_block: SignedBeaconBlock,
    current_time_ms: Uint64,
) -> None:
    """
    Validate a SignedBeaconBlock for gossip propagation.
    Raises GossipIgnore or GossipReject on validation failure.
    """
    block = signed_beacon_block.message
    bid = block.body.signed_execution_payload_bid.message

    # [IGNORE] The block is the first block with valid signature received for the slot and proposer
    proposer_slot_key = (block.slot, block.proposer_index)
    if proposer_slot_key in seen.proposer_slots:
        raise GossipIgnore("block is not the first valid block for this slot and proposer")

    # [IGNORE] The block is not from a future slot
    # (MAY be queued for processing at the appropriate slot)
    if is_future_slot(store, block.slot, current_time_ms):
        raise GossipIgnore("block is from a future slot")

    # [IGNORE] The block is from a slot greater than the latest finalized slot
    # (MAY choose to validate and store such blocks for additional purposes
    # -- e.g. slashing detection, archive nodes, etc)
    finalized_slot = compute_start_slot_at_epoch(store.finalized_checkpoint.epoch)
    if block.slot <= finalized_slot:
        raise GossipIgnore("block is not from a slot greater than the latest finalized slot")

    # [REJECT] The block body operation counts are within their limits
    verify_block_body_operation_limits(block.body)

    # [REJECT] The parent execution request counts are within their limits
    verify_execution_requests_limits(block.body.parent_execution_requests)

    # [IGNORE] The block's parent has been seen (via gossip or non-gossip sources)
    # (MAY be queued until parent is retrieved)
    if block.parent_root not in store.blocks:
        raise GossipIgnore("block's parent has not been seen")

    # [REJECT] The block's parent passes validation
    if block.parent_root not in store.block_states:
        raise GossipReject("block's parent is invalid")

    state = store.block_states[get_head(store).root]

    # [REJECT] The proposer index is a valid validator index
    if block.proposer_index >= len(state.validators):
        raise GossipReject("proposer index out of range")

    # [REJECT] The proposer signature is valid
    proposer = state.validators[block.proposer_index]
    domain = get_domain(state, DOMAIN_BEACON_PROPOSER, compute_epoch_at_slot(block.slot))
    signing_root = compute_signing_root(block, domain)
    # [Modified in PQ]
    leaf_index = compute_xmss_leaf_index(block.slot, LEAF_OFFSET_BEACON_PROPOSER)
    if not xmss.Verify(proposer.pubkey, leaf_index, signing_root, signed_beacon_block.signature):
        raise GossipReject("invalid proposer signature")

    # [IGNORE] If the parent block is full, the parent payload is valid
    # (MAY be queued until the parent payload is verified)
    if is_parent_node_full(store, block):
        if not is_payload_verified(store, block.parent_root):
            raise GossipIgnore("parent payload is not verified")

    # [REJECT] The block is from a higher slot than its parent
    if block.slot <= store.blocks[block.parent_root].slot:
        raise GossipReject("block is not from a higher slot than its parent")

    # [REJECT] The current finalized checkpoint is an ancestor of the block
    finalized_epoch = store.finalized_checkpoint.epoch
    finalized_checkpoint_block = get_checkpoint_block(store, block.parent_root, finalized_epoch)
    if finalized_checkpoint_block != store.finalized_checkpoint.root:
        raise GossipReject("finalized checkpoint is not an ancestor of block")

    # [REJECT] The bid's blob KZG commitment count is within the per-epoch limit
    max_blobs = get_blob_parameters(compute_epoch_at_slot(block.slot)).max_blobs_per_block
    if len(bid.blob_kzg_commitments) > max_blobs:
        raise GossipReject("too many blob kzg commitments")

    # [REJECT] The bid's parent equals the block's parent
    if bid.parent_block_root != block.parent_root:
        raise GossipReject("bid's parent does not equal block's parent")

    # [REJECT] The block is proposed by the expected proposer for the slot
    parent_state = store.block_states[block.parent_root].copy()
    process_slots(parent_state, block.slot)
    expected_proposer = get_beacon_proposer_index(parent_state)
    if block.proposer_index != expected_proposer:
        raise GossipReject("block proposer_index does not match expected proposer")

    # [REJECT] If the parent is not full, the bid builds on the parent's execution head
    if not is_parent_node_full(store, block):
        if bid.parent_block_hash != parent_state.latest_block_hash:
            raise GossipReject("bid does not build on the parent's execution head")

    # Mark this block as seen
    seen.proposer_slots.add(proposer_slot_key)
```

##### Modified `beacon_aggregate_and_proof`

```python
def validate_beacon_aggregate_and_proof_gossip(
    seen: Seen,
    store: Store,
    signed_aggregate_and_proof: SignedAggregateAndProof,
    current_time_ms: Uint64,
    block_payload_statuses: dict[Root, PayloadValidationStatus],
) -> None:
    """
    Validate a SignedAggregateAndProof for gossip propagation.
    Raises GossipIgnore or GossipReject on validation failure.
    """
    aggregate_and_proof = signed_aggregate_and_proof.message
    aggregate = aggregate_and_proof.aggregate
    aggregation_bits = aggregate.aggregation_bits

    # [REJECT] The aggregate attestation's data index is 0 or 1
    if aggregate.data.index > 1:
        raise GossipReject("aggregate data index must be 0 or 1")

    # [REJECT] Exactly one committee is specified by the committee bits
    committee_indices = get_committee_indices(aggregate.committee_bits)
    if len(committee_indices) != 1:
        raise GossipReject("aggregate committee bits must specify exactly one committee")
    index = committee_indices[0]

    # [IGNORE] A valid aggregate with a superset of aggregation bits has not already been seen
    aggregate_data_root = hash_tree_root(aggregate.data)
    aggregate_cache_key = (aggregate_data_root, index)
    aggregate_bits = tuple(bool(bit) for bit in aggregation_bits)
    seen_bits = seen.aggregate_data_roots.get(aggregate_cache_key, set())
    if is_non_strict_superset(seen_bits, aggregate_bits):
        raise GossipIgnore("already seen aggregate for this data")

    # [IGNORE] This is the first valid aggregate for this epoch and aggregator
    aggregator_index = aggregate_and_proof.aggregator_index
    target_epoch = aggregate.data.target.epoch
    aggregator_epoch_key = (target_epoch, aggregator_index)
    if aggregator_epoch_key in seen.aggregator_epochs:
        raise GossipIgnore("already seen aggregate for this epoch and aggregator")

    # [IGNORE] The block being voted for has been seen (via gossip or non-gossip sources)
    # (MAY be queued until block is retrieved)
    block_root = aggregate.data.beacon_block_root
    if block_root not in store.blocks:
        raise GossipIgnore("block being voted for has not been seen")

    # [REJECT] The block being voted for passes validation
    if block_root not in store.block_states:
        raise GossipReject("block being voted for failed validation")

    state = store.block_states[get_head(store).root]

    # [REJECT] The committee index is within the expected range
    committee_count = get_committee_count_per_slot(state, aggregate.data.target.epoch)
    if index >= committee_count:
        raise GossipReject("committee index out of range")

    # [IGNORE] The aggregate attestation's slot is not from a future slot
    # (MAY be queued for processing at the appropriate slot)
    if is_future_slot(store, aggregate.data.slot, current_time_ms):
        raise GossipIgnore("aggregate slot is from a future slot")

    # [IGNORE] The aggregate attestation's epoch is either the current or previous epoch
    attestation_epoch = compute_epoch_at_slot(aggregate.data.slot)
    if not is_current_or_previous_epoch(store, attestation_epoch, current_time_ms):
        raise GossipIgnore("aggregate epoch is not current or previous epoch")

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

    # [Modified in PQ]
    # [REJECT] The selection proof selects the validator as an aggregator
    if not is_aggregator(
        state,
        aggregate.data.slot,
        index,
        aggregator_index,
        aggregate_and_proof.selection_proof,
    ):
        raise GossipReject("validator is not selected as aggregator")

    # [REJECT] The aggregator is a member of the committee
    if aggregator_index not in committee:
        raise GossipReject("aggregator is not a member of the committee")

    # [Modified in PQ]
    # [REJECT] The selection proof is valid
    if not is_valid_vrf_proof(
        state, aggregator_index, aggregate.data.slot, aggregate_and_proof.selection_proof
    ):
        raise GossipReject("invalid selection proof")

    # [REJECT] The aggregator signature is valid
    domain = get_domain(state, DOMAIN_AGGREGATE_AND_PROOF, target_epoch)
    signing_root = compute_signing_root(aggregate_and_proof, domain)
    # [Modified in PQ]
    leaf_index = compute_xmss_leaf_index(aggregate.data.slot, LEAF_OFFSET_AGGREGATE_AND_PROOF)
    pubkey = state.validators[aggregator_index].pubkey
    if not xmss.Verify(pubkey, leaf_index, signing_root, signed_aggregate_and_proof.signature):
        raise GossipReject("invalid aggregator signature")

    # [Modified in PQ]
    # [REJECT] The aggregate stark is valid
    statements = get_attestation_statements(state, aggregate)
    if not stark.VerifyAggregates(statements, aggregate_and_proof.proof):
        raise GossipReject("invalid aggregate stark")

    # [REJECT] The target block is an ancestor of the LMD vote block
    checkpoint_block = get_checkpoint_block(store, block_root, aggregate.data.target.epoch)
    if checkpoint_block != aggregate.data.target.root:
        raise GossipReject("target block is not an ancestor of LMD vote block")

    # [IGNORE] The finalized checkpoint is an ancestor of the block
    finalized_epoch = store.finalized_checkpoint.epoch
    finalized_checkpoint_block = get_checkpoint_block(store, block_root, finalized_epoch)
    if finalized_checkpoint_block != store.finalized_checkpoint.root:
        raise GossipIgnore("finalized checkpoint is not an ancestor of block")

    # The attested payload status is consistent with the block's execution payload
    verify_attestation_payload_status(store, aggregate.data, block_payload_statuses)

    # Mark this aggregate as seen
    seen.aggregator_epochs.add(aggregator_epoch_key)
    if aggregate_cache_key not in seen.aggregate_data_roots:
        seen.aggregate_data_roots[aggregate_cache_key] = set()
    seen.aggregate_data_roots[aggregate_cache_key].add(aggregate_bits)
```

##### Modified `voluntary_exit`

```python
def validate_voluntary_exit_gossip(
    seen: Seen,
    store: Store,
    signed_voluntary_exit: SignedVoluntaryExit,
    current_time_ms: Uint64,
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

    # [IGNORE] The voluntary exit epoch is not in the future
    if is_future_epoch(store, voluntary_exit.epoch, current_time_ms):
        raise GossipIgnore("voluntary exit epoch is in the future")

    state = store.block_states[get_head(store).root]

    # [REJECT] The validator index is valid
    if validator_index >= len(state.validators):
        raise GossipReject("validator index out of range")

    validator = state.validators[validator_index]
    current_epoch = get_current_epoch(state)

    # [IGNORE] The validator has not already initiated exit
    if validator.exit_epoch != FAR_FUTURE_EPOCH:
        raise GossipIgnore("validator has already initiated exit")

    # [REJECT] The validator is active
    if not is_active_validator(validator, current_epoch):
        raise GossipReject("validator is not active")

    # [REJECT] The validator has been active long enough
    if current_epoch < validator.activation_epoch + SHARD_COMMITTEE_PERIOD:
        raise GossipReject("validator has not been active long enough")

    # [IGNORE] The validator has no pending partial withdrawals
    if get_pending_balance_to_withdraw(state, validator_index) != 0:
        raise GossipIgnore("validator has pending partial withdrawals")

    # [REJECT] The signature is valid
    domain = compute_domain(
        DOMAIN_VOLUNTARY_EXIT, CAPELLA_FORK_VERSION, state.genesis_validators_root
    )
    signing_root = compute_signing_root(voluntary_exit, domain)
    # [Modified in PQ]
    if not xmss.Verify(
        validator.pubkey,
        RESERVED_LEAF_VOLUNTARY_EXIT,
        signing_root,
        signed_voluntary_exit.signature,
    ):
        raise GossipReject("invalid voluntary exit signature")

    # Mark this voluntary exit as seen
    seen.voluntary_exit_indices.add(validator_index)
```

##### Modified `proposer_slashing`

```python
def validate_proposer_slashing_gossip(
    seen: Seen,
    store: Store,
    proposer_slashing: ProposerSlashing,
) -> None:
    """
    Validate a ProposerSlashing for gossip propagation.
    Raises GossipIgnore or GossipReject on validation failure.
    """
    header_1 = proposer_slashing.signed_header_1.message
    header_2 = proposer_slashing.signed_header_2.message
    proposer_index = header_1.proposer_index

    # [IGNORE] The proposer slashing is the first valid proposer slashing received for this proposer
    if proposer_index in seen.proposer_slashing_indices:
        raise GossipIgnore("already seen proposer slashing for this proposer")

    # [REJECT] The header slots match
    if header_1.slot != header_2.slot:
        raise GossipReject("header slots do not match")

    # [REJECT] The header proposer indices match
    if header_1.proposer_index != header_2.proposer_index:
        raise GossipReject("header proposer indices do not match")

    # [REJECT] The headers are different
    if header_1 == header_2:
        raise GossipReject("headers are not different")

    state = store.block_states[get_head(store).root]

    # [REJECT] The proposer index is a valid validator index
    if proposer_index >= len(state.validators):
        raise GossipReject("proposer index out of range")

    # [REJECT] The proposer is slashable
    proposer = state.validators[proposer_index]
    if not is_slashable_validator(proposer, get_current_epoch(state)):
        raise GossipReject("proposer is not slashable")

    # [REJECT] The signatures are valid
    for signed_header in (proposer_slashing.signed_header_1, proposer_slashing.signed_header_2):
        domain = get_domain(
            state, DOMAIN_BEACON_PROPOSER, compute_epoch_at_slot(signed_header.message.slot)
        )
        signing_root = compute_signing_root(signed_header.message, domain)
        # [Modified in PQ]
        leaf_index = compute_xmss_leaf_index(
            signed_header.message.slot, LEAF_OFFSET_BEACON_PROPOSER
        )
        if not xmss.Verify(proposer.pubkey, leaf_index, signing_root, signed_header.signature):
            raise GossipReject("invalid proposer slashing signature")

    # Mark this proposer slashing as seen
    seen.proposer_slashing_indices.add(proposer_index)
```

##### Removed `sync_committee_contribution_and_proof`

Sync committees are removed in PQ, so this topic is no longer used.

##### Modified `payload_attestation_message`

```python
def validate_payload_attestation_message_gossip(
    seen: Seen,
    store: Store,
    payload_attestation_message: PayloadAttestationMessage,
    current_time_ms: Uint64,
) -> None:
    """
    Validate a PayloadAttestationMessage for gossip propagation.
    Raises GossipIgnore or GossipReject on validation failure.
    """
    data = payload_attestation_message.data
    validator_index = payload_attestation_message.validator_index

    # [REJECT] The payload attestation's slot is at or after the Gloas fork
    if compute_epoch_at_slot(data.slot) < GLOAS_FORK_EPOCH:
        raise GossipReject("payload attestation's slot is pre-gloas")

    # [IGNORE] This is the first valid payload attestation from this validator index
    payload_attestation_key = (data.slot, validator_index)
    if payload_attestation_key in seen.payload_attestation_validators:
        raise GossipIgnore("already seen payload attestation from this validator")

    # [IGNORE] The payload attestation's slot is for the current slot
    if not is_current_slot(store, data.slot, current_time_ms):
        raise GossipIgnore("payload attestation is not for the current slot")

    # [IGNORE] The payload attestation's block has been seen (via gossip or non-gossip sources)
    # (MAY be queued until block is retrieved)
    if data.beacon_block_root not in store.blocks:
        raise GossipIgnore("payload attestation's block has not been seen")

    # [REJECT] The payload attestation's block passes validation
    if data.beacon_block_root not in store.block_states:
        raise GossipReject("payload attestation's block failed validation")

    # [IGNORE] The payload attestation's block is at the assigned slot
    if store.blocks[data.beacon_block_root].slot != data.slot:
        raise GossipIgnore("payload attestation's block is not at the assigned slot")

    state = store.block_states[get_head(store).root]

    # [REJECT] The validator index is valid
    if validator_index >= len(state.validators):
        raise GossipReject("validator index out of range")

    # [REJECT] The validator is a member of the payload timeliness committee
    if validator_index not in get_ptc(state, data.slot):
        raise GossipReject("validator is not in the payload timeliness committee")

    # [REJECT] The signature is valid
    validator = state.validators[validator_index]
    domain = get_domain(state, DOMAIN_PTC_ATTESTER, compute_epoch_at_slot(data.slot))
    signing_root = compute_signing_root(data, domain)
    # [Modified in PQ]
    leaf_index = compute_xmss_leaf_index(data.slot, LEAF_OFFSET_PTC_ATTESTER)
    if not xmss.Verify(
        validator.pubkey, leaf_index, signing_root, payload_attestation_message.signature
    ):
        raise GossipReject("invalid payload attestation signature")

    # Mark this payload_attestation as seen
    seen.payload_attestation_validators.add(payload_attestation_key)
```

##### Modified `execution_payload_bid`

*Note*: A builder signs all of its bids for a slot at the same leaf, so it must
not sign two different bids for the same slot. In particular, it cannot bid on
two different parents in the same slot, even though this topic accepts one bid
per parent.

```python
def validate_execution_payload_bid_gossip(
    seen: Seen,
    store: Store,
    signed_execution_payload_bid: SignedExecutionPayloadBid,
    current_time_ms: Uint64,
) -> None:
    """
    Validate a SignedExecutionPayloadBid for gossip propagation.
    Raises GossipIgnore or GossipReject on validation failure.
    """
    bid = signed_execution_payload_bid.message

    # [IGNORE] This is the first bid for this slot, parent, and builder
    bid_key = (bid.slot, bid.parent_block_hash, bid.parent_block_root, bid.builder_index)
    if bid_key in seen.execution_payload_bids:
        raise GossipIgnore("already seen valid bid for this slot, parent, and builder")

    # [IGNORE] This is the highest value bid seen for the slot and parent
    best_bid_key = (bid.slot, bid.parent_block_hash, bid.parent_block_root)
    if best_bid_key in seen.best_execution_payload_bid:
        if bid.value <= seen.best_execution_payload_bid[best_bid_key]:
            raise GossipIgnore("bid is not the highest value bid seen for this slot and parent")

    # [IGNORE] The bid's slot is the current slot or the next slot
    if not is_current_or_next_slot(store, bid.slot, current_time_ms):
        raise GossipIgnore("bid's slot is not the current or next slot")

    # [REJECT] The bid's execution payment is zero
    if bid.execution_payment != 0:
        raise GossipReject("bid's execution payment must be zero")

    # [REJECT] The bid's block hash is not equal to its parent block hash
    if bid.block_hash == bid.parent_block_hash:
        raise GossipReject("bid's block hash equals its parent block hash")

    # [REJECT] The bid's blob KZG commitment count is within the per-epoch limit
    proposal_epoch = compute_epoch_at_slot(bid.slot)
    max_blobs = get_blob_parameters(proposal_epoch).max_blobs_per_block
    if len(bid.blob_kzg_commitments) > max_blobs:
        raise GossipReject("too many blob kzg commitments")

    # [IGNORE] The bid's parent block root is a known beacon block
    # (MAY be queued until parent is retrieved)
    if bid.parent_block_root not in store.blocks:
        raise GossipIgnore("bid's parent block root is not a known beacon block")

    # [REJECT] The bid is for a higher slot than its parent block
    if bid.slot <= store.blocks[bid.parent_block_root].slot:
        raise GossipReject("bid's slot is not higher than its parent's slot")

    # [IGNORE] The bid's parent block has been imported
    # (MAY be queued until parent is imported)
    if bid.parent_block_root not in store.block_states:
        raise GossipIgnore("bid's parent block post-state is unavailable")

    state = store.block_states[bid.parent_block_root]

    # [IGNORE] The bid's slot is within the parent's proposer lookahead
    if proposal_epoch > get_current_epoch(state) + MIN_SEED_LOOKAHEAD:
        raise GossipIgnore("bid's slot is past the parent's proposer lookahead")

    # [IGNORE] The matching proposer preferences have been seen
    dependent_root = get_shuffling_dependent_root(store, bid.parent_block_root, proposal_epoch)
    prefs_key = (bid.slot, dependent_root)
    if prefs_key not in seen.proposer_preferences:
        raise GossipIgnore("matching proposer preferences have not been seen")

    proposer_preferences = seen.proposer_preferences[prefs_key]

    # [IGNORE] The bid's fee recipient matches the proposer's preference
    if bid.fee_recipient != proposer_preferences.fee_recipient:
        raise GossipIgnore("bid's fee recipient does not match the proposer's preference")

    # [IGNORE] The bid's parent block hash is the hash of a known execution payload
    if bid.parent_block_hash not in seen.execution_payloads:
        raise GossipIgnore("bid's parent block hash is not a known execution payload")

    # [IGNORE] The bid's gas limit is compatible with the proposer's target gas limit
    parent_gas_limit = seen.execution_payloads[bid.parent_block_hash].gas_limit
    if not is_gas_limit_target_compatible(
        parent_gas_limit, bid.gas_limit, proposer_preferences.target_gas_limit
    ):
        raise GossipIgnore("bid's gas limit is not compatible with the proposer's target")

    # [IGNORE] The bid is compatible with the current head branch
    if not is_bid_compatible_with_head(store, bid):
        raise GossipIgnore("bid is not compatible with the current head branch")

    # [REJECT] The bid's previous randao is correct
    if bid.prev_randao != get_randao_mix(state, get_current_epoch(state)):
        raise GossipReject("bid's previous randao is incorrect")

    state = state.copy()
    process_slots(state, bid.slot)

    # [REJECT] The builder index is valid
    if bid.builder_index >= len(state.builders):
        raise GossipReject("builder index out of range")

    builder = state.builders[bid.builder_index]

    # [REJECT] The builder is a payload builder
    if builder.version != PAYLOAD_BUILDER_VERSION:
        raise GossipReject("builder is not a payload builder")

    # [REJECT] The builder is active
    if not is_active_builder(state, bid.builder_index):
        raise GossipReject("builder is not active")

    # [IGNORE] The builder can cover the bid
    if not can_builder_cover_bid(state, bid.builder_index, bid.value):
        raise GossipIgnore("builder cannot cover bid value")

    # [IGNORE] The parent's payload does not try to exit the builder
    if bid.parent_block_hash == state.latest_execution_payload_bid.block_hash:
        envelope = store.payloads[bid.parent_block_root]
        for request in envelope.execution_requests.builder_exits:
            # [Modified in PQ]
            if XMSSPubkey(request.pubkey[16:]) == builder.pubkey:
                if request.source_address == builder.execution_address:
                    raise GossipIgnore("builder may exit")

    # [REJECT] The bid signature is valid
    if not verify_execution_payload_bid_signature(state, signed_execution_payload_bid):
        raise GossipReject("invalid bid signature")

    # Mark this bid as seen and update the highest-value bid for this slot/parent
    seen.execution_payload_bids.add(bid_key)
    seen.best_execution_payload_bid[best_bid_key] = bid.value
```

##### Modified `proposer_preferences`

*Note*: A proposer signs its preferences for a slot at the same leaf, so it must
not sign preferences for the same proposal slot under two different dependent
roots, even though this topic accepts one message per dependent root.

```python
def validate_proposer_preferences_gossip(
    seen: Seen,
    store: Store,
    signed_proposer_preferences: SignedProposerPreferences,
    current_time_ms: Uint64,
) -> None:
    """
    Validate a SignedProposerPreferences for gossip propagation.
    Raises GossipIgnore or GossipReject on validation failure.
    """
    preferences = signed_proposer_preferences.message

    # [IGNORE] These are the first valid preferences seen for this dependent root and slot
    prefs_key = (preferences.proposal_slot, preferences.dependent_root)
    if prefs_key in seen.proposer_preferences:
        raise GossipIgnore("already seen preferences for this dependent root and proposal slot")

    # [IGNORE] The proposal epoch is after the Gloas upgrade
    proposal_epoch = compute_epoch_at_slot(preferences.proposal_slot)
    if proposal_epoch < GLOAS_FORK_EPOCH:
        raise GossipIgnore("proposal epoch is pre-gloas")

    # [IGNORE] The proposal slot has not started yet
    if is_past_slot(store, preferences.proposal_slot, current_time_ms):
        raise GossipIgnore("proposal slot has already started")

    # [IGNORE] The proposer for the proposal slot is known
    lookahead_start_slot = compute_shuffling_lookahead_start_slot(proposal_epoch)
    if is_future_slot(store, lookahead_start_slot, current_time_ms):
        raise GossipIgnore("proposer for the proposal slot is not yet known")

    # [IGNORE] The dependent block has been seen (via gossip or non-gossip sources)
    # (MAY be queued until block is retrieved)
    if preferences.dependent_root not in store.blocks:
        raise GossipIgnore("dependent block has not been seen")

    # [IGNORE] The dependent block passes validation
    if preferences.dependent_root not in store.block_states:
        raise GossipIgnore("dependent block failed validation")

    # [REJECT] The dependent block's slot is not after the shuffling dependent slot
    dependent_slot = compute_shuffling_dependent_slot(proposal_epoch)
    if store.blocks[preferences.dependent_root].slot > dependent_slot:
        raise GossipReject("dependent block is after the shuffling dependent slot")

    # [IGNORE] The dependent block is a possible dependent block for the proposer lookahead
    if not is_valid_dependent_root(store, preferences.dependent_root, dependent_slot):
        raise GossipIgnore("dependent block is not a possible dependent block")

    state = store.block_states[preferences.dependent_root].copy()
    if state.slot < lookahead_start_slot:
        process_slots(state, lookahead_start_slot)

    # [REJECT] The validator is the proposer for the given slot in the proposer lookahead
    lookahead_index = preferences.proposal_slot - lookahead_start_slot
    if state.proposer_lookahead[lookahead_index] != preferences.validator_index:
        raise GossipReject("validator is not the proposer for the given slot")

    # [REJECT] The signature is valid
    validator = state.validators[preferences.validator_index]
    domain = compute_domain(
        DOMAIN_PROPOSER_PREFERENCES,
        compute_fork_version(proposal_epoch),
        state.genesis_validators_root,
    )
    signing_root = compute_signing_root(preferences, domain)
    # [Modified in PQ]
    leaf_index = compute_xmss_leaf_index(
        preferences.proposal_slot, LEAF_OFFSET_PROPOSER_PREFERENCES
    )
    if not xmss.Verify(
        validator.pubkey, leaf_index, signing_root, signed_proposer_preferences.signature
    ):
        raise GossipReject("invalid proposer preferences signature")

    # Mark these preferences as seen
    seen.proposer_preferences[prefs_key] = preferences
```

#### Attestation subnets

##### Modified `beacon_attestation_{subnet_id}`

There are `ATTESTATION_SUBNET_COUNT_PQ` attestation subnets. `Attnets` keeps its
length of `ATTESTATION_SUBNET_COUNT` bits, so `MetaData` and the `attnets` ENR
entry are unchanged, and only the bits of the `ATTESTATION_SUBNET_COUNT_PQ`
subnets may be set.

```python
def validate_beacon_attestation_gossip(
    seen: Seen,
    store: Store,
    attestation: SingleAttestation,
    current_time_ms: Uint64,
    subnet_id: SubnetID,
    block_payload_statuses: dict[Root, PayloadValidationStatus],
) -> None:
    """
    Validate a SingleAttestation for gossip propagation on a subnet.
    Raises GossipIgnore or GossipReject on validation failure.
    """
    data = attestation.data
    committee_index = attestation.committee_index
    attester_index = attestation.attester_index
    target_epoch = data.target.epoch

    # [IGNORE] No other valid attestation seen for this target epoch and validator
    attestation_epoch_key = (target_epoch, attester_index)
    if attestation_epoch_key in seen.attestation_validator_epochs:
        raise GossipIgnore("already seen attestation for this epoch and validator")

    # [REJECT] The attestation's data index is 0 or 1
    if data.index > 1:
        raise GossipReject("attestation data index must be 0 or 1")

    # [IGNORE] The block being voted for has been seen (via gossip or non-gossip sources)
    # (MAY be queued until block is retrieved)
    block_root = data.beacon_block_root
    if block_root not in store.blocks:
        raise GossipIgnore("block being voted for has not been seen")

    # [REJECT] The block being voted for passes validation
    if block_root not in store.block_states:
        raise GossipReject("block being voted for failed validation")

    state = store.block_states[get_head(store).root]

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
    if is_future_slot(store, data.slot, current_time_ms):
        raise GossipIgnore("attestation slot is from a future slot")

    # [IGNORE] The attestation's epoch is either the current or previous epoch
    attestation_epoch = compute_epoch_at_slot(data.slot)
    if not is_current_or_previous_epoch(store, attestation_epoch, current_time_ms):
        raise GossipIgnore("attestation epoch is not current or previous epoch")

    # [REJECT] The attestation's epoch matches its target
    if target_epoch != compute_epoch_at_slot(data.slot):
        raise GossipReject("attestation epoch does not match target epoch")

    # [REJECT] The attester is a member of the committee
    committee = get_beacon_committee(state, data.slot, committee_index)
    if attester_index not in committee:
        raise GossipReject("attester is not a member of the committee")

    # [REJECT] The attestation signature is valid
    attester = state.validators[attester_index]
    domain = get_domain(state, DOMAIN_BEACON_ATTESTER, target_epoch)
    signing_root = compute_signing_root(data, domain)
    # [Modified in PQ]
    leaf_index = compute_xmss_attestation_leaf_index(target_epoch)
    if not xmss.Verify(attester.pubkey, leaf_index, signing_root, attestation.signature):
        raise GossipReject("invalid attestation signature")

    # [REJECT] The attestation's target block is an ancestor of the LMD vote block
    target_checkpoint_block = get_checkpoint_block(store, block_root, target_epoch)
    if target_checkpoint_block != data.target.root:
        raise GossipReject("target block is not an ancestor of LMD vote block")

    # [IGNORE] The current finalized checkpoint is an ancestor of the block
    finalized_epoch = store.finalized_checkpoint.epoch
    finalized_checkpoint_block = get_checkpoint_block(store, block_root, finalized_epoch)
    if finalized_checkpoint_block != store.finalized_checkpoint.root:
        raise GossipIgnore("finalized checkpoint is not an ancestor of block")

    # The attested payload status is consistent with the block's execution payload
    verify_attestation_payload_status(store, data, block_payload_statuses)

    # Mark this attestation as seen
    seen.attestation_validator_epochs.add(attestation_epoch_key)
```

#### Sync committee subnets

Sync committees are removed in PQ, so the `sync_committee_{subnet_id}` topics
are no longer used.
