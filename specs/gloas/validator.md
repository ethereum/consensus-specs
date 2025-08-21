# Gloas -- Honest Validator

*Note*: This document is a work-in-progress for researchers and implementers.

<!-- mdformat-toc start --slug=github --no-anchors --maxlevel=6 --minlevel=2 -->

- [Introduction](#introduction)
- [Modifications in Gloas](#modifications-in-gloas)
  - [Helper functions](#helper-functions)
    - [Modified `compute_fork_version`](#modified-compute_fork_version)
- [Configuration](#configuration)
  - [Time parameters](#time-parameters)
- [Validator assignment](#validator-assignment)
  - [Lookahead](#lookahead)
- [Beacon chain responsibilities](#beacon-chain-responsibilities)
  - [Attestation](#attestation)
  - [Sync Committee participations](#sync-committee-participations)
  - [Block proposal](#block-proposal)
    - [Constructing the new `signed_execution_payload_header` field in `BeaconBlockBody`](#constructing-the-new-signed_execution_payload_header-field-in-beaconblockbody)
    - [Constructing the new `payload_attestations` field in `BeaconBlockBody`](#constructing-the-new-payload_attestations-field-in-beaconblockbody)
    - [Blob sidecars](#blob-sidecars)
  - [Payload timeliness attestation](#payload-timeliness-attestation)
    - [Constructing a payload attestation](#constructing-a-payload-attestation)
- [Modified functions](#modified-functions)
  - [Modified `prepare_execution_payload`](#modified-prepare_execution_payload)

<!-- mdformat-toc end -->

## Introduction

This document represents the changes and additions to the Honest validator guide
included in Gloas.

## Modifications in Gloas

### Helper functions

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

## Configuration

### Time parameters

| Name                          | Value          |     Unit     |         Duration          |
| ----------------------------- | -------------- | :----------: | :-----------------------: |
| `ATTESTATION_DUE_BPS_GLOAS`   | `uint64(2500)` | basis points | 25% of `SLOT_DURATION_MS` |
| `AGGREGRATE_DUE_BPS_GLOAS`    | `uint64(5000)` | basis points | 50% of `SLOT_DURATION_MS` |
| `SYNC_MESSAGE_DUE_BPS_GLOAS`  | `uint64(2500)` | basis points | 25% of `SLOT_DURATION_MS` |
| `CONTRIBUTION_DUE_BPS_GLOAS`  | `uint64(5000)` | basis points | 50% of `SLOT_DURATION_MS` |
| `PAYLOAD_ATTESTATION_DUE_BPS` | `uint64(7500)` | basis points | 75% of `SLOT_DURATION_MS` |

## Validator assignment

A validator may be a member of the new Payload Timeliness Committee (PTC) for a
given slot. To check for PTC assignments the validator uses the helper
`get_ptc_assignment(state, epoch, validator_index)` where `epoch <= next_epoch`.

PTC committee selection is only stable within the context of the current and
next epoch.

```python
def get_ptc_assignment(
    state: BeaconState, epoch: Epoch, validator_index: ValidatorIndex
) -> Optional[Slot]:
    """
    Returns the slot during the requested epoch in which the validator with index `validator_index`
    is a member of the PTC. Returns None if no assignment is found.
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

- Proposers are no longer required to broadcast `BlobSidecar` objects, as this
  becomes a builder's duty.
- Some validators are selected per slot to become PTC members, these validators
  must broadcast `PayloadAttestationMessage` objects during the assigned slot
  before the deadline of
  `get_slot_component_duration_ms(PAYLOAD_ATTESTATION_DUE_BPS)` milliseconds
  into the slot.

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

### Block proposal

Validators are still expected to propose `SignedBeaconBlock` at the beginning of
any slot during which `is_proposer(state, validator_index)` returns `true`. The
mechanism to prepare this beacon block and related sidecars differs from
previous forks as follows

#### Constructing the new `signed_execution_payload_header` field in `BeaconBlockBody`

To obtain `signed_execution_payload_header`, a block proposer building a block
on top of a `state` must take the following actions:

- Listen to the `execution_payload_header` gossip global topic and save an
  accepted `signed_execution_payload_header` from a builder. Proposer MAY obtain
  these signed messages by other off-protocol means.
- The `signed_execution_payload_header` must satisfy the verification conditions
  found in `process_execution_payload_header`, that is
  - The header signature must be valid
  - The builder balance can cover the header value
  - The header slot is for the proposal block slot
  - The header parent block hash equals the state's `latest_block_hash`.
  - The header parent block root equals the current block's `parent_root`.
- Select one bid and set
  `body.signed_execution_payload_header = signed_execution_payload_header`

#### Constructing the new `payload_attestations` field in `BeaconBlockBody`

Up to `MAX_PAYLOAD_ATTESTATIONS`, aggregate payload attestations can be included
in the block. The validator will have to

- Listen to the `payload_attestation_message` gossip global topic
- The payload attestations added must satisfy the verification conditions found
  in payload attestation gossip validation and payload attestation processing.
  This means
  - The `data.beacon_block_root` corresponds to `block.parent_root`.
  - The slot of the parent block is exactly one slot before the proposing slot.
  - The signature of the payload attestation data message verifies correctly.
- The proposer needs to aggregate all payload attestations with the same data
  into a given `PayloadAttestation` object. For this it needs to fill the
  `aggregation_bits` field by using the relative position of the validator
  indices with respect to the PTC that is obtained from
  `get_ptc(state, block_slot - 1)`.

#### Blob sidecars

The blob sidecars are no longer broadcast by the validator, and thus their
construction is not necessary. This deprecates the corresponding sections from
the honest validator guide in the Fulu fork, moving them, albeit with some
modifications, to the [honest Builder guide](./builder.md)

### Payload timeliness attestation

Some validators are selected to submit payload timeliness attestations.
Validators should call `get_ptc_assignment` at the beginning of an epoch to be
prepared to submit their PTC attestations during the next epoch.

A validator should create and broadcast the `payload_attestation_message` to the
global execution attestation subnet not after
`get_slot_component_duration_ms(PAYLOAD_ATTESTATION_DUE_BPS)` milliseconds since
the start of `slot`.

#### Constructing a payload attestation

If a validator is in the payload attestation committee for the current slot (as
obtained from `get_ptc_assignment` above) then the validator should prepare a
`PayloadAttestationMessage` for the current slot, according to the logic in
`get_payload_attestation_message` below and broadcast it not after
`get_slot_component_duration_ms(PAYLOAD_ATTESTATION_DUE_BPS)` milliseconds since
the start of the slot, to the global `payload_attestation_message` pubsub topic.

The validator creates `payload_attestation_message` as follows:

- If the validator has not seen any beacon block for the assigned slot, do not
  submit a payload attestation. It will be ignored anyway.
- Set `data.beacon_block_root` be the HTR of the beacon block seen for the
  assigned slot
- Set `data.slot` to be the assigned slot.
- If a `SignedExecutionPayloadEnvelope` has been seen referencing the block
  `data.beacon_block_root` set `data.payload_present = True`. Otherwise set it
  to `False`.
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

**Remark** Validators do not need to check the full validity of the
`ExecutionPayload` contained in within the envelope, but the checks in the
[P2P guide](./p2p-interface.md) should pass for the
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
    # Verify consistency of the parent hash with respect to the previous execution payload header
    parent_hash = state.latest_execution_payload_header.block_hash

    # [Modified in Gloas:EIP7732]
    # Set the forkchoice head and initiate the payload build process
    withdrawals, _, _ = get_expected_withdrawals(state)

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
