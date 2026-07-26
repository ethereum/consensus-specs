# Gloas -- Honest Validator

*Note*: This document is a work-in-progress for researchers and implementers.

<!-- mdformat-toc start --slug=github --no-anchors --maxlevel=6 --minlevel=2 -->

- [Introduction](#introduction)
- [Configuration](#configuration)
  - [Time parameters](#time-parameters)
- [Validator assignment](#validator-assignment)
  - [Payload timeliness committee](#payload-timeliness-committee)
  - [Lookahead](#lookahead)
- [Beacon chain responsibilities](#beacon-chain-responsibilities)
  - [Attestation](#attestation)
  - [Sync Committee participations](#sync-committee-participations)
  - [Block and sidecar proposal](#block-and-sidecar-proposal)
    - [Broadcasting `SignedProposerPreferences`](#broadcasting-signedproposerpreferences)
    - [Constructing the `BeaconBlockBody`](#constructing-the-beaconblockbody)
      - [Signed execution payload bid](#signed-execution-payload-bid)
      - [Payload attestations](#payload-attestations)
      - [Parent execution requests](#parent-execution-requests)
      - [Execution requests](#execution-requests)
      - [ExecutionPayload](#executionpayload)
      - [Voluntary exits](#voluntary-exits)
  - [Payload timeliness attestation](#payload-timeliness-attestation)
    - [Constructing the `PayloadAttestationMessage`](#constructing-the-payloadattestationmessage)
- [Modified functions](#modified-functions)
  - [Modified `get_data_column_sidecars_from_column_sidecar`](#modified-get_data_column_sidecars_from_column_sidecar)

<!-- mdformat-toc end -->

## Introduction

This document represents the changes to be made in the code of an "honest
validator" to implement Gloas.

## Configuration

### Time parameters

| Name                          | Value          | Unit         | Duration                  |
| ----------------------------- | -------------- | ------------ | ------------------------- |
| `ATTESTATION_DUE_BPS_GLOAS`   | `Uint64(2500)` | basis points | 25% of `SLOT_DURATION_MS` |
| `AGGREGATE_DUE_BPS_GLOAS`     | `Uint64(5000)` | basis points | 50% of `SLOT_DURATION_MS` |
| `SYNC_MESSAGE_DUE_BPS_GLOAS`  | `Uint64(2500)` | basis points | 25% of `SLOT_DURATION_MS` |
| `CONTRIBUTION_DUE_BPS_GLOAS`  | `Uint64(5000)` | basis points | 50% of `SLOT_DURATION_MS` |
| `PAYLOAD_DUE_BPS`             | `Uint64(5000)` | basis points | 50% of `SLOT_DURATION_MS` |
| `PAYLOAD_ATTESTATION_DUE_BPS` | `Uint64(7500)` | basis points | 75% of `SLOT_DURATION_MS` |

## Validator assignment

### Payload timeliness committee

A validator may be a member of the new Payload Timeliness Committee (PTC) for a
given slot. To check for PTC assignments, use
`get_ptc_assignment(state, epoch, validator_index)` where
`epoch <= get_current_epoch(state) + MIN_SEED_LOOKAHEAD`, as PTC committee
selection is only stable within the context of the current and next epochs in
the lookahead.

```python
def get_ptc_assignment(
    state: BeaconState, epoch: Epoch, validator_index: ValidatorIndex
) -> Optional[Slot]:
    """
    Returns the slot during the requested epoch in which the validator with
    index ``validator_index`` is a member of the PTC. Returns None if no
    assignment is found.
    """
    max_epoch = Epoch(get_current_epoch(state) + MIN_SEED_LOOKAHEAD)
    assert epoch <= max_epoch

    start_slot = compute_start_slot_at_epoch(epoch)
    for slot in range(start_slot, start_slot + SLOTS_PER_EPOCH):
        if validator_index in get_ptc(state, Slot(slot)):
            return Slot(slot)
    return None
```

### Lookahead

`get_ptc_assignment` should be called at the start of each epoch to get the
assignment for the next epoch (`current_epoch + 1`). A validator should plan for
future assignments by noting their assigned PTC slot.

## Beacon chain responsibilities

All validator responsibilities remain unchanged other than the following:

- Proposers are no longer required to broadcast `DataColumnSidecar` objects, as
  this becomes a builder's duty.
- Some attesters are selected per slot to become PTC members, these validators
  must broadcast `PayloadAttestationMessage` objects during the assigned slot
  before the deadline of `get_payload_attestation_due_ms()` milliseconds into
  the slot.

### Attestation

The attestation deadline is changed with `ATTESTATION_DUE_BPS_GLOAS`. Moreover,
the `attestation.data.index` field is now used to signal the payload status of
the block being attested to (`attestation.data.beacon_block_root`). With the
alias `data = attestation.data`, the validator should set this field as follows:

- If `block.slot == current_slot` (i.e., `data.slot`), then always set
  `data.index = 0`.
- Otherwise, set `data.index` based on the payload status in the validator's
  fork-choice:
  - Set `data.index = 0` to signal that the payload is not present in the
    canonical chain (payload status is `EMPTY` in the fork-choice).
  - Set `data.index = 1` to signal that the payload is present in the canonical
    chain (payload status is `FULL` in the fork-choice).

### Sync Committee participations

Sync committee duties are not changed for validators, however the submission
deadline is changed with `SYNC_MESSAGE_DUE_BPS_GLOAS`.

### Block and sidecar proposal

Validators are still expected to propose `SignedBeaconBlock` at the beginning of
any slot during which `is_proposer(state, validator_index)` returns `True`. The
mechanism to prepare this beacon block and related sidecars differs from
previous forks as follows

#### Broadcasting `SignedProposerPreferences`

A validator MAY broadcast `SignedProposerPreferences` messages to the
`proposer_preferences` gossip topic for each slot returned by
`get_upcoming_proposal_slots(state, validator_index)`. These include any future
proposal slots within the proposer lookahead, i.e. the current epoch up to
`MIN_SEED_LOOKAHEAD` epochs ahead. This allows builders to construct execution
payloads with the validator's preferred `fee_recipient` and `target_gas_limit`.
If a validator does not broadcast a `SignedProposerPreferences` message, this
implies that the validator will not accept any trustless bids for that slot.

```python
def get_upcoming_proposal_slots(
    state: BeaconState, validator_index: ValidatorIndex
) -> Sequence[Slot]:
    """
    Get the future slots within the proposer lookahead for which
    ``validator_index`` is proposing.
    """
    current_epoch_start_slot = compute_start_slot_at_epoch(get_current_epoch(state))
    upcoming_proposal_slots = []
    for offset, proposer_index in enumerate(state.proposer_lookahead):
        slot = Slot(current_epoch_start_slot + offset)
        if slot <= state.slot:
            continue
        if validator_index == proposer_index:
            upcoming_proposal_slots.append(slot)
    return upcoming_proposal_slots
```

A validator constructs each `SignedProposerPreferences` with
`get_signed_proposer_preferences` for each `proposal_slot` in
`get_upcoming_proposal_slots(state, validator_index)`. Let `head_root` be the
validator's current head root, `fee_recipient` be the execution address where
the validator wishes to receive the builder payment, and `target_gas_limit` be
the validator's preferred gas limit for the execution payload.

```python
def get_signed_proposer_preferences(
    store: Store,
    state: BeaconState,
    head_root: Root,
    proposal_slot: Slot,
    validator_index: ValidatorIndex,
    fee_recipient: ExecutionAddress,
    target_gas_limit: Uint64,
    privkey: int,
) -> SignedProposerPreferences:
    proposal_epoch = compute_epoch_at_slot(proposal_slot)
    dependent_root = get_shuffling_dependent_root(store, head_root, proposal_epoch)
    preferences = ProposerPreferences(
        dependent_root=dependent_root,
        proposal_slot=proposal_slot,
        validator_index=validator_index,
        fee_recipient=fee_recipient,
        target_gas_limit=target_gas_limit,
    )
    domain = get_domain(state, DOMAIN_PROPOSER_PREFERENCES, proposal_epoch)
    signing_root = compute_signing_root(preferences, domain)
    signature = bls.Sign(privkey, signing_root)
    return SignedProposerPreferences(message=preferences, signature=signature)
```

#### Constructing the `BeaconBlockBody`

Let `head = get_head(store)`. A proposer may set
`head = get_proposer_head(store, head, slot)` if proposer re-orgs are
implemented and enabled. Let `head` be the parent node the proposer builds on,
from which `state` is derived.

##### Signed execution payload bid

To obtain `signed_execution_payload_bid`, a block proposer building a block on
top of a `state` MUST take the following actions in order to construct the
`signed_execution_payload_bid` field in `BeaconBlockBody`:

- Listen to the `execution_payload_bid` gossip global topic and save an accepted
  `signed_execution_payload_bid` from a builder. The block proposer MAY obtain
  these signed messages by other off-protocol means.
- The `signed_execution_payload_bid` MUST satisfy the verification conditions
  found in `process_execution_payload_bid` with the alias
  `bid = signed_execution_payload_bid.message`, that is:
  - For external builders, the signature MUST be valid.
  - For self-builds, set `bid.builder_index` to `BUILDER_INDEX_SELF_BUILD`.
  - For self-builds, the signature MUST be `bls.G2_POINT_AT_INFINITY` and the
    `bid.value` MUST be zero.
  - The builder balance can cover the `bid.value`.
  - The `bid.slot` is for the proposal block slot.
  - The `bid.parent_block_hash` equals
    `state.latest_execution_payload_bid.block_hash` if
    `should_build_on_full(store, head)` is true, otherwise
    `state.latest_execution_payload_bid.parent_block_hash`.
  - The `bid.parent_block_root` equals the current block's `parent_root`.
  - The `bid.prev_randao` equals
    `get_randao_mix(state, get_current_epoch(state))`.
- Select one bid and set
  `block.body.signed_execution_payload_bid = signed_execution_payload_bid`.

*Note*: The execution address encoded in the `fee_recipient` field in the
`signed_execution_payload_bid.message` will receive the builder payment.

##### Payload attestations

Up to `MAX_PAYLOAD_ATTESTATIONS` aggregate payload attestations can be included
in the block. The block proposer MUST take the following actions in order to
construct the `payload_attestations` field in `BeaconBlockBody`:

- Listen to the `payload_attestation_message` gossip global topic.
- Added payload attestations MUST satisfy the verification conditions found in
  payload attestation gossip validation and payload attestation processing.
  - The `data.beacon_block_root` corresponds to `block.parent_root`.
  - The slot of the parent block is exactly one slot before the proposing slot.
  - The signature of the payload attestation data message verifies correctly.
- The proposer MUST aggregate all payload attestations with the same data into a
  given `PayloadAttestation` object. For this the proposer needs to fill the
  `aggregation_bits` field by using the relative position of the validator
  indices with respect to the PTC that is obtained from
  `get_ptc(state, Slot(block_slot - 1))`.

##### Parent execution requests

The `parent_execution_requests` field contains the execution requests from the
parent's execution payload. The proposer constructs this field as follows:

- If the parent block is pre-Gloas (first Gloas block), set
  `parent_execution_requests` to an empty `ExecutionRequests()`.
- If `should_build_on_full(store, head)` returns `True` (the proposer is
  building on the parent's full payload), set `parent_execution_requests` to
  `store.payloads[head.root].execution_requests`.
- Otherwise (the proposer is building on the parent's empty variant), set
  `parent_execution_requests` to an empty `ExecutionRequests()`.

##### Execution requests

*Note*: The function `get_execution_requests` is modified to parse the builder
deposit requests and builder exit requests.

```python
def get_execution_requests(execution_requests_list: Sequence[bytes]) -> ExecutionRequests:
    deposits = []
    withdrawals = []
    consolidations = []
    # [New in Gloas:EIP8282]
    builder_deposits = []
    # [New in Gloas:EIP8282]
    builder_exits = []

    request_types = [
        DEPOSIT_REQUEST_TYPE,
        WITHDRAWAL_REQUEST_TYPE,
        CONSOLIDATION_REQUEST_TYPE,
        # [New in Gloas:EIP8282]
        BUILDER_DEPOSIT_REQUEST_TYPE,
        # [New in Gloas:EIP8282]
        BUILDER_EXIT_REQUEST_TYPE,
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
            deposits = ssz_deserialize(DepositRequests, request_data)
        elif request_type == WITHDRAWAL_REQUEST_TYPE:
            withdrawals = ssz_deserialize(WithdrawalRequests, request_data)
        elif request_type == CONSOLIDATION_REQUEST_TYPE:
            consolidations = ssz_deserialize(ConsolidationRequests, request_data)
        # [New in Gloas:EIP8282]
        elif request_type == BUILDER_DEPOSIT_REQUEST_TYPE:
            builder_deposits = ssz_deserialize(BuilderDepositRequests, request_data)
        # [New in Gloas:EIP8282]
        elif request_type == BUILDER_EXIT_REQUEST_TYPE:
            builder_exits = ssz_deserialize(BuilderExitRequests, request_data)

    return ExecutionRequests(
        deposits=deposits,
        withdrawals=withdrawals,
        consolidations=consolidations,
        # [New in Gloas:EIP8282]
        builder_deposits=builder_deposits,
        # [New in Gloas:EIP8282]
        builder_exits=builder_exits,
    )
```

##### ExecutionPayload

*Note*: `prepare_execution_payload` is modified to build on the parent's full
payload or its empty variant, as decided by `should_build_on_full(store, head)`,
which determines the withdrawals source and the execution head for the new
payload. When building on a full parent, `apply_parent_execution_payload` is
called so that withdrawals are computed against the post-processing state.

```python
def prepare_execution_payload(
    # [New in Gloas:EIP7732]
    store: Store,
    # [New in Gloas:EIP7732]
    head: ForkChoiceNode,
    state: BeaconState,
    safe_block_hash: Hash32,
    finalized_block_hash: Hash32,
    suggested_fee_recipient: ExecutionAddress,
    # [New in Gloas]
    target_gas_limit: Uint64,
    execution_engine: ExecutionEngine,
) -> Optional[PayloadId]:
    # [New in Gloas:EIP7732]
    parent_bid = state.latest_execution_payload_bid
    if should_build_on_full(store, head):
        envelope = store.payloads[head.root]
        # Make a copy of the state to avoid mutability issues
        state = copy(state)
        # Apply parent payload before computing withdrawals
        apply_parent_execution_payload(state, envelope.execution_requests)
        withdrawals = get_expected_withdrawals(state).withdrawals
        head_block_hash = parent_bid.block_hash
    else:
        withdrawals = state.payload_expected_withdrawals
        head_block_hash = parent_bid.parent_block_hash

    # Set the forkchoice head and initiate the payload build process
    payload_attributes = PayloadAttributes(
        timestamp=compute_time_at_slot(state, state.slot),
        prev_randao=get_randao_mix(state, get_current_epoch(state)),
        suggested_fee_recipient=suggested_fee_recipient,
        # [Modified in Gloas:EIP7732]
        withdrawals=withdrawals,
        parent_beacon_block_root=hash_tree_root(state.latest_block_header),
        # [New in Gloas:EIP7843]
        slot_number=state.slot,
        # [New in Gloas]
        target_gas_limit=target_gas_limit,
    )
    return execution_engine.notify_forkchoice_updated(
        # [Modified in Gloas:EIP7732]
        head_block_hash=head_block_hash,
        safe_block_hash=safe_block_hash,
        finalized_block_hash=finalized_block_hash,
        payload_attributes=payload_attributes,
    )
```

##### Voluntary exits

*Note*: Because execution request processing is deferred, a request in
`parent_execution_requests` can invalidate a voluntary exit in the same block.
For example, a withdrawal request for a validator will cause a voluntary exit
for the same validator to fail, invalidating the entire block. When selecting
voluntary exits to include, proposers must take heed of this interaction.

### Payload timeliness attestation

Some validators are selected to submit payload timeliness attestations.
Validators should call `get_ptc_assignment` at the beginning of an epoch to be
prepared to submit their PTC attestations during the next epoch.

A validator should create and broadcast the `payload_attestation_message` to the
global execution attestation subnet within the first
`get_payload_attestation_due_ms()` milliseconds of the slot.

#### Constructing the `PayloadAttestationMessage`

If a validator is in the payload attestation committee for the current slot (as
obtained from `get_ptc_assignment` above) then the validator should prepare a
`PayloadAttestationMessage` for the current slot. Follow the logic below to
create the `payload_attestation_message` and broadcast to the global
`payload_attestation_message` pubsub topic within the first
`get_payload_attestation_due_ms()` milliseconds of the slot.

The validator creates `payload_attestation_message` as follows:

- If the validator has not seen any beacon block for the assigned slot, do not
  submit a payload attestation; it will be ignored anyway.
- Set `data.beacon_block_root` be the hash tree root of the beacon block seen
  for the assigned slot.
- Set `data.slot` to be the assigned slot.
- If a previously seen `SignedExecutionPayloadEnvelope` references the block
  with root `data.beacon_block_root`, and it was seen before
  `get_payload_due_ms()` milliseconds into the slot, set `data.payload_present`
  to `True`; otherwise, set `data.payload_present` to `False`.
- Set `data.blob_data_available` to `is_data_available(data.beacon_block_root)`.
- Set `payload_attestation_message.validator_index = validator_index` where
  `validator_index` is the validator chosen to submit. The private key mapping
  to `state.validators[validator_index].pubkey` is used to sign the payload
  timeliness attestation.
- Sign the `payload_attestation_message.data` using the helper
  `get_payload_attestation_message_signature`.

Notice that the attester only signs the `PayloadAttestationData` and not the
`validator_index` field in the message. Proposers need to aggregate these
attestations as described above.

```python
def get_payload_attestation_message_signature(
    state: BeaconState, attestation: PayloadAttestationMessage, privkey: int
) -> BLSSignature:
    domain = get_domain(state, DOMAIN_PTC_ATTESTER, compute_epoch_at_slot(attestation.data.slot))
    signing_root = compute_signing_root(attestation.data, domain)
    return bls.Sign(privkey, signing_root)
```

*Note*: Validators do not need to check the full validity of the
`ExecutionPayload` contained in within the envelope, but the checks in the
[Networking](./p2p-interface.md) specifications should pass for the
`SignedExecutionPayloadEnvelope`.

## Modified functions

### Modified `get_data_column_sidecars_from_column_sidecar`

```python
def get_data_column_sidecars_from_column_sidecar(
    sidecar: DataColumnSidecar,
    cells_and_kzg_proofs: Sequence[
        Tuple[Vector[Cell, CELLS_PER_EXT_BLOB], Vector[KZGProof, CELLS_PER_EXT_BLOB]]
    ],
) -> Sequence[DataColumnSidecar]:
    """
    Given a data column sidecar and the cells/proofs associated with each blob
    in the corresponding payload, assemble the sidecars which can be
    distributed to peers.
    """
    # [Modified in Gloas:EIP7732]
    return get_data_column_sidecars(
        sidecar.beacon_block_root,
        sidecar.slot,
        cells_and_kzg_proofs,
    )
```
