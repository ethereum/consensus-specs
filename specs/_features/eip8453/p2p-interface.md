# EIP-8453 -- Networking

*Note*: This document is a work-in-progress for researchers and implementers.

<!-- mdformat-toc start --slug=github --no-anchors --maxlevel=6 --minlevel=2 -->

- [Introduction](#introduction)
- [Presets](#presets)
  - [Type-specific SSZ bounds](#type-specific-ssz-bounds)
- [Helpers](#helpers)
  - [Modified `Seen`](#modified-seen)
  - [Modified `compute_fork_version`](#modified-compute_fork_version)
  - [Modified `verify_block_body_operation_limits`](#modified-verify_block_body_operation_limits)
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
    - [Attestation subnets](#attestation-subnets)
      - [Deprecated `beacon_attestation_{subnet_id}`](#deprecated-beacon_attestation_subnet_id)
      - [New `attestation_{subnet_id}`](#new-attestation_subnet_id)
- [The Req/Resp domain](#the-reqresp-domain)
  - [Messages](#messages)
    - [Status v3](#status-v3)
    - [BeaconBlocksByRange v2](#beaconblocksbyrange-v2)
    - [BeaconBlocksByRoot v2](#beaconblocksbyroot-v2)
    - [BeaconBlocksByHead v1](#beaconblocksbyhead-v1)

<!-- mdformat-toc end -->

## Introduction

This document contains the consensus-layer networking specifications for
EIP-8453.

The specification of these changes continues in the same format as the network
specifications of previous upgrades, and assumes them as pre-requisite.

FG attestations replace beacon attestations on new attestation subnets, head
votes are propagated on a new global topic, and the `Status` message carries the
finalized slot instead of the finalized epoch.

*Note*: This specification is built upon [Heze](../../heze/p2p-interface.md).

## Presets

### Type-specific SSZ bounds

`MAX_ATTESTER_SLASHING_SIZE_EIP8453` supersedes `MAX_ATTESTER_SLASHING_SIZE` for
the `attester_slashing` topic, since `IndexedAttestation` is modified in
EIP-8453.

| Name                                 | Value                        |
| ------------------------------------ | ---------------------------- |
| `MAX_ATTESTER_SLASHING_SIZE_EIP8453` | `Uint64(2097538)` (= ~2 MiB) |

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
    # [Modified in EIP8453]
    # Removed `attestation_validator_epochs`
    sync_contribution_aggregator_slots: set[tuple[Slot, ValidatorIndex, Uint64]]
    sync_contribution_data: dict[tuple[Slot, Root, Uint64], set[tuple[bool, ...]]]
    sync_message_validator_slots: set[tuple[Slot, ValidatorIndex, Uint64]]
    bls_to_execution_change_indices: set[ValidatorIndex]
    data_column_sidecar_tuples: set[tuple[Root, ColumnIndex]]
    execution_payloads: dict[Hash32, ExecutionPayload]
    execution_payload_envelopes: set[tuple[Root, BuilderIndex]]
    payload_attestation_validators: set[tuple[Slot, ValidatorIndex]]
    execution_payload_bids: set[tuple[Slot, Hash32, Root, BuilderIndex]]
    best_execution_payload_bid: dict[tuple[Slot, Hash32, Root], Gwei]
    proposer_preferences: dict[tuple[Slot, Root], ProposerPreferences]
    inclusion_list_counts: Counter[tuple[Slot, Root, ValidatorIndex]]
    # [New in EIP8453]
    attestation_validator_rounds: set[tuple[Round, ValidatorIndex]]
    # [New in EIP8453]
    head_vote_validator_slots: set[tuple[Slot, ValidatorIndex]]
```

### Modified `compute_fork_version`

```python
def compute_fork_version(epoch: Epoch) -> Version:
    """
    Return the fork version at the given ``epoch``.
    """
    if epoch >= EIP8453_FORK_EPOCH:
        return EIP8453_FORK_VERSION
    if epoch >= HEZE_FORK_EPOCH:
        return HEZE_FORK_VERSION
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

    # [REJECT] The attestation count is within the limit
    if len(body.attestations) > MAX_ATTESTATIONS_ELECTRA:
        raise GossipReject("too many attestations")

    # [REJECT] The voluntary exit count is within the limit
    if len(body.voluntary_exits) > MAX_VOLUNTARY_EXITS:
        raise GossipReject("too many voluntary exits")

    # [REJECT] The BLS to execution change count is within the limit
    if len(body.bls_to_execution_changes) > MAX_BLS_TO_EXECUTION_CHANGES:
        raise GossipReject("too many bls to execution changes")

    # [REJECT] The payload attestation count is within the limit
    if len(body.payload_attestations) > MAX_PAYLOAD_ATTESTATIONS:
        raise GossipReject("too many payload attestations")

    # [New in EIP8453]
    # [REJECT] The head vote count is within the limit
    if len(body.head_votes) > MAX_HEAD_VOTES:
        raise GossipReject("too many head votes")

    # [New in EIP8453]
    # [REJECT] The head vote support count matches the head vote count
    if len(body.head_vote_support) != len(body.head_votes):
        raise GossipReject("head vote support count does not match head vote count")

    # [New in EIP8453]
    # [REJECT] Each head vote has one support bit per voter
    for index in range(len(body.head_votes)):
        if len(body.head_vote_support[index]) != len(body.head_votes[index].voter_indices):
            raise GossipReject("head vote support bits do not match voters")

    # [New in EIP8453]
    # [REJECT] The legacy attester slashing count is within the limit
    if len(body.legacy_attester_slashings) > MAX_ATTESTER_SLASHINGS_ELECTRA:
        raise GossipReject("too many legacy attester slashings")
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
latest slot of its committee that has started, which fixes its round and epoch.

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

Topics follow the same specification as in prior upgrades. The `beacon_block`
and `attester_slashing` topics are updated with modified types, the
`beacon_aggregate_and_proof` and `beacon_attestation_{subnet_id}` topics are
deprecated, and the `head_vote` and `attestation_{subnet_id}` topics are new:

| Name                      | Message Type                   |
| ------------------------- | ------------------------------ |
| `beacon_block`            | `SignedBeaconBlock` (modified) |
| `attester_slashing`       | `AttesterSlashing` (modified)  |
| `head_vote`               | `HeadVoteMessage`              |
| `attestation_{subnet_id}` | `SingleAttestation` (modified) |

Legacy attester slashings are not propagated on gossip. A proposer includes the
evidence it holds.

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

    # [Modified in EIP8453]
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
    if not bls.Verify(proposer.pubkey, signing_root, signed_beacon_block.signature):
        raise GossipReject("invalid proposer signature")

    # [IGNORE] If the parent block is full, the parent payload is valid
    # (MAY be queued until the parent payload is verified)
    if is_parent_node_full(store, block):
        if not is_payload_verified(store, block.parent_root):
            raise GossipIgnore("parent payload is not verified")

    # [REJECT] The block is from a higher slot than its parent
    if block.slot <= store.blocks[block.parent_root].slot:
        raise GossipReject("block is not from a higher slot than its parent")

    # [Modified in EIP8453]
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

*Note*: The `AttesterSlashing` type is modified to carry FG attestations. The
validation logic is unchanged.

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

    # [REJECT] The head vote's slot is at or after the EIP-8453 fork
    if compute_epoch_at_slot(data.slot) < EIP8453_FORK_EPOCH:
        raise GossipReject("head vote's slot is pre-eip8453")

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
    if not bls.Verify(validator.pubkey, signing_root, head_vote_message.signature):
        raise GossipReject("invalid head vote signature")

    # Mark this head vote as seen
    seen.head_vote_validator_slots.add(head_vote_key)
```

##### New `head_vote_aggregate`

*TODO*: Specify this topic, which propagates aggregated head votes, together
with aggregator selection in the honest validator guide.

##### New `attestation_aggregate`

*TODO*: Specify this topic, which propagates aggregated FG attestations,
together with aggregator selection in the honest validator guide.

#### Attestation subnets

##### Deprecated `beacon_attestation_{subnet_id}`

`beacon_attestation_{subnet_id}` is deprecated.

##### New `attestation_{subnet_id}`

The `attestation_{subnet_id}` topics, where each committee index maps to some
`subnet_id`, are used to propagate FG attestations as `SingleAttestation`. FG
attestations carry neither a slot nor a block root. Each validator may propagate
one attestation per round, in the slot of its attestation committee.

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

    # [IGNORE] The attestation's epoch is the epoch of its committee's slot
    if attestation.epoch != compute_epoch_at_slot(slot):
        raise GossipIgnore("attestation epoch is not the epoch of its committee's slot")

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
    committee = get_attestation_committee(state, attestation.epoch, committee_index)
    if attester_index not in committee:
        raise GossipReject("attester is not a member of the committee")

    # [REJECT] The attestation signature is valid
    attester = state.validators[attester_index]
    domain = get_domain(state, DOMAIN_FINALITY_ATTESTER, attestation.epoch)
    signing_root = compute_signing_root(data, domain)
    if not bls.Verify(attester.pubkey, signing_root, attestation.signature):
        raise GossipReject("invalid attestation signature")

    # Mark this attestation as seen
    seen.attestation_validator_rounds.add(attestation_round_key)
```

## The Req/Resp domain

### Messages

#### Status v3

**Protocol ID:** `/eth2/beacon_chain/req/status/3/`

*[New in EIP8453]*

Request, Response Content:

```
(
  fork_digest: ForkDigest
  finalized_root: Root
  # [Modified in EIP8453]
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

The EIP-8453 fork-digest is introduced to the `context` enum to specify EIP-8453
beacon block type.

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
| `HEZE_FORK_VERSION`      | `heze.SignedBeaconBlock`      |
| `EIP8453_FORK_VERSION`   | `eip8453.SignedBeaconBlock`   |

#### BeaconBlocksByRoot v2

**Protocol ID:** `/eth2/beacon_chain/req/beacon_blocks_by_root/2/`

The EIP-8453 fork-digest is introduced to the `context` enum to specify EIP-8453
beacon block type.

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
| `HEZE_FORK_VERSION`      | `heze.SignedBeaconBlock`      |
| `EIP8453_FORK_VERSION`   | `eip8453.SignedBeaconBlock`   |

#### BeaconBlocksByHead v1

**Protocol ID:** `/eth2/beacon_chain/req/beacon_blocks_by_head/1/`

The EIP-8453 fork-digest is introduced to the `context` enum to specify EIP-8453
beacon block type.

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
| `HEZE_FORK_VERSION`      | `heze.SignedBeaconBlock`      |
| `EIP8453_FORK_VERSION`   | `eip8453.SignedBeaconBlock`   |
