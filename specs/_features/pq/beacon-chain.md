# PQ -- The Beacon Chain

*Note*: This document is a work-in-progress for researchers and implementers.

<!-- mdformat-toc start --slug=github --no-anchors --maxlevel=6 --minlevel=2 -->

- [Introduction](#introduction)
- [Types](#types)
  - [New `PQDataList`](#new-pqdatalist)
  - [New `XMSSAggregateSignature`](#new-xmssaggregatesignature)
  - [New `XMSSPubkey`](#new-xmsspubkey)
  - [New `XMSSSignature`](#new-xmsssignature)
- [Constants](#constants)
  - [XMSS](#xmss)
  - [XMSS leaf offsets](#xmss-leaf-offsets)
- [Presets](#presets)
  - [XMSS](#xmss-1)
  - [Max operations per block](#max-operations-per-block)
- [Containers](#containers)
  - [Modified containers](#modified-containers)
    - [`Attestation`](#attestation)
    - [`BeaconBlockBody`](#beaconblockbody)
    - [`BeaconState`](#beaconstate)
    - [`ExecutionRequests`](#executionrequests)
    - [`IndexedAttestation`](#indexedattestation)
    - [`PayloadAttestationMessage`](#payloadattestationmessage)
    - [`SignedBeaconBlock`](#signedbeaconblock)
    - [`SignedBeaconBlockHeader`](#signedbeaconblockheader)
    - [`SignedExecutionPayloadBid`](#signedexecutionpayloadbid)
    - [`SignedExecutionPayloadEnvelope`](#signedexecutionpayloadenvelope)
    - [`SignedVoluntaryExit`](#signedvoluntaryexit)
    - [`SingleAttestation`](#singleattestation)
  - [New containers](#new-containers)
    - [`PQData`](#pqdata)
- [Helpers](#helpers)
  - [Crypto](#crypto)
    - [XMSS signatures](#xmss-signatures)
  - [Misc](#misc)
    - [New `compute_xmss_leaf_index`](#new-compute_xmss_leaf_index)
  - [Predicates](#predicates)
    - [Modified `is_valid_indexed_attestation`](#modified-is_valid_indexed_attestation)
  - [Beacon state accessors](#beacon-state-accessors)
    - [New `get_xmss_pubkey`](#new-get_xmss_pubkey)
- [Beacon chain state transition function](#beacon-chain-state-transition-function)
  - [Modified `verify_block_signature`](#modified-verify_block_signature)
  - [Epoch processing](#epoch-processing)
    - [Modified `process_epoch`](#modified-process_epoch)
  - [Block processing](#block-processing)
    - [Modified `process_block`](#modified-process_block)
    - [Modified `process_randao`](#modified-process_randao)
    - [Execution payload](#execution-payload)
      - [Modified `get_execution_requests_list`](#modified-get_execution_requests_list)
      - [Modified `verify_execution_payload_envelope_signature`](#modified-verify_execution_payload_envelope_signature)
    - [Execution payload bid](#execution-payload-bid)
      - [Modified `verify_execution_payload_bid_signature`](#modified-verify_execution_payload_bid_signature)
      - [Modified `process_execution_payload_bid`](#modified-process_execution_payload_bid)
    - [Operations](#operations)
      - [Modified `process_operations`](#modified-process_operations)
      - [Modified `process_proposer_slashing`](#modified-process_proposer_slashing)
      - [Modified `process_voluntary_exit`](#modified-process_voluntary_exit)
    - [Parent execution payload](#parent-execution-payload)
      - [Modified `apply_parent_execution_payload`](#modified-apply_parent_execution_payload)

<!-- mdformat-toc end -->

## Introduction

This upgrade replaces the BLS signatures used by validators and builders with
leanXMSS, a hash-based signature scheme believed to be secure against a quantum
adversary.

This upgrade is meant as an emergency fork for when elliptic curve cryptography
can no longer be trusted, so it keeps only what consensus needs. It removes sync
committees, whose hundreds of signatures per slot serve only light clients, and
with them the light client protocol. It also disables blobs, because KZG
commitments rely on elliptic curve pairings. The execution layer must reject
blob transactions from the fork on.

XMSS is a stateful scheme. A key covers a fixed number of one-time leaves, and
signing two different messages at the same leaf breaks the key. This upgrade
therefore assigns every validator message a leaf derived from its slot and its
type, see `compute_xmss_leaf_index`. An honest signer that never equivocates
never reuses a leaf. Each signature carries its leaf index, and verification
checks it against the expected one.

XMSS has no native aggregation. Aggregates are opaque `XMSSAggregateSignature`
values, produced and checked by `xmss.Aggregate` and `xmss.AggregateVerify`. The
reference implementation concatenates signatures as a stand-in for a succinct
aggregation scheme.

Validators and builders keep their BLS public keys as identifiers, so execution
layer requests and deposits still refer to them by BLS public key. Their XMSS
public keys and VRF data, registered with EIP-8483 before the fork, are stored
in `state.pq_data`, and every signature is verified against the XMSS public key
found there. Validators and builders that did not register are exited at the
fork. See [the fork document](./fork.md) for details.

*Note*: A validator or builder that deposits after the fork has no entry in
`state.pq_data`, so it cannot sign. Deposits also still carry a BLS proof of
possession. A way to register keys after the fork is left open.

`BLSToExecutionChange` is disabled, because its BLS signature could be forged.
Balances behind `0x00` withdrawal credentials stay locked until a later upgrade
adds a quantum-safe way to change them.

Consolidation requests are deprecated, so the execution layer must stop
producing them at the fork. Pending consolidations still complete.

Blocks no longer carry payload attestations, which spares proposers from
aggregating them. The payload timeliness committee still broadcasts its votes,
which fork choice uses as before.

*Note*: This specification is built upon [EIP-8483](../eip8483/beacon-chain.md),
which is built upon [Gloas](../../gloas/beacon-chain.md).

## Types

### New `PQDataList`

```python
class PQDataList(ProgressiveList[PQData]):
    """
    The post-quantum keys and VRF data of validators and builders, at most one
    entry per role and BLS public key.
    """
```

### New `XMSSAggregateSignature`

```python
class XMSSAggregateSignature(ByteList):
    """
    An aggregate of XMSS signatures over the same message at the same leaf.
    """

    LIMIT = MAX_XMSS_AGGREGATE_SIGNATURE_SIZE
```

### New `XMSSPubkey`

```python
class XMSSPubkey(Bytes32):
    """
    A leanXMSS public key, the Merkle root followed by the public parameter.
    """
```

### New `XMSSSignature`

```python
class XMSSSignature(ByteVector):
    """
    A leanXMSS signature, the leaf index followed by one signature per layer.
    """

    LENGTH = XMSS_SIGNATURE_SIZE
```

## Constants

### XMSS

| Name                   | Value                 |
| ---------------------- | --------------------- |
| `XMSS_SIGNATURE_SIZE`  | `Uint64(2404)`        |
| `XMSS_LEAVES_PER_SLOT` | `Uint64(2**4)` (= 16) |

### XMSS leaf offsets

| Name                                     | Value       |
| ---------------------------------------- | ----------- |
| `LEAF_OFFSET_BEACON_PROPOSER`            | `Uint64(0)` |
| `LEAF_OFFSET_RANDAO`                     | `Uint64(1)` |
| `LEAF_OFFSET_BEACON_ATTESTER`            | `Uint64(2)` |
| `LEAF_OFFSET_AGGREGATE_AND_PROOF`        | `Uint64(3)` |
| `LEAF_OFFSET_PTC_ATTESTER`               | `Uint64(4)` |
| `LEAF_OFFSET_PROPOSER_PREFERENCES`       | `Uint64(5)` |
| `LEAF_OFFSET_EXECUTION_PAYLOAD_BID`      | `Uint64(6)` |
| `LEAF_OFFSET_EXECUTION_PAYLOAD_ENVELOPE` | `Uint64(7)` |
| `LEAF_OFFSET_VOLUNTARY_EXIT`             | `Uint64(8)` |

## Presets

### XMSS

| Name                                | Value                         |
| ----------------------------------- | ----------------------------- |
| `MAX_XMSS_AGGREGATE_SIGNATURE_SIZE` | `Uint64(2**20)` (= 1,048,576) |

*Note*: `MAX_XMSS_AGGREGATE_SIGNATURE_SIZE` is a placeholder for the proof size
of a succinct aggregation scheme. The reference concatenation fits at most
`MAX_XMSS_AGGREGATE_SIGNATURE_SIZE // XMSS_SIGNATURE_SIZE` signatures.

### Max operations per block

| Name                  | Value                 |
| --------------------- | --------------------- |
| `MAX_ATTESTATIONS_PQ` | `Uint64(2**4)` (= 16) |

## Containers

### Modified containers

#### `Attestation`

```python
class Attestation(ProgressiveContainer):
    ACTIVE_FIELDS = active_fields(width=4)

    aggregation_bits: AggregationBits
    data: AttestationData
    # [Modified in PQ]
    signature: XMSSAggregateSignature
    committee_bits: CommitteeBits
```

#### `BeaconBlockBody`

```python
class BeaconBlockBody(ProgressiveContainer):
    ACTIVE_FIELDS = active_fields(width=13, gaps=(8, 9, 11))

    # [Modified in PQ]
    randao_reveal: XMSSSignature
    eth1_data: Eth1Data
    graffiti: Bytes32
    proposer_slashings: ProposerSlashings
    attester_slashings: AttesterSlashings
    attestations: Attestations
    deposits: Deposits
    voluntary_exits: VoluntaryExits
    # [Modified in PQ]
    # Removed `sync_aggregate`
    # [Modified in PQ]
    # Removed `bls_to_execution_changes`
    signed_execution_payload_bid: SignedExecutionPayloadBid
    # [Modified in PQ]
    # Removed `payload_attestations`
    parent_execution_requests: ExecutionRequests
```

#### `BeaconState`

```python
class BeaconState(ProgressiveContainer):
    ACTIVE_FIELDS = active_fields(width=48, gaps=(22, 23, 46))

    genesis_time: Uint64
    genesis_validators_root: Root
    slot: Slot
    fork: Fork
    latest_block_header: BeaconBlockHeader
    block_roots: BlockRoots
    state_roots: StateRoots
    historical_roots: HistoricalRoots
    eth1_data: Eth1Data
    eth1_data_votes: Eth1DataVotes
    eth1_deposit_index: Uint64
    validators: Validators
    balances: Balances
    randao_mixes: RandaoMixes
    slashings: Slashings
    previous_epoch_participation: EpochParticipation
    current_epoch_participation: EpochParticipation
    justification_bits: JustificationBits
    previous_justified_checkpoint: Checkpoint
    current_justified_checkpoint: Checkpoint
    finalized_checkpoint: Checkpoint
    inactivity_scores: InactivityScores
    # [Modified in PQ]
    # Removed `current_sync_committee`
    # [Modified in PQ]
    # Removed `next_sync_committee`
    latest_block_hash: Hash32
    next_withdrawal_index: WithdrawalIndex
    next_withdrawal_validator_index: ValidatorIndex
    historical_summaries: HistoricalSummaries
    deposit_requests_start_index: Uint64
    deposit_balance_to_consume: Gwei
    exit_balance_to_consume: Gwei
    earliest_exit_epoch: Epoch
    consolidation_balance_to_consume: Gwei
    earliest_consolidation_epoch: Epoch
    pending_deposits: PendingDeposits
    pending_partial_withdrawals: PendingPartialWithdrawals
    pending_consolidations: PendingConsolidations
    proposer_lookahead: ProposerLookahead
    builders: Builders
    next_withdrawal_builder_index: BuilderIndex
    execution_payload_availability: ExecutionPayloadAvailability
    builder_pending_payments: BuilderPendingPayments
    builder_pending_withdrawals: BuilderPendingWithdrawals
    latest_execution_payload_bid: ExecutionPayloadBid
    payload_expected_withdrawals: Withdrawals
    ptc_window: PayloadTimelinessCommitteeWindow
    # [Modified in PQ]
    # Removed `pq_registrations`
    # [New in PQ]
    pq_data: PQDataList
```

#### `ExecutionRequests`

```python
class ExecutionRequests(ProgressiveContainer):
    ACTIVE_FIELDS = active_fields(width=5, gaps=(2,))

    deposits: DepositRequests
    withdrawals: WithdrawalRequests
    # [Modified in PQ]
    # Removed `consolidations`
    builder_deposits: BuilderDepositRequests
    builder_exits: BuilderExitRequests
    # [Modified in PQ]
    # Removed `pq_registrations`
```

#### `IndexedAttestation`

```python
class IndexedAttestation(ProgressiveContainer):
    ACTIVE_FIELDS = active_fields(width=3)

    attesting_indices: AttestingIndices
    data: AttestationData
    # [Modified in PQ]
    signature: XMSSAggregateSignature
```

#### `PayloadAttestationMessage`

```python
class PayloadAttestationMessage(Container):
    validator_index: ValidatorIndex
    data: PayloadAttestationData
    # [Modified in PQ]
    signature: XMSSSignature
```

#### `SignedBeaconBlock`

```python
class SignedBeaconBlock(Container):
    message: BeaconBlock
    # [Modified in PQ]
    signature: XMSSSignature
```

#### `SignedBeaconBlockHeader`

```python
class SignedBeaconBlockHeader(Container):
    message: BeaconBlockHeader
    # [Modified in PQ]
    signature: XMSSSignature
```

#### `SignedExecutionPayloadBid`

```python
class SignedExecutionPayloadBid(Container):
    message: ExecutionPayloadBid
    # [Modified in PQ]
    signature: XMSSSignature
```

#### `SignedExecutionPayloadEnvelope`

```python
class SignedExecutionPayloadEnvelope(Container):
    message: ExecutionPayloadEnvelope
    # [Modified in PQ]
    signature: XMSSSignature
```

#### `SignedVoluntaryExit`

```python
class SignedVoluntaryExit(Container):
    message: VoluntaryExit
    # [Modified in PQ]
    signature: XMSSSignature
```

#### `SingleAttestation`

```python
class SingleAttestation(Container):
    committee_index: CommitteeIndex
    attester_index: ValidatorIndex
    data: AttestationData
    # [Modified in PQ]
    signature: XMSSSignature
```

### New containers

#### `PQData`

```python
class PQData(Container):
    role: Uint8
    bls_pubkey: BLSPubkey
    xmss_pubkey: XMSSPubkey
    vrf_data: Bytes32
```

## Helpers

### Crypto

#### XMSS signatures

[leanXMSS](https://github.com/ethereum/ethlib/tree/main/EthLib/Cryptography/Xmss)
defines the following functions:

- `def Sign(privkey: Bytes32, leaf_index: Uint64, message: Bytes32) -> XMSSSignature`
- `def Verify(pubkey: XMSSPubkey, leaf_index: Uint64, message: Bytes32, signature: XMSSSignature) -> bool`

`Verify` returns `True` only if `signature` was produced at `leaf_index`. This
upgrade adds the following functions for aggregation:

- `def Aggregate(signatures: Sequence[XMSSSignature | XMSSAggregateSignature]) -> XMSSAggregateSignature`
- `def AggregateVerify(pubkeys: Sequence[XMSSPubkey], leaf_index: Uint64, message: Bytes32, signature: XMSSAggregateSignature) -> bool`

`Aggregate` combines signatures and aggregates over the same message at the same
leaf. `AggregateVerify` returns `True` only if `signature` holds exactly one
valid signature at `leaf_index` for each entry of `pubkeys`, in any order. A
public key that appears more than once needs one signature per appearance. An
empty aggregate is valid for an empty `pubkeys`.

The above functions are accessed through the `xmss` module, e.g. `xmss.Verify`.

*Note*: The reference implementation of `Aggregate` concatenates its inputs. It
stands in for a succinct aggregation scheme, which would change the encoding of
`XMSSAggregateSignature` but not how these functions are used.

### Misc

#### New `compute_xmss_leaf_index`

*Note*: A key covers `2**32` leaves, so it lasts `2**32 // XMSS_LEAVES_PER_SLOT`
slots.

```python
def compute_xmss_leaf_index(slot: Slot, leaf_offset: Uint64) -> Uint64:
    """
    Return the XMSS leaf at which a message of the type given by ``leaf_offset``
    is signed for ``slot``.
    """
    return Uint64(slot * XMSS_LEAVES_PER_SLOT + leaf_offset)
```

### Predicates

#### Modified `is_valid_indexed_attestation`

```python
def is_valid_indexed_attestation(
    state: BeaconState, indexed_attestation: IndexedAttestation
) -> bool:
    """
    Check if ``indexed_attestation`` is not empty, has sorted and unique indices and has a valid aggregate signature.
    """
    # Verify indices are sorted and unique
    indices = indexed_attestation.attesting_indices
    if (
        len(indices) == 0
        or len(indices) > MAX_VALIDATORS_PER_COMMITTEE * MAX_COMMITTEES_PER_SLOT
        or list(indices) != sorted(set(indices))
    ):
        return False
    # Verify aggregate signature
    # [Modified in PQ]
    pubkeys = [
        get_xmss_pubkey(state, PQ_REGISTRATION_ROLE_VALIDATOR, state.validators[index].pubkey)
        for index in indices
    ]
    domain = get_domain(state, DOMAIN_BEACON_ATTESTER, indexed_attestation.data.target.epoch)
    signing_root = compute_signing_root(indexed_attestation.data, domain)
    # [Modified in PQ]
    leaf_index = compute_xmss_leaf_index(indexed_attestation.data.slot, LEAF_OFFSET_BEACON_ATTESTER)
    return xmss.AggregateVerify(pubkeys, leaf_index, signing_root, indexed_attestation.signature)
```

### Beacon state accessors

#### New `get_xmss_pubkey`

*Note*: The linear scan is for specification clarity. Implementations SHOULD
cache the XMSS public key of each validator and builder.

```python
def get_xmss_pubkey(state: BeaconState, role: Uint8, bls_pubkey: BLSPubkey) -> XMSSPubkey:
    """
    Return the XMSS public key registered for ``bls_pubkey`` with ``role``, or
    the empty public key, which no signature verifies against, if there is none.
    """
    for entry in state.pq_data:
        if entry.role == role and entry.bls_pubkey == bls_pubkey:
            return entry.xmss_pubkey
    return XMSSPubkey()
```

## Beacon chain state transition function

### Modified `verify_block_signature`

```python
def verify_block_signature(state: BeaconState, signed_block: SignedBeaconBlock) -> bool:
    proposer = state.validators[signed_block.message.proposer_index]
    signing_root = compute_signing_root(
        signed_block.message, get_domain(state, DOMAIN_BEACON_PROPOSER)
    )
    # [Modified in PQ]
    leaf_index = compute_xmss_leaf_index(signed_block.message.slot, LEAF_OFFSET_BEACON_PROPOSER)
    pubkey = get_xmss_pubkey(state, PQ_REGISTRATION_ROLE_VALIDATOR, proposer.pubkey)
    return xmss.Verify(pubkey, leaf_index, signing_root, signed_block.signature)
```

### Epoch processing

#### Modified `process_epoch`

```python
def process_epoch(state: BeaconState) -> None:
    process_justification_and_finalization(state)
    process_inactivity_updates(state)
    process_rewards_and_penalties(state)
    process_registry_updates(state)
    process_slashings(state)
    process_eth1_data_reset(state)
    process_pending_deposits(state)
    process_pending_consolidations(state)
    process_builder_pending_payments(state)
    process_effective_balance_updates(state)
    process_slashings_reset(state)
    process_randao_mixes_reset(state)
    process_historical_summaries_update(state)
    process_participation_flag_updates(state)
    # [Modified in PQ]
    # Removed `process_sync_committee_updates`
    process_proposer_lookahead(state)
    process_ptc_window(state)
```

### Block processing

#### Modified `process_block`

*Note*: Without sync aggregates, the sync committee rewards are no longer
issued, which lowers issuance by `SYNC_REWARD_WEIGHT / WEIGHT_DENOMINATOR`.

```python
def process_block(state: BeaconState, block: BeaconBlock) -> None:
    parent_slot = state.latest_block_header.slot
    process_parent_execution_payload(state, block)
    process_block_header(state, block)
    process_withdrawals(state)
    process_execution_payload_bid(state, block.body.signed_execution_payload_bid)
    process_randao(state, block.body)
    process_eth1_data(state, block.body)
    process_operations(state, block.body, parent_slot)
    # [Modified in PQ]
    # Removed `process_sync_aggregate`
```

#### Modified `process_randao`

*Note*: XMSS signatures are not unique. A proposer can grind the randomizer of
its reveal to bias the RANDAO mix, which BLS uniqueness used to prevent. A
hash-based commit-reveal such as EIP-8321 would close this gap.

```python
def process_randao(state: BeaconState, body: BeaconBlockBody) -> None:
    epoch = get_current_epoch(state)
    # Verify RANDAO reveal
    proposer = state.validators[get_beacon_proposer_index(state)]
    signing_root = compute_signing_root(epoch, get_domain(state, DOMAIN_RANDAO))
    # [Modified in PQ]
    leaf_index = compute_xmss_leaf_index(state.slot, LEAF_OFFSET_RANDAO)
    pubkey = get_xmss_pubkey(state, PQ_REGISTRATION_ROLE_VALIDATOR, proposer.pubkey)
    assert xmss.Verify(pubkey, leaf_index, signing_root, body.randao_reveal)
    # Mix in RANDAO reveal
    mix = xor(get_randao_mix(state, epoch), sha256(body.randao_reveal))
    state.randao_mixes[epoch % EPOCHS_PER_HISTORICAL_VECTOR] = mix
```

#### Execution payload

##### Modified `get_execution_requests_list`

*Note*: Encodes execution requests as defined by
[EIP-7685](https://eips.ethereum.org/EIPS/eip-7685).

```python
def get_execution_requests_list(execution_requests: ExecutionRequests) -> Sequence[bytes]:
    requests: Sequence[tuple[Bytes1, ProgressiveList]] = [
        (DEPOSIT_REQUEST_TYPE, execution_requests.deposits),
        (WITHDRAWAL_REQUEST_TYPE, execution_requests.withdrawals),
        # [Modified in PQ]
        # Removed `CONSOLIDATION_REQUEST_TYPE`
        (BUILDER_DEPOSIT_REQUEST_TYPE, execution_requests.builder_deposits),
        (BUILDER_EXIT_REQUEST_TYPE, execution_requests.builder_exits),
        # [Modified in PQ]
        # Removed `PQ_REGISTRATION_REQUEST_TYPE`
    ]

    return [
        request_type + ssz_serialize(request_data)
        for request_type, request_data in requests
        if len(request_data) != 0
    ]
```

##### Modified `verify_execution_payload_envelope_signature`

```python
def verify_execution_payload_envelope_signature(
    state: BeaconState, signed_envelope: SignedExecutionPayloadEnvelope
) -> bool:
    builder_index = signed_envelope.message.builder_index
    if builder_index == BUILDER_INDEX_SELF_BUILD:
        validator_index = state.latest_block_header.proposer_index
        # [Modified in PQ]
        pubkey = get_xmss_pubkey(
            state, PQ_REGISTRATION_ROLE_VALIDATOR, state.validators[validator_index].pubkey
        )
    else:
        # [Modified in PQ]
        pubkey = get_xmss_pubkey(
            state, PQ_REGISTRATION_ROLE_BUILDER, state.builders[builder_index].pubkey
        )

    signing_root = compute_signing_root(
        signed_envelope.message, get_domain(state, DOMAIN_BEACON_BUILDER)
    )
    # [Modified in PQ]
    leaf_index = compute_xmss_leaf_index(
        state.latest_block_header.slot, LEAF_OFFSET_EXECUTION_PAYLOAD_ENVELOPE
    )
    return xmss.Verify(pubkey, leaf_index, signing_root, signed_envelope.signature)
```

#### Execution payload bid

##### Modified `verify_execution_payload_bid_signature`

```python
def verify_execution_payload_bid_signature(
    state: BeaconState, signed_bid: SignedExecutionPayloadBid
) -> bool:
    builder = state.builders[signed_bid.message.builder_index]
    signing_root = compute_signing_root(
        signed_bid.message, get_domain(state, DOMAIN_BEACON_BUILDER)
    )
    # [Modified in PQ]
    leaf_index = compute_xmss_leaf_index(signed_bid.message.slot, LEAF_OFFSET_EXECUTION_PAYLOAD_BID)
    pubkey = get_xmss_pubkey(state, PQ_REGISTRATION_ROLE_BUILDER, builder.pubkey)
    return xmss.Verify(pubkey, leaf_index, signing_root, signed_bid.signature)
```

##### Modified `process_execution_payload_bid`

*Note*: Blobs are disabled, so a bid must not commit to any blobs.

```python
def process_execution_payload_bid(
    state: BeaconState, signed_bid: SignedExecutionPayloadBid
) -> None:
    bid = signed_bid.message
    builder_index = bid.builder_index
    amount = bid.value

    # For self-builds, amount must be zero regardless of withdrawal credential prefix
    if builder_index == BUILDER_INDEX_SELF_BUILD:
        assert amount == 0
        # [Modified in PQ]
        assert signed_bid.signature == XMSSSignature()
    else:
        # Verify that the builder is active
        assert is_active_builder(state, builder_index)
        # Verify that the builder is a payload builder
        assert state.builders[builder_index].version == PAYLOAD_BUILDER_VERSION
        # Verify that the builder has funds to cover the bid
        assert can_builder_cover_bid(state, builder_index, amount)
        # Verify that the bid signature is valid
        assert verify_execution_payload_bid_signature(state, signed_bid)

    # [Modified in PQ]
    # Verify there are no blob commitments
    assert len(bid.blob_kzg_commitments) == 0

    # Verify that the bid is for the current slot
    assert bid.slot == state.slot
    assert state.slot > GENESIS_SLOT
    # Verify that the bid is for the right parent block
    assert bid.parent_block_hash == state.latest_block_hash
    # Verify that the bid's block hash differs from its parent block hash
    assert bid.block_hash != bid.parent_block_hash
    assert bid.parent_block_root == get_block_root_at_slot(state, state.slot - 1)
    assert bid.prev_randao == get_randao_mix(state, get_current_epoch(state))

    # Record the pending payment if there is some payment
    if amount > 0:
        pending_payment = BuilderPendingPayment(
            weight=Gwei(0),
            withdrawal=BuilderPendingWithdrawal(
                fee_recipient=bid.fee_recipient,
                amount=amount,
                builder_index=builder_index,
            ),
            proposer_index=get_beacon_proposer_index(state),
        )
        state.builder_pending_payments[SLOTS_PER_EPOCH + bid.slot % SLOTS_PER_EPOCH] = (
            pending_payment
        )

    # Cache the signed execution payload bid
    state.latest_execution_payload_bid = bid
```

#### Operations

##### Modified `process_operations`

```python
def process_operations(state: BeaconState, body: BeaconBlockBody, parent_slot: Slot) -> None:
    assert len(body.deposits) == 0

    def for_ops(operations: Sequence[Any], fn: Callable[..., None], *args: Any) -> None:
        for operation in operations:
            fn(state, operation, *args)

    assert len(body.proposer_slashings) <= MAX_PROPOSER_SLASHINGS
    assert len(body.attester_slashings) <= MAX_ATTESTER_SLASHINGS_ELECTRA
    # [Modified in PQ]
    assert len(body.attestations) <= MAX_ATTESTATIONS_PQ
    assert len(body.voluntary_exits) <= MAX_VOLUNTARY_EXITS
    # [Modified in PQ]
    # Removed the BLS to execution change limit
    # [Modified in PQ]
    # Removed the payload attestation limit

    for_ops(body.proposer_slashings, process_proposer_slashing)
    for_ops(body.attester_slashings, process_attester_slashing)
    for_ops(body.attestations, process_attestation, parent_slot)
    for_ops(body.voluntary_exits, process_voluntary_exit)
    # [Modified in PQ]
    # Removed `process_bls_to_execution_change`
    # [Modified in PQ]
    # Removed `process_payload_attestation`
```

##### Modified `process_proposer_slashing`

*Note*: Both headers are signed at the same leaf, which exposes that leaf of the
proposer's key. The leaf belongs to a past slot and the proposer is slashed.

```python
def process_proposer_slashing(state: BeaconState, proposer_slashing: ProposerSlashing) -> None:
    header_1 = proposer_slashing.signed_header_1.message
    header_2 = proposer_slashing.signed_header_2.message

    # Verify header slots match
    assert header_1.slot == header_2.slot
    # Verify header proposer indices match
    assert header_1.proposer_index == header_2.proposer_index
    # Verify the headers are different
    assert header_1 != header_2
    # Verify the proposer is slashable
    proposer = state.validators[header_1.proposer_index]
    assert is_slashable_validator(proposer, get_current_epoch(state))
    # Verify signatures
    for signed_header in (proposer_slashing.signed_header_1, proposer_slashing.signed_header_2):
        domain = get_domain(
            state, DOMAIN_BEACON_PROPOSER, compute_epoch_at_slot(signed_header.message.slot)
        )
        signing_root = compute_signing_root(signed_header.message, domain)
        # [Modified in PQ]
        leaf_index = compute_xmss_leaf_index(
            signed_header.message.slot, LEAF_OFFSET_BEACON_PROPOSER
        )
        pubkey = get_xmss_pubkey(state, PQ_REGISTRATION_ROLE_VALIDATOR, proposer.pubkey)
        assert xmss.Verify(pubkey, leaf_index, signing_root, signed_header.signature)

    slash_validator(state, header_1.proposer_index)
```

##### Modified `process_voluntary_exit`

```python
def process_voluntary_exit(state: BeaconState, signed_voluntary_exit: SignedVoluntaryExit) -> None:
    voluntary_exit = signed_voluntary_exit.message
    validator = state.validators[voluntary_exit.validator_index]
    # Verify the validator is active
    assert is_active_validator(validator, get_current_epoch(state))
    # Verify exit has not been initiated
    assert validator.exit_epoch == FAR_FUTURE_EPOCH
    # Exits must specify an epoch when they become valid; they are not valid before then
    assert get_current_epoch(state) >= voluntary_exit.epoch
    # Verify the validator has been active long enough
    assert get_current_epoch(state) >= validator.activation_epoch + SHARD_COMMITTEE_PERIOD
    # Only exit validator if it has no pending withdrawals in the queue
    assert get_pending_balance_to_withdraw(state, voluntary_exit.validator_index) == 0
    # Verify signature
    domain = compute_domain(
        DOMAIN_VOLUNTARY_EXIT, CAPELLA_FORK_VERSION, state.genesis_validators_root
    )
    signing_root = compute_signing_root(voluntary_exit, domain)
    # [Modified in PQ]
    leaf_index = compute_xmss_leaf_index(
        compute_start_slot_at_epoch(voluntary_exit.epoch), LEAF_OFFSET_VOLUNTARY_EXIT
    )
    pubkey = get_xmss_pubkey(state, PQ_REGISTRATION_ROLE_VALIDATOR, validator.pubkey)
    assert xmss.Verify(pubkey, leaf_index, signing_root, signed_voluntary_exit.signature)
    # Initiate exit
    initiate_validator_exit(state, voluntary_exit.validator_index)
```

#### Parent execution payload

##### Modified `apply_parent_execution_payload`

*Note*: This function queues the builder payment, processes the parent's
execution requests, updates payload availability, and updates the latest block
hash. It is called by `process_parent_execution_payload` during block processing
and by the validator during block production before computing withdrawals.

```python
def apply_parent_execution_payload(
    state: BeaconState,
    requests: ExecutionRequests,
) -> None:
    parent_bid = state.latest_execution_payload_bid
    parent_slot = state.latest_block_header.slot
    parent_epoch = compute_epoch_at_slot(parent_slot)

    assert len(requests.withdrawals) <= MAX_WITHDRAWAL_REQUESTS_PER_PAYLOAD
    # [Modified in PQ]
    # Removed the consolidation request limit
    assert len(requests.builder_deposits) <= MAX_BUILDER_DEPOSIT_REQUESTS_PER_PAYLOAD
    assert len(requests.builder_exits) <= MAX_BUILDER_EXIT_REQUESTS_PER_PAYLOAD
    # [Modified in PQ]
    # Removed the PQ registration request limit

    # Settle the builder payment before the requests so that a builder exit
    # request is rejected while the payment is pending
    if parent_epoch == get_current_epoch(state):
        payment_index = SLOTS_PER_EPOCH + parent_slot % SLOTS_PER_EPOCH
        settle_builder_payment(state, payment_index)
    elif parent_epoch == get_previous_epoch(state):
        payment_index = parent_slot % SLOTS_PER_EPOCH
        settle_builder_payment(state, payment_index)
    elif parent_bid.value > 0:
        # Parent is older than the previous epoch, its payment entry has been
        # evicted from builder_pending_payments. Append the withdrawal directly.
        state.builder_pending_withdrawals.append(
            BuilderPendingWithdrawal(
                fee_recipient=parent_bid.fee_recipient,
                amount=parent_bid.value,
                builder_index=parent_bid.builder_index,
            )
        )

    # Process execution requests from parent's payload. The execution
    # requests are processed at state.slot (child's slot), not the parent's slot.
    def for_ops(operations: Sequence[Any], fn: Callable[[BeaconState, Any], None]) -> None:
        for operation in operations:
            fn(state, operation)

    for_ops(requests.deposits, process_deposit_request)
    for_ops(requests.withdrawals, process_withdrawal_request)
    # [Modified in PQ]
    # Removed `process_consolidation_request`
    for_ops(requests.builder_deposits, process_builder_deposit_request)
    for_ops(requests.builder_exits, process_builder_exit_request)
    # [Modified in PQ]
    # Removed `process_pq_registration_request`

    # Update parent payload availability and latest block hash
    state.execution_payload_availability[parent_slot % SLOTS_PER_HISTORICAL_ROOT] = Boolean(True)
    state.latest_block_hash = parent_bid.block_hash
```
