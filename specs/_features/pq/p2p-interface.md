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
  - [Modified `Seen`](#modified-seen)
  - [Modified `compute_fork_version`](#modified-compute_fork_version)
  - [Modified `verify_block_body_operation_limits`](#modified-verify_block_body_operation_limits)
  - [Modified `verify_execution_requests_limits`](#modified-verify_execution_requests_limits)
  - [Modified `compute_attestation_subnet_prefix_bits`](#modified-compute_attestation_subnet_prefix_bits)
  - [Modified `compute_subscribed_subnet`](#modified-compute_subscribed_subnet)
  - [New `is_finalized_ancestor`](#new-is_finalized_ancestor)
  - [New `get_latest_attestation_committee_slot`](#new-get_latest_attestation_committee_slot)
  - [New `verify_head_vote_payload_status`](#new-verify_head_vote_payload_status)
- [The gossip domain: gossipsub](#the-gossip-domain-gossipsub)
  - [Topics and messages](#topics-and-messages)
    - [Global topics](#global-topics)
      - [Modified `beacon_block`](#modified-beacon_block)
      - [Deprecated `beacon_aggregate_and_proof`](#deprecated-beacon_aggregate_and_proof)
      - [Modified `attester_slashing`](#modified-attester_slashing)
      - [New `head_vote`](#new-head_vote)
      - [New `head_vote_aggregate`](#new-head_vote_aggregate)
      - [New `attestation_aggregate`](#new-attestation_aggregate)
      - [Removed `voluntary_exit`](#removed-voluntary_exit)
      - [Modified `proposer_slashing`](#modified-proposer_slashing)
      - [Removed `sync_committee_contribution_and_proof`](#removed-sync_committee_contribution_and_proof)
      - [Modified `payload_attestation_message`](#modified-payload_attestation_message)
      - [Modified `execution_payload_bid`](#modified-execution_payload_bid)
      - [Modified `proposer_preferences`](#modified-proposer_preferences)
    - [Attestation subnets](#attestation-subnets)
      - [Deprecated `beacon_attestation_{subnet_id}`](#deprecated-beacon_attestation_subnet_id)
      - [New `attestation_{subnet_id}`](#new-attestation_subnet_id)
    - [Sync committee subnets](#sync-committee-subnets)
- [The Req/Resp domain](#the-reqresp-domain)
  - [Messages](#messages)
    - [Status v3](#status-v3)
    - [BeaconBlocksByRange v2](#beaconblocksbyrange-v2)
    - [BeaconBlocksByRoot v2](#beaconblocksbyroot-v2)
    - [BeaconBlocksByHead v1](#beaconblocksbyhead-v1)

<!-- mdformat-toc end -->

## Introduction

This document contains the consensus-layer networking specifications for PQ.

The specification of these changes continues in the same format as the network
specifications of previous upgrades, and assumes them as pre-requisite.

Sync committees are removed in PQ, and with them the light client protocol, so
the light client topics and request/response methods are no longer used.

FG attestations replace beacon attestations on new attestation subnets, head
votes are propagated on a new global topic, and the `Status` message carries the
finalized slot instead of the finalized epoch.

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
which were sized for BLS signatures and Casper FFG attestations. The
`beacon_aggregate_and_proof` topic is deprecated, so
`MAX_SIGNED_AGGREGATE_AND_PROOF_SIZE` has no successor.

| Name                                       | Value                         |
| ------------------------------------------ | ----------------------------- |
| `MAX_ATTESTER_SLASHING_SIZE_PQ`            | `Uint64(4194506)` (= ~4 MiB)  |
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

### Modified `Seen`

```python
@dataclass
class Seen:
    proposer_slots: set[tuple[Slot, ValidatorIndex]]
    aggregator_epochs: set[tuple[Epoch, ValidatorIndex]]
    aggregate_data_roots: dict[tuple[Root, CommitteeIndex], set[tuple[bool, ...]]]
    voluntary_exit_indices: set[ValidatorIndex]
    proposer_slashing_indices: set[ValidatorIndex]
    attester_slashing_indices: set[ValidatorIndex]
    # [Modified in PQ:EIP8453]
    # Removed `attestation_validator_epochs`
    sync_contribution_aggregator_slots: set[tuple[Slot, ValidatorIndex, Uint64]]
    sync_contribution_data: dict[tuple[Slot, Root, Uint64], set[tuple[bool, ...]]]
    sync_message_validator_slots: set[tuple[Slot, ValidatorIndex, Uint64]]
    bls_to_execution_change_indices: set[ValidatorIndex]
    data_column_sidecar_tuples: set[tuple[Root, ColumnIndex]]
    execution_payloads: dict[Hash32, ExecutionPayload]
    execution_payload_envelopes: set[tuple[Root, BuilderIndex]]
    payload_attestation_validators: set[tuple[Slot, ValidatorIndex]]
    execution_payload_bid_counts: Counter[tuple[Slot, Hash32, Root, BuilderIndex]]
    best_execution_payload_bid: dict[tuple[Slot, Hash32, Root], Gwei]
    proposer_preferences: dict[tuple[Slot, Root], ProposerPreferences]
    # [New in PQ:EIP8453]
    attestation_validator_rounds: set[tuple[Round, ValidatorIndex]]
    # [New in PQ:EIP8453]
    head_vote_validator_slots: set[tuple[Slot, ValidatorIndex]]
```

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

    # [Modified in PQ]
    # Removed the voluntary exit limit

    # [Modified in PQ]
    # Removed the BLS to execution change limit

    # [Modified in PQ]
    # Removed the payload attestation limit

    # [New in PQ:EIP8453]
    # [REJECT] The head vote count is within the limit
    if len(body.head_votes) > MAX_HEAD_VOTES:
        raise GossipReject("too many head votes")

    # [New in PQ:EIP8453]
    # [REJECT] The head vote support count matches the head vote count
    if len(body.head_vote_support) != len(body.head_votes):
        raise GossipReject("head vote support count does not match head vote count")

    # [New in PQ:EIP8453]
    # [REJECT] Each head vote has one support bit per voter
    for index in range(len(body.head_votes)):
        if len(body.head_vote_support[index]) != len(body.head_votes[index].voter_indices):
            raise GossipReject("head vote support bits do not match voters")
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

    # [New in PQ:EIP8205]
    # [REJECT] The validator preregistration request count is within the limit
    if (
        len(execution_requests.validator_preregistrations)
        > MAX_VALIDATOR_PREREGISTRATION_REQUESTS_PER_PAYLOAD
    ):
        raise GossipReject("too many validator preregistration requests")

    # [New in PQ:EIP8205]
    # [REJECT] The builder preregistration request count is within the limit
    if (
        len(execution_requests.builder_preregistrations)
        > MAX_BUILDER_PREREGISTRATION_REQUESTS_PER_PAYLOAD
    ):
        raise GossipReject("too many builder preregistration requests")

    # [New in PQ]
    # [REJECT] The voluntary exit request count is within the limit
    if len(execution_requests.voluntary_exits) > MAX_VOLUNTARY_EXIT_REQUESTS_PER_PAYLOAD:
        raise GossipReject("too many voluntary exit requests")
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

### New `is_finalized_ancestor`

```python
def is_finalized_ancestor(store: Store, state: BeaconState, root: Root) -> bool:
    """
    Check if the finalized block of ``state`` is an ancestor of ``root``.
    """
    node = ForkChoiceNode(root=root, payload_status=PAYLOAD_STATUS_PENDING)
    return get_ancestor(store, node, state.finalized_slot).root == state.finalized_checkpoint.root
```

### New `get_latest_attestation_committee_slot`

*Note*: FG attestations carry no slot. On gossip, an attestation belongs to the
latest slot of its committee that has started, which fixes its round.

```python
def get_latest_attestation_committee_slot(
    store: Store, committee_index: CommitteeIndex, current_time_ms: Uint64
) -> Slot:
    """
    Return the latest slot of the attestation committee at ``committee_index``
    that has started, allowing for ``MAXIMUM_GOSSIP_CLOCK_DISPARITY``.
    """
    current_time_with_disparity_ms = current_time_ms + MAXIMUM_GOSSIP_CLOCK_DISPARITY
    current_slot = compute_slot_at_time_ms(store.genesis_time_ms, current_time_with_disparity_ms)
    round = compute_round_at_slot(current_slot)
    slot = compute_attestation_committee_slot(round, committee_index)
    if slot > current_slot:
        return compute_attestation_committee_slot(round - 1, committee_index)
    return slot
```

### New `verify_head_vote_payload_status`

```python
def verify_head_vote_payload_status(
    store: Store,
    data: HeadVoteData,
    block_payload_statuses: dict[Root, PayloadValidationStatus],
) -> None:
    """
    Verify that the payload status of ``data`` is consistent with its block.
    Raises GossipIgnore or GossipReject on validation failure.
    """
    block_root = data.beacon_block_root
    block = store.blocks[block_root]

    # [REJECT] A vote for the block of its own slot has a pending payload status
    if block.slot == data.slot and data.payload_status != PAYLOAD_STATUS_PENDING:
        raise GossipReject("same-slot head vote must have a pending payload status")

    # [REJECT] A vote for an earlier block has an empty or full payload status
    is_payload_decision = data.payload_status in (PAYLOAD_STATUS_EMPTY, PAYLOAD_STATUS_FULL)
    if block.slot < data.slot and not is_payload_decision:
        raise GossipReject("head vote for an earlier block must be empty or full")

    if data.payload_status != PAYLOAD_STATUS_FULL:
        return

    # [IGNORE] The corresponding execution payload envelope has been seen and verified
    # (MAY queue head votes for processing once the payload is retrieved and
    # SHOULD request the payload envelope via ExecutionPayloadEnvelopesByRoot
    # using data.beacon_block_root)
    if not is_payload_verified(store, block_root):
        raise GossipIgnore("execution payload envelope has not been seen")

    validation_status = block_payload_statuses.get(block_root, PAYLOAD_STATUS_NOT_VALIDATED)

    # [IGNORE] The voted execution payload is not optimistic
    if validation_status == PAYLOAD_STATUS_NOT_VALIDATED:
        raise GossipIgnore("voted payload is optimistic")

    # [REJECT] The voted execution payload is processed and invalid
    if validation_status == PAYLOAD_STATUS_INVALIDATED:
        raise GossipReject("voted payload is invalid")
```

## The gossip domain: gossipsub

### Topics and messages

Topics follow the same specification as in prior upgrades. Every topic whose
message holds a validator or builder signature is updated to the modified type,
which carries an XMSS signature instead. The `bls_to_execution_change` topic is
removed, because `BLSToExecutionChange` is disabled. The `voluntary_exit` topic
is removed, because voluntary exits are execution layer requests.

The `beacon_block` and `attester_slashing` topics are updated with modified
types, the `beacon_aggregate_and_proof` and `beacon_attestation_{subnet_id}`
topics are deprecated, and the `head_vote` and `attestation_{subnet_id}` topics
are new:

| Name                      | Message Type                   |
| ------------------------- | ------------------------------ |
| `beacon_block`            | `SignedBeaconBlock` (modified) |
| `attester_slashing`       | `AttesterSlashing` (modified)  |
| `head_vote`               | `HeadVoteMessage`              |
| `attestation_{subnet_id}` | `SingleAttestation` (modified) |

#### Global topics

##### Modified `beacon_block`

*Note*: This function is modified to read the finalized block from the finality
gadget, which finalizes blocks at heights rather than epoch checkpoints.

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

    state = store.block_states[get_head(store).root]

    # [Modified in PQ:EIP8453]
    # [IGNORE] The block is from a slot greater than the latest finalized slot
    # (MAY choose to validate and store such blocks for additional purposes
    # -- e.g. slashing detection, archive nodes, etc)
    if block.slot <= state.finalized_slot:
        raise GossipIgnore("block is from a finalized slot")

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

    # [Modified in PQ:EIP8453]
    # [REJECT] The finalized block is an ancestor of the block
    if not is_finalized_ancestor(store, state, block.parent_root):
        raise GossipReject("finalized block is not an ancestor of block")

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

##### Deprecated `beacon_aggregate_and_proof`

`beacon_aggregate_and_proof` is deprecated.

##### Modified `attester_slashing`

*Note*: The `AttesterSlashing` type is modified to carry FG attestations, each
with a `proof` of its attesters' signatures in place of an aggregate signature.
The validation logic is unchanged. `MAX_ATTESTER_SLASHING_SIZE_PQ` supersedes
`MAX_ATTESTER_SLASHING_SIZE` for this topic.

##### New `head_vote`

This topic is used to propagate head votes as `HeadVoteMessage`.

```python
def validate_head_vote_gossip(
    seen: Seen,
    store: Store,
    head_vote_message: HeadVoteMessage,
    current_time_ms: Uint64,
    block_payload_statuses: dict[Root, PayloadValidationStatus],
) -> None:
    """
    Validate a HeadVoteMessage for gossip propagation.
    Raises GossipIgnore or GossipReject on validation failure.
    """
    data = head_vote_message.data
    validator_index = head_vote_message.validator_index

    # [REJECT] The head vote's slot is at or after the PQ fork
    if compute_epoch_at_slot(data.slot) < PQ_FORK_EPOCH:
        raise GossipReject("head vote's slot is pre-pq")

    # [IGNORE] This is the first valid head vote from this validator for the slot
    head_vote_key = (data.slot, validator_index)
    if head_vote_key in seen.head_vote_validator_slots:
        raise GossipIgnore("already seen head vote from this validator for this slot")

    # [IGNORE] The head vote is for the current slot
    if not is_current_slot(store, data.slot, current_time_ms):
        raise GossipIgnore("head vote is not for the current slot")

    # [IGNORE] The block being voted for has been seen (via gossip or non-gossip sources)
    # (MAY be queued until block is retrieved)
    block_root = data.beacon_block_root
    if block_root not in store.blocks:
        raise GossipIgnore("block being voted for has not been seen")

    # [REJECT] The block being voted for passes validation
    if block_root not in store.block_states:
        raise GossipReject("block being voted for failed validation")

    # [REJECT] The block being voted for is not from a later slot than the head vote
    if store.blocks[block_root].slot > data.slot:
        raise GossipReject("block being voted for is from a later slot")

    state = store.block_states[get_head(store).root]

    # [IGNORE] The finalized block is an ancestor of the block being voted for
    if not is_finalized_ancestor(store, state, block_root):
        raise GossipIgnore("finalized block is not an ancestor of the block being voted for")

    # The payload status is consistent with the block being voted for
    verify_head_vote_payload_status(store, data, block_payload_statuses)

    # [REJECT] The validator is a member of the head vote committee
    if validator_index not in get_head_vote_committee(state, data.slot):
        raise GossipReject("validator is not in the head vote committee")

    # [REJECT] The signature is valid
    validator = state.validators[validator_index]
    domain = get_domain(state, DOMAIN_HEAD_VOTE, compute_epoch_at_slot(data.slot))
    signing_root = compute_signing_root(data, domain)
    leaf_index = compute_xmss_leaf_index(data.slot, LEAF_OFFSET_HEAD_VOTE)
    if not xmss.Verify(validator.pubkey, leaf_index, signing_root, head_vote_message.signature):
        raise GossipReject("invalid head vote signature")

    # Mark this head vote as seen
    seen.head_vote_validator_slots.add(head_vote_key)
```

##### New `head_vote_aggregate`

*TODO*: Specify this topic, which propagates aggregated head votes, together
with aggregator selection in the honest validator guide.

*TODO*: Specify the message of this topic. A head vote in a block carries no
signature, so an aggregate on the wire must carry a STARK `proof` of the
signatures of its voters, which the proposer merges into the block's `proof`.

##### New `attestation_aggregate`

*TODO*: Specify this topic, which propagates aggregated FG attestations,
together with aggregator selection in the honest validator guide.

*TODO*: Specify the message of this topic. An attestation carries no signature,
so an aggregate on the wire must carry a STARK `proof` of the signatures of its
attesters, which the proposer merges into the block's `proof`.

##### Removed `voluntary_exit`

Voluntary exits are execution layer requests in PQ, so this topic is no longer
used.

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

    # [IGNORE] The builder has not reached its bid limit for this slot and parent
    bid_key = (bid.slot, bid.parent_block_hash, bid.parent_block_root, bid.builder_index)
    bid_limit = get_builder_bid_limit(state, bid.builder_index)
    if seen.execution_payload_bid_counts[bid_key] >= bid_limit:
        raise GossipIgnore("builder has reached its bid limit for this slot and parent")

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

    # Count this bid and update the highest-value bid for this slot/parent
    seen.execution_payload_bid_counts[bid_key] += 1
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

##### Deprecated `beacon_attestation_{subnet_id}`

`beacon_attestation_{subnet_id}` is deprecated.

##### New `attestation_{subnet_id}`

The `attestation_{subnet_id}` topics, where each committee index maps to some
`subnet_id`, are used to propagate FG attestations as `SingleAttestation`. FG
attestations carry neither a slot nor a block root. Each validator may propagate
one attestation per round, in the slot of its attestation committee.

There are `ATTESTATION_SUBNET_COUNT_PQ` attestation subnets. `Attnets` keeps its
length of `ATTESTATION_SUBNET_COUNT` bits, so `MetaData` and the `attnets` ENR
entry are unchanged, and only the bits of the `ATTESTATION_SUBNET_COUNT_PQ`
subnets may be set.

```python
def validate_attestation_gossip(
    seen: Seen,
    store: Store,
    attestation: SingleAttestation,
    current_time_ms: Uint64,
    subnet_id: SubnetID,
) -> None:
    """
    Validate a SingleAttestation for gossip propagation on a subnet.
    Raises GossipIgnore or GossipReject on validation failure.
    """
    data = attestation.data
    committee_index = attestation.committee_index
    attester_index = attestation.attester_index

    # [REJECT] The committee index is within the expected range
    if committee_index >= ATTESTATION_COMMITTEES_PER_ROUND:
        raise GossipReject("committee index out of range")

    # [REJECT] The attestation is for the correct subnet
    if compute_subnet_for_attestation(committee_index) != subnet_id:
        raise GossipReject("attestation is for wrong subnet")

    slot = get_latest_attestation_committee_slot(store, committee_index, current_time_ms)

    # [IGNORE] No other valid attestation seen for this round and validator
    attestation_round_key = (compute_round_at_slot(slot), attester_index)
    if attestation_round_key in seen.attestation_validator_rounds:
        raise GossipIgnore("already seen attestation for this round and validator")

    # [IGNORE] The attestation's round is the round of its committee's slot
    if attestation.round != compute_round_at_slot(slot):
        raise GossipIgnore("attestation round is not the round of its committee's slot")

    # [REJECT] The attestation data is well formed
    if not is_well_formed_attestation_data(data):
        raise GossipReject("attestation data is not well formed")

    # [IGNORE] The target block has been seen (via gossip or non-gossip sources)
    # (MAY be queued until block is retrieved)
    if data.target.root not in store.blocks:
        raise GossipIgnore("target block has not been seen")

    # [REJECT] The target block passes validation
    if data.target.root not in store.block_states:
        raise GossipReject("target block failed validation")

    state = store.block_states[get_head(store).root]

    # [IGNORE] The finalized block is an ancestor of the target block
    if not is_finalized_ancestor(store, state, data.target.root):
        raise GossipIgnore("finalized block is not an ancestor of the target block")

    # [REJECT] The attester is a member of the committee
    epoch = compute_epoch_at_round(attestation.round)
    committee = get_attestation_committee(state, epoch, committee_index)
    if attester_index not in committee:
        raise GossipReject("attester is not a member of the committee")

    # [REJECT] The attestation signature is valid
    attester = state.validators[attester_index]
    domain = get_domain(state, DOMAIN_FINALITY_ATTESTER, epoch)
    signing_root = compute_signing_root(data, domain)
    leaf_index = compute_xmss_attestation_leaf_index(attestation.round)
    if not xmss.Verify(attester.pubkey, leaf_index, signing_root, attestation.signature):
        raise GossipReject("invalid attestation signature")

    # Mark this attestation as seen
    seen.attestation_validator_rounds.add(attestation_round_key)
```

#### Sync committee subnets

Sync committees are removed in PQ, so the `sync_committee_{subnet_id}` topics
are no longer used.

## The Req/Resp domain

### Messages

#### Status v3

**Protocol ID:** `/eth2/beacon_chain/req/status/3/`

*[New in PQ:EIP8453]*

Request, Response Content:

```
(
  fork_digest: ForkDigest
  finalized_root: Root
  # [Modified in PQ:EIP8453]
  finalized_slot: Slot
  head_root: Root
  head_slot: Slot
  earliest_available_slot: Slot
)
```

The finality gadget finalizes blocks at heights, so the finalized block need not
be the first block of an epoch. `finalized_slot` replaces `finalized_epoch` so
that peers can compare finalized blocks directly.

As seen by the client at the time of sending the message:

- `finalized_root`: `state.finalized_checkpoint.root`, where `state` is the
  post-state of the node's head.
- `finalized_slot`: `state.finalized_slot`.

The remaining fields are unchanged from Status v2. The disconnect conditions of
Status v1 apply, with a peer's finalized block checked against the latest block
at or before `finalized_slot` in the client's chain.

Once the handshake completes, the client with the lower `finalized_slot` or
`head_slot` (if the clients have equal `finalized_slot`s) SHOULD request beacon
blocks from its counterparty via the `BeaconBlocksByRange` request.

#### BeaconBlocksByRange v2

**Protocol ID:** `/eth2/beacon_chain/req/beacon_blocks_by_range/2/`

The PQ fork-digest is introduced to the `context` enum to specify PQ beacon
block type.

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
| `EIP8483_FORK_VERSION`   | `eip8483.SignedBeaconBlock`   |
| `PQ_FORK_VERSION`        | `pq.SignedBeaconBlock`        |

#### BeaconBlocksByRoot v2

**Protocol ID:** `/eth2/beacon_chain/req/beacon_blocks_by_root/2/`

The PQ fork-digest is introduced to the `context` enum to specify PQ beacon
block type.

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
| `EIP8483_FORK_VERSION`   | `eip8483.SignedBeaconBlock`   |
| `PQ_FORK_VERSION`        | `pq.SignedBeaconBlock`        |

#### BeaconBlocksByHead v1

**Protocol ID:** `/eth2/beacon_chain/req/beacon_blocks_by_head/1/`

The PQ fork-digest is introduced to the `context` enum to specify PQ beacon
block type.

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
| `EIP8483_FORK_VERSION`   | `eip8483.SignedBeaconBlock`   |
| `PQ_FORK_VERSION`        | `pq.SignedBeaconBlock`        |
