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
  - [Validating a `SignedExecutionPayloadBid`](#validating-a-signedexecutionpayloadbid)
  - [Block proposal](#block-proposal)
    - [Constructing `signed_execution_payload_bid`](#constructing-signed_execution_payload_bid)
    - [Constructing `payload_attestations`](#constructing-payload_attestations)
    - [Blob sidecars](#blob-sidecars)
  - [Payload timeliness attestation](#payload-timeliness-attestation)
    - [Constructing a payload attestation](#constructing-a-payload-attestation)
- [Modified functions](#modified-functions)
  - [Modified `prepare_execution_payload`](#modified-prepare_execution_payload)
- [Data column sidecars](#data-column-sidecars)
  - [Modified `get_data_column_sidecars_from_column_sidecar`](#modified-get_data_column_sidecars_from_column_sidecar)

<!-- mdformat-toc end -->

## Introduction

This document represents the changes to be made in the code of an "honest
validator" to implement Gloas.

## Configuration

### Time parameters

| Name                          | Value          |     Unit     |         Duration          |
| ----------------------------- | -------------- | :----------: | :-----------------------: |
| `ATTESTATION_DUE_BPS_GLOAS`   | `uint64(2500)` | basis points | 25% of `SLOT_DURATION_MS` |
| `AGGREGATE_DUE_BPS_GLOAS`     | `uint64(5000)` | basis points | 50% of `SLOT_DURATION_MS` |
| `SYNC_MESSAGE_DUE_BPS_GLOAS`  | `uint64(2500)` | basis points | 25% of `SLOT_DURATION_MS` |
| `CONTRIBUTION_DUE_BPS_GLOAS`  | `uint64(5000)` | basis points | 50% of `SLOT_DURATION_MS` |
| `PAYLOAD_ATTESTATION_DUE_BPS` | `uint64(7500)` | basis points | 75% of `SLOT_DURATION_MS` |

## Validator assignment

### Payload timeliness committee

A validator may be a member of the new Payload Timeliness Committee (PTC) for a
given slot. To check for PTC assignments, use
`get_ptc_assignment(state, epoch, validator_index)` where `epoch <= next_epoch`,
as PTC committee selection is only stable within the context of the current and
next epoch.

```python
def get_ptc_assignment(
    state: BeaconState, epoch: Epoch, validator_index: ValidatorIndex
) -> Optional[Slot]:
    """
    Returns the slot during the requested epoch in which the validator with
    index `validator_index` is a member of the PTC. Returns None if no
    assignment is found.
    """
    next_epoch = Epoch(get_current_epoch(state) + 1)
    assert epoch <= next_epoch

    start_slot = compute_start_slot_at_epoch(epoch)
    for slot in range(start_slot, start_slot + SLOTS_PER_EPOCH):
        if validator_index in get_ptc(state, Slot(slot)):
            return Slot(slot)
    return None
```

### Lookahead

*[New in Gloas:EIP7732]*

`get_ptc_assignment` should be called at the start of each epoch to get the
assignment for the next epoch (`current_epoch + 1`). A validator should plan for
future assignments by noting their assigned PTC slot.

## Beacon chain responsibilities

All validator responsibilities remain unchanged other than the following:

- Proposers are no longer required to broadcast `DataColumnSidecar` objects, as
  this becomes a builder's duty.
- Some attesters are selected per slot to become PTC members, these validators
  must broadcast `PayloadAttestationMessage` objects during the assigned slot
  before the deadline of `get_attestation_due_ms(epoch)` milliseconds into the
  slot.

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

### Validating a `SignedExecutionPayloadBid`

When the proposer receives a `SignedExecutionPayloadBid` from either the p2p
gossip topic or from the Builder-API, it can validate the bid using
`validate_bid`. It can discard the bid if the conditions are not satisfied.

```python
def validate_bid(
    state: BeaconState, signed_bid: SignedExecutionPayloadBid, fee_recipient: ExecutionAddress
) -> bool:
    builder = state.builders[signed_bid.builder_index]

    assert signed_bid.slot == state.slot
    assert signed_bid.fee_recipient == fee_recipient
    assert signed_bid.parent_block_hash == state.latest_block_hash
    assert signed_bid.parent_block_root == hash_tree_root(state.latest_block_header)
    assert signed_bid.prev_randao == get_randao_mix(state, get_current_epoch(state))
    assert is_builder(state, builder.pubkey)

    if signed_bid.value > 0:
        assert can_builder_cover_bid(state, signed_bid.builder_index, signed_bid.value)

    return verify_execution_payload_bid_signature(state, signed_bid)
```

### Block proposal

Validators are still expected to propose `SignedBeaconBlock` at the beginning of
any slot during which `is_proposer(state, validator_index)` returns `True`. The
mechanism to prepare this beacon block and related sidecars differs from
previous forks as follows

#### Constructing `signed_execution_payload_bid`

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
  - The `bid.parent_block_hash` equals the state's `latest_block_hash`.
  - The `bid.parent_block_root` equals the current block's `parent_root`.
- Select one bid and set
  `body.signed_execution_payload_bid = signed_execution_payload_bid`.

*Note:* The execution address encoded in the `fee_recipient` field in the
`signed_execution_payload_bid.message` will receive the builder payment.

#### Constructing `payload_attestations`

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
  `get_ptc(state, block_slot - 1)`.

#### Blob sidecars

The blob sidecars are no longer broadcast by the validator, and thus their
construction is not necessary. This deprecates the corresponding sections from
the Honest Validator specifications in the Fulu fork, moving them, albeit with
some modifications, to the [Honest Builder](./builder.md) specifications.

### Payload timeliness attestation

Some validators are selected to submit payload timeliness attestations.
Validators should call `get_ptc_assignment` at the beginning of an epoch to be
prepared to submit their PTC attestations during the next epoch.

A validator should create and broadcast the `payload_attestation_message` to the
global execution attestation subnet within the first
`get_payload_attestation_due_ms(epoch)` milliseconds of the slot.

#### Constructing a payload attestation

If a validator is in the payload attestation committee for the current slot (as
obtained from `get_ptc_assignment` above) then the validator should prepare a
`PayloadAttestationMessage` for the current slot. Follow the logic below to
create the `payload_attestation_message` and broadcast to the global
`payload_attestation_message` pubsub topic within the first
`get_payload_attestation_due_ms(epoch)` milliseconds of the slot.

The validator creates `payload_attestation_message` as follows:

- If the validator has not seen any beacon block for the assigned slot, do not
  submit a payload attestation; it will be ignored anyway.
- Set `data.beacon_block_root` be the hash tree root of the beacon block seen
  for the assigned slot.
- Set `data.slot` to be the assigned slot.
- If a previously seen `SignedExecutionPayloadEnvelope` references the block
  with root `data.beacon_block_root`, set `data.payload_present` to `True`;
  otherwise, set `data.payload_present` to `False`.
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

### Modified `prepare_execution_payload`

*Note*: The function `prepare_execution_payload` is modified to handle the
updated `get_expected_withdrawals` return signature.

```python
def prepare_execution_payload(
    state: BeaconState,
    safe_block_hash: Hash32,
    finalized_block_hash: Hash32,
    suggested_fee_recipient: ExecutionAddress,
    execution_engine: ExecutionEngine,
) -> Optional[PayloadId]:
    # Verify consistency of the parent hash with respect to the previous execution payload bid
    parent_hash = state.latest_execution_payload_bid.block_hash

    # [Modified in Gloas:EIP7732]
    # Set the forkchoice head and initiate the payload build process
    withdrawals, _, _, _ = get_expected_withdrawals(state)

    payload_attributes = PayloadAttributes(
        timestamp=compute_time_at_slot(state, state.slot),
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

## Data column sidecars

*[Modified in Gloas]*

### Modified `get_data_column_sidecars_from_column_sidecar`

```python
def get_data_column_sidecars_from_column_sidecar(
    sidecar: DataColumnSidecar,
    cells_and_kzg_proofs: Sequence[
        Tuple[Vector[Cell, CELLS_PER_EXT_BLOB], Vector[KZGProof, CELLS_PER_EXT_BLOB]]
    ],
) -> Sequence[DataColumnSidecar]:
    """
    Given a DataColumnSidecar and the cells/proofs associated with each blob corresponding
    to the commitments it contains, assemble all sidecars for distribution to peers.
    """
    assert len(cells_and_kzg_proofs) == len(sidecar.kzg_commitments)

    return get_data_column_sidecars(
        sidecar.beacon_block_root,
        sidecar.slot,
        sidecar.kzg_commitments,
        cells_and_kzg_proofs,
    )
```
