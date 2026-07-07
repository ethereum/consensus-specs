# Gloas -- Honest Builder

*Note*: This document is a work-in-progress for researchers and implementers.

<!-- mdformat-toc start --slug=github --no-anchors --maxlevel=6 --minlevel=2 -->

- [Introduction](#introduction)
- [Becoming a builder](#becoming-a-builder)
  - [Submit deposit](#submit-deposit)
  - [Process deposit](#process-deposit)
  - [Builder index](#builder-index)
  - [Activation](#activation)
  - [Exiting](#exiting)
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

### Submit deposit

Builders are created by submitting a builder deposit request to the builder
deposit contract on the execution layer, as defined in EIP-8282. The request
must include:

- `pubkey`: The builder's BLS public key.
- `withdrawal_credentials`: The withdrawal credentials. The last 20 bytes are
  the execution-layer address that will receive withdrawals. In Gloas, new
  builders are registered with `PAYLOAD_BUILDER_VERSION` regardless of the first
  byte.
- `amount`: At least `MIN_DEPOSIT_AMOUNT` gwei.
- `signature`: BLS proof of possession over the corresponding `DepositMessage`
  under `DOMAIN_BUILDER_DEPOSIT`.

*Note*: Builders may be onboarded at the fork by submitting a deposit to the
validator deposit contract with a `BUILDER_WITHDRAWAL_PREFIX` withdrawal
credential. This must be done late enough that the deposit is still pending at
the fork, but early enough that the slot in which the deposit is added to the
pending deposit queue is finalized so that the builder is considered active.
Such a deposit signs over `DepositMessage` under `DOMAIN_DEPOSIT`, with
withdrawal credentials of the form
`BUILDER_WITHDRAWAL_PREFIX + b"\x00" * 11 + execution_address`.

### Process deposit

A builder deposit request for a new pubkey registers a builder with
`PAYLOAD_BUILDER_VERSION`. A request for an existing builder's pubkey tops up
its balance.

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

### Exiting

A builder exits by submitting a builder exit request to the builder exit
contract on the execution layer, as defined in EIP-8282. The request contains
the builder's `pubkey` and is authorized by the builder's `execution_address`
(the transaction sender), not the BLS key.

The consensus layer initiates the exit only if the builder is active, the
request's `source_address` matches the builder's `execution_address`, and the
builder has no pending balance to withdraw. Otherwise the request is consumed
without effect and must be resubmitted once those conditions hold.

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

01. Set `bid.parent_block_hash` to be the parent hash of the constructed
    payload, that is `payload.parent_hash`.
02. Set `bid.parent_block_root` to be the head of the consensus chain. This can
    be obtained from the beacon state as
    `hash_tree_root(state.latest_block_header)`. The `parent_block_root` and
    `parent_block_hash` must be compatible, in the sense that they both should
    come from the same `state` and `store` by the method described in this and
    the previous point.
03. Construct an execution payload. This can be performed with an external
    execution engine via a call to `engine_getPayloadV6`.
04. Set `bid.block_hash` to be the block hash of the constructed payload, that
    is `payload.block_hash`.
05. Set `bid.prev_randao` to be the previous RANDAO of the constructed payload,
    that is `payload.prev_randao`. This value **MUST** equal
    `get_randao_mix(parent_state, get_current_epoch(parent_state))`, where
    `parent_state` is the post-state of `bid.parent_block_root`.
06. Set `bid.slot` to be the slot for which this bid is aimed. This slot
    **MUST** be either the current slot or the next slot.
07. Set `bid.fee_recipient` to be an execution address to receive the payment.
    The proposer's preferred fee recipient is obtained from the
    `SignedProposerPreferences` whose `message.proposal_slot` matches `bid.slot`
    and whose `message.dependent_root` matches
    `get_shuffling_dependent_root(store, bid.parent_block_root, compute_epoch_at_slot(bid.slot))`,
    where `store` is the fork choice store.
08. Set `bid.gas_limit` to be the gas limit of the constructed payload, which
    **MUST** satisfy
    `is_gas_limit_target_compatible(parent_gas_limit, bid.gas_limit, target_gas_limit)`,
    where `parent_gas_limit` is the `gas_limit` of the parent execution payload
    and `target_gas_limit` is the `target_gas_limit` in the
    `SignedProposerPreferences` referenced in step 7.
09. Set `bid.builder_index` to be the index of the builder performing these
    actions.
10. Set `bid.value` to be the value (in gwei) that the builder will pay the
    proposer if the bid is accepted. The builder **MUST** have enough excess
    balance to fulfill this bid and all pending payments.
11. Set `bid.execution_payment` to zero. A non-zero value indicates a trusted
    execution-layer payment. Bids with non-zero `execution_payment` **MUST NOT**
    be broadcast to the `execution_payload_bid` gossip topic.
12. Set `bid.blob_kzg_commitments` to be the `blobsbundle.commitments` field
    returned by `engine_getPayloadV6`.
13. Set `bid.execution_requests_root` to `hash_tree_root(execution_requests)`,
    where `execution_requests` is the `ExecutionRequests` field returned by
    `engine_getPayloadV6`.

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
5. Set `envelope.parent_beacon_block_root` to be `block.parent_root`.

After preparing the `envelope` the builder signs it using:

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
