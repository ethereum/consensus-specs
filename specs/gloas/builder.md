# Gloas -- Honest Builder

*Note*: This document is a work-in-progress for researchers and implementers.

<!-- mdformat-toc start --slug=github --no-anchors --maxlevel=6 --minlevel=2 -->

- [Introduction](#introduction)
- [Becoming a builder](#becoming-a-builder)
  - [Builder withdrawal credentials](#builder-withdrawal-credentials)
  - [Submit deposit](#submit-deposit)
  - [Process deposit](#process-deposit)
  - [Builder index](#builder-index)
  - [Activation](#activation)
- [Builder activities](#builder-activities)
  - [Constructing the `SignedExecutionPayloadBid`](#constructing-the-signedexecutionpayloadbid)
  - [Constructing the `DataColumnSidecar`s](#constructing-the-datacolumnsidecars)
    - [Modified `get_data_column_sidecars`](#modified-get_data_column_sidecars)
    - [Modified `get_data_column_sidecars_from_block`](#modified-get_data_column_sidecars_from_block)
  - [Constructing the `SignedExecutionPayloadEnvelope`](#constructing-the-signedexecutionpayloadenvelope)
  - [Honest payload withheld messages](#honest-payload-withheld-messages)

<!-- mdformat-toc end -->

## Introduction

This is an accompanying document which describes the expected actions of a
"builder" participating in the Ethereum proof-of-stake protocol.

With the Gloas upgrade, the protocol introduces a new type of staked actor (not
a validator) called a *builder*. Since builders are not validators, they do not
perform validator duties (e.g., attesting and proposing) and therefore do not
earn yield on their stake. Builders have the option to produce execution
payloads by submitting bids. This document is a collection of guidelines for
builders.

## Becoming a builder

### Builder withdrawal credentials

When submitting a deposit to the deposit contract, the `withdrawal_credentials`
field determines whether the staked actor will be a validator or a builder. To
be recognized as a builder, the `withdrawal_credentials` must use the
`BUILDER_WITHDRAWAL_PREFIX`.

The `withdrawal_credentials` field must be:

- `withdrawal_credentials[:1] == BUILDER_WITHDRAWAL_PREFIX` (`0x03`)
- `withdrawal_credentials[1:12] == b'\x00' * 11`
- `withdrawal_credentials[12:] == builder_execution_address`

Where `builder_execution_address` is an execution-layer address that will
receive withdrawals.

### Submit deposit

Builders follow the same deposit process as validators, but with the
builder-specific withdrawal credentials. The deposit must include:

- `pubkey`: The builder's BLS public key.
- `withdrawal_credentials`: With the `BUILDER_WITHDRAWAL_PREFIX` (`0x03`)
  prefix.
- `amount`: At least `MIN_DEPOSIT_AMOUNT` gwei.
- `signature`: BLS signature over the deposit data.

### Process deposit

The beacon chain processes builder deposits identically to validator deposits,
with the withdrawal credentials using `BUILDER_WITHDRAWAL_PREFIX`.

### Builder index

When the deposit is processed on the beacon chain, the builder is assigned a
unique `builder_index` within the builder registry. This index is used to
identify the builder in execution payload bids and envelopes.

### Activation

Builders become active once the epoch in which they were registered (assigned an
index) has been finalized. Since registrations occur as soon as deposits reach
the beacon chain, builders typically become active two epochs after submitting
their deposit.

*Note*: At the fork, pending deposits with the `BUILDER_WITHDRAWAL_PREFIX` are
applied to the builder registry. The builder's `deposit_epoch` is set to the
epoch of the pending deposit, not the fork epoch. Therefore, if that epoch is
finalized at the fork, the builder will be immediately active. See
`onboard_builders_from_pending_deposits` for details.

## Builder activities

Builders have two optional activities: submitting bids and submitting payloads.
Builders can submit bids to produce execution payloads. They can broadcast these
bids in the form of `SignedExecutionPayloadBid` objects. These objects encode a
commitment to reveal an execution payload in exchange for a payment. When their
bids are chosen by the corresponding proposer, builders are expected to
broadcast an accompanying `SignedExecutionPayloadEnvelope` object honoring the
commitment. If a proposer accepts a builder's bid, the builder will pay the
proposer what it promised whether it submits the payload or not.

### Constructing the `SignedExecutionPayloadBid`

Builders can broadcast a payload bid for the current or the next slot's proposer
to include. They produce a `SignedExecutionPayloadBid` as follows.

01. Set `bid.parent_block_hash` to the current head of the execution chain (this
    can be obtained from the beacon state as `state.latest_block_hash`).
02. Set `bid.parent_block_root` to be the head of the consensus chain; this can
    be obtained from the beacon state as
    `hash_tree_root(state.latest_block_header)`. The `parent_block_root` and
    `parent_block_hash` must be compatible, in the sense that they both should
    come from the same `state` by the method described in this and the previous
    point.
03. Construct an execution payload. This can be performed with an external
    execution engine via a call to `engine_getPayloadV5`.
04. Set `bid.block_hash` to be the block hash of the constructed payload, that
    is `payload.block_hash`.
05. Set `bid.prev_randao` to be the previous RANDAO of the constructed payload,
    that is `payload.prev_randao`.
06. Set `bid.fee_recipient` to be an execution address to receive the payment.
    The proposer's preferred fee recipient can be obtained from the
    `SignedProposerPreferences` associated with `bid.slot`.
07. Set `bid.gas_limit` to be the gas limit of the constructed payload. The
    proposer's preferred gas limit can be obtained from the
    `SignedProposerPreferences` associated with `bid.slot`.
08. Set `bid.builder_index` to be the index of the builder performing these
    actions.
09. Set `bid.slot` to be the slot for which this bid is aimed. This slot
    **MUST** be either the current slot or the next slot.
10. Set `bid.value` to be the value (in gwei) that the builder will pay the
    proposer if the bid is accepted. The builder **MUST** have enough excess
    balance to fulfill this bid and all pending payments.
11. Set `bid.execution_payment` to zero. A non-zero value indicates a trusted
    execution-layer payment. Bids with non-zero `execution_payment` **MUST NOT**
    be broadcast to the `execution_payload_bid` gossip topic.
12. Set `bid.blob_kzg_commitments` to be the `blobsbundle.commitments` field
    returned by `engine_getPayloadV5`.

After building the `bid`, the builder obtains a `signature` of the bid by using:

```python
def get_execution_payload_bid_signature(
    state: BeaconState, bid: ExecutionPayloadBid, privkey: int
) -> BLSSignature:
    domain = get_domain(state, DOMAIN_BEACON_BUILDER, compute_epoch_at_slot(bid.slot))
    signing_root = compute_signing_root(bid, domain)
    return bls.Sign(privkey, signing_root)
```

Then the builder assembles
`signed_execution_payload_bid = SignedExecutionPayloadBid(message=bid, signature=signature)`
and broadcasts it on the `execution_payload_bid` global gossip topic.

### Constructing the `DataColumnSidecar`s

#### Modified `get_data_column_sidecars`

```python
def get_data_column_sidecars(
    # [Modified in Gloas:EIP7732]
    # Removed `signed_block_header`
    # [New in Gloas:EIP7732]
    beacon_block_root: Root,
    # [New in Gloas:EIP7732]
    slot: Slot,
    # [Modified in Gloas:EIP7732]
    # Removed `kzg_commitments`
    # [Modified in Gloas:EIP7732]
    # Removed `kzg_commitments_inclusion_proof`
    cells_and_kzg_proofs: Sequence[
        Tuple[Vector[Cell, CELLS_PER_EXT_BLOB], Vector[KZGProof, CELLS_PER_EXT_BLOB]]
    ],
) -> Sequence[DataColumnSidecar]:
    """
    Given a beacon block root and the cells/proofs associated with each blob
    in the corresponding payload, assemble the sidecars which can be
    distributed to peers.
    """
    sidecars = []
    for column_index in range(NUMBER_OF_COLUMNS):
        column_cells, column_proofs = [], []
        for cells, proofs in cells_and_kzg_proofs:
            column_cells.append(cells[column_index])
            column_proofs.append(proofs[column_index])
        sidecars.append(
            # [Modified in Gloas:EIP7732]
            DataColumnSidecar(
                index=column_index,
                column=column_cells,
                kzg_proofs=column_proofs,
                slot=slot,
                beacon_block_root=beacon_block_root,
            )
        )
    return sidecars
```

#### Modified `get_data_column_sidecars_from_block`

*Note*: The function `get_data_column_sidecars_from_block` is modified to use
`beacon_block_root` instead of header and inclusion proof computations.

```python
def get_data_column_sidecars_from_block(
    signed_block: SignedBeaconBlock,
    cells_and_kzg_proofs: Sequence[
        Tuple[Vector[Cell, CELLS_PER_EXT_BLOB], Vector[KZGProof, CELLS_PER_EXT_BLOB]]
    ],
) -> Sequence[DataColumnSidecar]:
    """
    Given a signed block and the cells/proofs associated with each blob in the
    block, assemble the sidecars which can be distributed to peers.
    """
    beacon_block_root = hash_tree_root(signed_block.message)
    return get_data_column_sidecars(
        beacon_block_root,
        signed_block.message.slot,
        cells_and_kzg_proofs,
    )
```

### Constructing the `SignedExecutionPayloadEnvelope`

When the proposer publishes a valid `SignedBeaconBlock` containing a signed
commitment by the builder, the builder is later expected to broadcast the
corresponding `SignedExecutionPayloadEnvelope` that fulfills this commitment.
See below for a special case of an *honestly withheld payload*.

To construct the `ExecutionPayloadEnvelope` the builder must perform the
following steps. We alias `block` to be the corresponding `BeaconBlock` and
alias `bid` to be the committed `ExecutionPayloadBid` in
`block.body.signed_execution_payload_bid.message`.

1. Set `envelope.payload` to be the `ExecutionPayload` constructed when creating
   the corresponding bid. This payload **MUST** have the same block hash as
   `bid.block_hash`.
2. Set `envelope.execution_requests` to be the `ExecutionRequests` associated
   with `payload`.
3. Set `envelope.builder_index` to be the index of the builder performing these
   steps. This field **MUST** be `bid.builder_index`.
4. Set `envelope.beacon_block_root` to be `hash_tree_root(block)`.
5. Set `envelope.slot` to be `block.slot`.

After setting these parameters, the builder assembles
`signed_execution_payload_envelope = SignedExecutionPayloadEnvelope(message=envelope, signature=BLSSignature())`,
then verify that the envelope is valid with
`process_execution_payload(state, signed_execution_payload_envelope, execution_engine, verify=False)`.
This function should not trigger an exception.

7. Set `envelope.state_root` to `hash_tree_root(state)`.

After preparing the `envelope` the builder should sign the envelope using:

```python
def get_execution_payload_envelope_signature(
    state: BeaconState, envelope: ExecutionPayloadEnvelope, privkey: int
) -> BLSSignature:
    domain = get_domain(state, DOMAIN_BEACON_BUILDER, compute_epoch_at_slot(state.slot))
    signing_root = compute_signing_root(envelope, domain)
    return bls.Sign(privkey, signing_root)
```

Then the builder assembles
`signed_execution_payload_envelope = SignedExecutionPayloadEnvelope(message=envelope, signature=signature)`
and broadcasts it on the `execution_payload` global gossip topic.

### Honest payload withheld messages

An honest builder that has seen a `SignedBeaconBlock` referencing his signed
bid, but that block was not timely and thus it is not the head of the builder's
chain, may choose to withhold their execution payload. For this, the builder
should act as if no block was produced and not broadcast the payload.
