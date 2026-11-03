# PQ -- The Beacon Chain

*Note*: This document is a work-in-progress for researchers and implementers.

<!-- mdformat-toc start --slug=github --no-anchors --maxlevel=6 --minlevel=2 -->

- [Introduction](#introduction)
- [Types](#types)
  - [Modified `SyncCommitteePubkeys`](#modified-synccommitteepubkeys)
  - [New `XMSSAggregateSignature`](#new-xmssaggregatesignature)
  - [New `XMSSPubkey`](#new-xmsspubkey)
  - [New `XMSSSignature`](#new-xmsssignature)
- [Constants](#constants)
  - [XMSS](#xmss)
  - [XMSS leaf offsets](#xmss-leaf-offsets)
- [Presets](#presets)
  - [XMSS](#xmss-1)
- [Containers](#containers)
  - [Modified containers](#modified-containers)
    - [`Attestation`](#attestation)
    - [`BeaconBlockBody`](#beaconblockbody)
    - [`BeaconState`](#beaconstate)
    - [`Builder`](#builder)
    - [`BuilderDepositRequest`](#builderdepositrequest)
    - [`BuilderExitRequest`](#builderexitrequest)
    - [`ConsolidationRequest`](#consolidationrequest)
    - [`DepositData`](#depositdata)
    - [`DepositMessage`](#depositmessage)
    - [`DepositRequest`](#depositrequest)
    - [`ExecutionRequests`](#executionrequests)
    - [`IndexedAttestation`](#indexedattestation)
    - [`IndexedPayloadAttestation`](#indexedpayloadattestation)
    - [`PayloadAttestation`](#payloadattestation)
    - [`PayloadAttestationMessage`](#payloadattestationmessage)
    - [`PendingDeposit`](#pendingdeposit)
    - [`SignedBeaconBlock`](#signedbeaconblock)
    - [`SignedBeaconBlockHeader`](#signedbeaconblockheader)
    - [`SignedExecutionPayloadBid`](#signedexecutionpayloadbid)
    - [`SignedExecutionPayloadEnvelope`](#signedexecutionpayloadenvelope)
    - [`SignedVoluntaryExit`](#signedvoluntaryexit)
    - [`SingleAttestation`](#singleattestation)
    - [`SyncAggregate`](#syncaggregate)
    - [`SyncCommittee`](#synccommittee)
    - [`Validator`](#validator)
    - [`WithdrawalRequest`](#withdrawalrequest)
- [Helpers](#helpers)
  - [Crypto](#crypto)
    - [XMSS signatures](#xmss-signatures)
  - [Misc](#misc)
    - [New `compute_xmss_leaf_index`](#new-compute_xmss_leaf_index)
  - [Predicates](#predicates)
    - [Modified `is_valid_indexed_attestation`](#modified-is_valid_indexed_attestation)
    - [Modified `is_valid_indexed_payload_attestation`](#modified-is_valid_indexed_payload_attestation)
    - [Modified `is_pending_validator`](#modified-is_pending_validator)
  - [Beacon state accessors](#beacon-state-accessors)
    - [Modified `get_next_sync_committee`](#modified-get_next_sync_committee)
  - [Beacon state mutators](#beacon-state-mutators)
    - [Modified `queue_excess_active_balance`](#modified-queue_excess_active_balance)
  - [Validator registry](#validator-registry)
    - [Modified `get_validator_from_deposit`](#modified-get_validator_from_deposit)
    - [Modified `add_validator_to_registry`](#modified-add_validator_to_registry)
    - [Modified `add_builder_to_registry`](#modified-add_builder_to_registry)
- [Beacon chain state transition function](#beacon-chain-state-transition-function)
  - [Modified `verify_block_signature`](#modified-verify_block_signature)
  - [Block processing](#block-processing)
    - [Modified `process_randao`](#modified-process_randao)
    - [Execution payload](#execution-payload)
      - [Modified `get_execution_requests_list`](#modified-get_execution_requests_list)
      - [Modified `verify_execution_payload_envelope_signature`](#modified-verify_execution_payload_envelope_signature)
    - [Execution payload bid](#execution-payload-bid)
      - [Modified `verify_execution_payload_bid_signature`](#modified-verify_execution_payload_bid_signature)
      - [Modified `process_execution_payload_bid`](#modified-process_execution_payload_bid)
    - [Operations](#operations)
      - [Modified `process_proposer_slashing`](#modified-process_proposer_slashing)
      - [Modified `process_voluntary_exit`](#modified-process_voluntary_exit)
      - [Deposit requests](#deposit-requests)
        - [Modified `is_valid_deposit_signature`](#modified-is_valid_deposit_signature)
      - [Builder deposit requests](#builder-deposit-requests)
        - [Modified `is_valid_builder_deposit_signature`](#modified-is_valid_builder_deposit_signature)
    - [Sync aggregate processing](#sync-aggregate-processing)
      - [Modified `process_sync_aggregate`](#modified-process_sync_aggregate)
    - [Parent execution payload](#parent-execution-payload)
      - [Modified `apply_parent_execution_payload`](#modified-apply_parent_execution_payload)

<!-- mdformat-toc end -->

## Introduction

This upgrade replaces the BLS signatures used by validators and builders with
leanXMSS, a hash-based signature scheme believed to be secure against a quantum
adversary.

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

Validators move to XMSS keys through the post-quantum material registered with
EIP-8483 before the fork. Each registration holds the validator's XMSS public
key. Validators that did not register are exited at the fork. See
[the fork document](./fork.md) for details.

`BLSToExecutionChange` keeps its BLS signature, because it is signed with the
withdrawal key rather than the validator's signing key, and is the only way to
move funds out of `0x00` withdrawal credentials.

*Note*: This specification is built upon [EIP-8483](../eip8483/beacon-chain.md),
which is built upon [Gloas](../../gloas/beacon-chain.md).

## Types

### Modified `SyncCommitteePubkeys`

```python
# [Modified in PQ]
class SyncCommitteePubkeys(Vector[XMSSPubkey]):
    """
    The public keys of the sync committee members, in committee order.
    """

    LENGTH = SYNC_COMMITTEE_SIZE
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
| `XMSS_LEAVES_PER_SLOT` | `Uint64(2**5)` (= 32) |

### XMSS leaf offsets

*Note*: The two sync committee offsets are each followed by one leaf per sync
subcommittee, so that a validator in several subcommittees signs each one at its
own leaf.

| Name                                         | Value        |
| -------------------------------------------- | ------------ |
| `LEAF_OFFSET_BEACON_PROPOSER`                | `Uint64(0)`  |
| `LEAF_OFFSET_RANDAO`                         | `Uint64(1)`  |
| `LEAF_OFFSET_BEACON_ATTESTER`                | `Uint64(2)`  |
| `LEAF_OFFSET_SELECTION_PROOF`                | `Uint64(3)`  |
| `LEAF_OFFSET_AGGREGATE_AND_PROOF`            | `Uint64(4)`  |
| `LEAF_OFFSET_SYNC_COMMITTEE`                 | `Uint64(5)`  |
| `LEAF_OFFSET_PTC_ATTESTER`                   | `Uint64(6)`  |
| `LEAF_OFFSET_PROPOSER_PREFERENCES`           | `Uint64(7)`  |
| `LEAF_OFFSET_EXECUTION_PAYLOAD_BID`          | `Uint64(8)`  |
| `LEAF_OFFSET_EXECUTION_PAYLOAD_ENVELOPE`     | `Uint64(9)`  |
| `LEAF_OFFSET_VOLUNTARY_EXIT`                 | `Uint64(10)` |
| `LEAF_OFFSET_DEPOSIT`                        | `Uint64(11)` |
| `LEAF_OFFSET_SYNC_COMMITTEE_SELECTION_PROOF` | `Uint64(12)` |
| `LEAF_OFFSET_CONTRIBUTION_AND_PROOF`         | `Uint64(16)` |

## Presets

### XMSS

| Name                                | Value                         | Description                                                        |
| ----------------------------------- | ----------------------------- | ------------------------------------------------------------------ |
| `MAX_XMSS_AGGREGATE_SIGNATURE_SIZE` | `Uint64(2**20)` (= 1,048,576) | *[New in PQ]* Maximum size in bytes of an aggregate XMSS signature |

*Note*: `MAX_XMSS_AGGREGATE_SIGNATURE_SIZE` is a placeholder for the proof size
of a succinct aggregation scheme. The reference concatenation fits at most
`MAX_XMSS_AGGREGATE_SIGNATURE_SIZE // XMSS_SIGNATURE_SIZE` signatures.

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
    ACTIVE_FIELDS = active_fields(width=13)

    # [Modified in PQ]
    randao_reveal: XMSSSignature
    eth1_data: Eth1Data
    graffiti: Bytes32
    proposer_slashings: ProposerSlashings
    attester_slashings: AttesterSlashings
    attestations: Attestations
    deposits: Deposits
    voluntary_exits: VoluntaryExits
    sync_aggregate: SyncAggregate
    bls_to_execution_changes: BLSToExecutionChanges
    signed_execution_payload_bid: SignedExecutionPayloadBid
    payload_attestations: PayloadAttestations
    parent_execution_requests: ExecutionRequests
```

#### `BeaconState`

```python
class BeaconState(ProgressiveContainer):
    ACTIVE_FIELDS = active_fields(width=46)

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
    current_sync_committee: SyncCommittee
    next_sync_committee: SyncCommittee
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
    # [Modified in PQ]
    # Removed `builder_pq_registrations`
```

#### `Builder`

```python
class Builder(Container):
    # [Modified in PQ]
    pubkey: XMSSPubkey
    version: Uint8
    execution_address: ExecutionAddress
    balance: Gwei
    deposit_epoch: Epoch
    withdrawable_epoch: Epoch
```

#### `BuilderDepositRequest`

```python
class BuilderDepositRequest(Container):
    # [Modified in PQ]
    pubkey: XMSSPubkey
    withdrawal_credentials: Bytes32
    amount: Gwei
    # [Modified in PQ]
    signature: XMSSSignature
```

#### `BuilderExitRequest`

```python
class BuilderExitRequest(Container):
    source_address: ExecutionAddress
    # [Modified in PQ]
    pubkey: XMSSPubkey
```

#### `ConsolidationRequest`

```python
class ConsolidationRequest(Container):
    source_address: ExecutionAddress
    # [Modified in PQ]
    source_pubkey: XMSSPubkey
    # [Modified in PQ]
    target_pubkey: XMSSPubkey
```

#### `DepositData`

*Note*: `signature` is over `DepositMessage`.

```python
class DepositData(Container):
    # [Modified in PQ]
    pubkey: XMSSPubkey
    withdrawal_credentials: Bytes32
    amount: Gwei
    # [Modified in PQ]
    signature: XMSSSignature
```

#### `DepositMessage`

```python
class DepositMessage(Container):
    # [Modified in PQ]
    pubkey: XMSSPubkey
    withdrawal_credentials: Bytes32
    amount: Gwei
```

#### `DepositRequest`

```python
class DepositRequest(Container):
    # [Modified in PQ]
    pubkey: XMSSPubkey
    withdrawal_credentials: Bytes32
    amount: Gwei
    # [Modified in PQ]
    signature: XMSSSignature
    index: Uint64
```

#### `ExecutionRequests`

```python
class ExecutionRequests(ProgressiveContainer):
    ACTIVE_FIELDS = active_fields(width=5)

    deposits: DepositRequests
    withdrawals: WithdrawalRequests
    consolidations: ConsolidationRequests
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

#### `IndexedPayloadAttestation`

```python
class IndexedPayloadAttestation(ProgressiveContainer):
    ACTIVE_FIELDS = active_fields(width=3)

    attesting_indices: PayloadTimelinessCommitteeIndices
    data: PayloadAttestationData
    # [Modified in PQ]
    signature: XMSSAggregateSignature
```

#### `PayloadAttestation`

```python
class PayloadAttestation(ProgressiveContainer):
    ACTIVE_FIELDS = active_fields(width=3)

    aggregation_bits: PayloadTimelinessCommitteeBits
    data: PayloadAttestationData
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

#### `PendingDeposit`

```python
class PendingDeposit(Container):
    # [Modified in PQ]
    pubkey: XMSSPubkey
    withdrawal_credentials: Bytes32
    amount: Gwei
    # [Modified in PQ]
    signature: XMSSSignature
    slot: Slot
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

#### `SyncAggregate`

```python
class SyncAggregate(Container):
    sync_committee_bits: SyncCommitteeBits
    # [Modified in PQ]
    sync_committee_signature: XMSSAggregateSignature
```

#### `SyncCommittee`

```python
class SyncCommittee(Container):
    pubkeys: SyncCommitteePubkeys
    # [Modified in PQ]
    # Removed `aggregate_pubkey`
```

#### `Validator`

```python
class Validator(Container):
    # [Modified in PQ]
    pubkey: XMSSPubkey
    withdrawal_credentials: Bytes32
    effective_balance: Gwei
    slashed: Boolean
    activation_eligibility_epoch: Epoch
    activation_epoch: Epoch
    exit_epoch: Epoch
    withdrawable_epoch: Epoch
```

#### `WithdrawalRequest`

```python
class WithdrawalRequest(Container):
    source_address: ExecutionAddress
    # [Modified in PQ]
    validator_pubkey: XMSSPubkey
    amount: Gwei
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
    pubkeys = [state.validators[index].pubkey for index in indices]
    domain = get_domain(state, DOMAIN_BEACON_ATTESTER, indexed_attestation.data.target.epoch)
    signing_root = compute_signing_root(indexed_attestation.data, domain)
    # [Modified in PQ]
    leaf_index = compute_xmss_leaf_index(indexed_attestation.data.slot, LEAF_OFFSET_BEACON_ATTESTER)
    return xmss.AggregateVerify(pubkeys, leaf_index, signing_root, indexed_attestation.signature)
```

#### Modified `is_valid_indexed_payload_attestation`

```python
def is_valid_indexed_payload_attestation(
    state: BeaconState, attestation: IndexedPayloadAttestation
) -> bool:
    """
    Check if ``attestation`` is non-empty, has sorted indices, and has
    a valid aggregate signature.
    """
    # Verify indices are non-empty and sorted
    indices = attestation.attesting_indices
    if len(indices) == 0 or list(indices) != sorted(indices):
        return False

    # Verify aggregate signature
    pubkeys = [state.validators[index].pubkey for index in indices]
    domain = get_domain(state, DOMAIN_PTC_ATTESTER, compute_epoch_at_slot(attestation.data.slot))
    signing_root = compute_signing_root(attestation.data, domain)
    # [Modified in PQ]
    leaf_index = compute_xmss_leaf_index(attestation.data.slot, LEAF_OFFSET_PTC_ATTESTER)
    return xmss.AggregateVerify(pubkeys, leaf_index, signing_root, attestation.signature)
```

#### Modified `is_pending_validator`

*Note*: This function naively revalidates deposit signatures on every call.
Implementations SHOULD cache verification results to avoid repeated work.

```python
def is_pending_validator(
    pending_deposits: Sequence[PendingDeposit],
    # [Modified in PQ]
    pubkey: XMSSPubkey,
) -> bool:
    """
    Check if a pending deposit with a valid signature is in the queue for the given pubkey.
    """
    for pending_deposit in pending_deposits:
        if pending_deposit.pubkey != pubkey:
            continue
        if is_valid_deposit_signature(
            pending_deposit.pubkey,
            pending_deposit.withdrawal_credentials,
            pending_deposit.amount,
            pending_deposit.signature,
        ):
            return True
    return False
```

### Beacon state accessors

#### Modified `get_next_sync_committee`

```python
def get_next_sync_committee(state: BeaconState) -> SyncCommittee:
    """
    Return the next sync committee, with possible pubkey duplicates.
    """
    indices = get_next_sync_committee_indices(state)
    pubkeys = SyncCommitteePubkeys(data=[state.validators[index].pubkey for index in indices])
    # [Modified in PQ]
    # Removed `aggregate_pubkey`
    return SyncCommittee(pubkeys=pubkeys)
```

### Beacon state mutators

#### Modified `queue_excess_active_balance`

```python
def queue_excess_active_balance(state: BeaconState, index: ValidatorIndex) -> None:
    balance = state.balances[index]
    if balance > MIN_ACTIVATION_BALANCE:
        excess_balance = balance - MIN_ACTIVATION_BALANCE
        state.balances[index] = MIN_ACTIVATION_BALANCE
        validator = state.validators[index]
        # Use an empty signature as a signature field placeholder
        # and GENESIS_SLOT to distinguish from a pending deposit request
        state.pending_deposits.append(
            PendingDeposit(
                pubkey=validator.pubkey,
                withdrawal_credentials=validator.withdrawal_credentials,
                amount=excess_balance,
                # [Modified in PQ]
                signature=XMSSSignature(),
                slot=GENESIS_SLOT,
            )
        )
```

### Validator registry

#### Modified `get_validator_from_deposit`

```python
def get_validator_from_deposit(
    # [Modified in PQ]
    pubkey: XMSSPubkey,
    withdrawal_credentials: Bytes32,
    amount: Gwei,
) -> Validator:
    validator = Validator(
        pubkey=pubkey,
        withdrawal_credentials=withdrawal_credentials,
        effective_balance=Gwei(0),
        slashed=Boolean(False),
        activation_eligibility_epoch=FAR_FUTURE_EPOCH,
        activation_epoch=FAR_FUTURE_EPOCH,
        exit_epoch=FAR_FUTURE_EPOCH,
        withdrawable_epoch=FAR_FUTURE_EPOCH,
    )

    max_effective_balance = get_max_effective_balance(validator)
    validator.effective_balance = min(
        amount - amount % EFFECTIVE_BALANCE_INCREMENT, max_effective_balance
    )

    return validator
```

#### Modified `add_validator_to_registry`

```python
def add_validator_to_registry(
    state: BeaconState,
    # [Modified in PQ]
    pubkey: XMSSPubkey,
    withdrawal_credentials: Bytes32,
    amount: Gwei,
) -> None:
    index = get_index_for_new_validator(state)
    validator = get_validator_from_deposit(pubkey, withdrawal_credentials, amount)
    set_or_append_list(state.validators, index, validator)
    set_or_append_list(state.balances, index, amount)
    set_or_append_list(state.previous_epoch_participation, index, ParticipationFlags(0b0000_0000))
    set_or_append_list(state.current_epoch_participation, index, ParticipationFlags(0b0000_0000))
    set_or_append_list(state.inactivity_scores, index, Uint64(0))
```

#### Modified `add_builder_to_registry`

```python
def add_builder_to_registry(
    state: BeaconState,
    # [Modified in PQ]
    pubkey: XMSSPubkey,
    version: Uint8,
    execution_address: ExecutionAddress,
    amount: Gwei,
    slot: Slot,
) -> None:
    set_or_append_list(
        state.builders,
        get_index_for_new_builder(state),
        Builder(
            pubkey=pubkey,
            version=version,
            execution_address=execution_address,
            balance=amount,
            deposit_epoch=compute_epoch_at_slot(slot),
            withdrawable_epoch=FAR_FUTURE_EPOCH,
        ),
    )
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
    return xmss.Verify(proposer.pubkey, leaf_index, signing_root, signed_block.signature)
```

### Block processing

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
    assert xmss.Verify(proposer.pubkey, leaf_index, signing_root, body.randao_reveal)
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
        (CONSOLIDATION_REQUEST_TYPE, execution_requests.consolidations),
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
        pubkey = state.validators[validator_index].pubkey
    else:
        pubkey = state.builders[builder_index].pubkey

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
    return xmss.Verify(builder.pubkey, leaf_index, signing_root, signed_bid.signature)
```

##### Modified `process_execution_payload_bid`

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

    # Verify commitments are under limit
    assert (
        len(bid.blob_kzg_commitments)
        <= get_blob_parameters(get_current_epoch(state)).max_blobs_per_block
    )

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
        assert xmss.Verify(proposer.pubkey, leaf_index, signing_root, signed_header.signature)

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
    assert xmss.Verify(validator.pubkey, leaf_index, signing_root, signed_voluntary_exit.signature)
    # Initiate exit
    initiate_validator_exit(state, voluntary_exit.validator_index)
```

##### Deposit requests

###### Modified `is_valid_deposit_signature`

*Note*: A deposit is signed at the deposit leaf of the genesis slot, a leaf that
no other message uses. A depositor must sign only one deposit message per key.

```python
def is_valid_deposit_signature(
    # [Modified in PQ]
    pubkey: XMSSPubkey,
    withdrawal_credentials: Bytes32,
    amount: Gwei,
    # [Modified in PQ]
    signature: XMSSSignature,
) -> bool:
    deposit_message = DepositMessage(
        pubkey=pubkey,
        withdrawal_credentials=withdrawal_credentials,
        amount=amount,
    )
    # Fork-agnostic domain since deposits are valid across forks
    domain = compute_domain(DOMAIN_DEPOSIT)
    signing_root = compute_signing_root(deposit_message, domain)
    # [Modified in PQ]
    leaf_index = compute_xmss_leaf_index(GENESIS_SLOT, LEAF_OFFSET_DEPOSIT)
    return xmss.Verify(pubkey, leaf_index, signing_root, signature)
```

##### Builder deposit requests

###### Modified `is_valid_builder_deposit_signature`

```python
def is_valid_builder_deposit_signature(request: BuilderDepositRequest) -> bool:
    deposit_message = DepositMessage(
        pubkey=request.pubkey,
        withdrawal_credentials=request.withdrawal_credentials,
        amount=request.amount,
    )
    domain = compute_domain(DOMAIN_BUILDER_DEPOSIT)
    signing_root = compute_signing_root(deposit_message, domain)
    # [Modified in PQ]
    leaf_index = compute_xmss_leaf_index(GENESIS_SLOT, LEAF_OFFSET_DEPOSIT)
    return xmss.Verify(request.pubkey, leaf_index, signing_root, request.signature)
```

#### Sync aggregate processing

##### Modified `process_sync_aggregate`

*Note*: XMSS has no public key aggregation, so the participant keys are passed
to `xmss.AggregateVerify` individually.

```python
def process_sync_aggregate(state: BeaconState, sync_aggregate: SyncAggregate) -> None:
    # Verify sync committee aggregate signature signing over the previous slot block root
    committee_pubkeys = state.current_sync_committee.pubkeys
    # [Modified in PQ]
    participant_pubkeys = [
        pubkey
        for pubkey, bit in zip(committee_pubkeys, sync_aggregate.sync_committee_bits, strict=True)
        if bit
    ]
    previous_slot = saturating_sub(state.slot, 1)
    domain = get_domain(state, DOMAIN_SYNC_COMMITTEE, compute_epoch_at_slot(previous_slot))
    signing_root = compute_signing_root(get_block_root_at_slot(state, previous_slot), domain)
    # [Modified in PQ]
    leaf_index = compute_xmss_leaf_index(previous_slot, LEAF_OFFSET_SYNC_COMMITTEE)
    assert xmss.AggregateVerify(
        participant_pubkeys, leaf_index, signing_root, sync_aggregate.sync_committee_signature
    )

    # Compute participant and proposer rewards
    total_active_increments = get_total_active_balance(state) // EFFECTIVE_BALANCE_INCREMENT
    total_base_rewards = get_base_reward_per_increment(state) * total_active_increments
    max_participant_rewards = (
        total_base_rewards * SYNC_REWARD_WEIGHT // WEIGHT_DENOMINATOR // Uint64(SLOTS_PER_EPOCH)
    )
    participant_reward = max_participant_rewards // SYNC_COMMITTEE_SIZE
    proposer_reward = participant_reward * PROPOSER_WEIGHT // (WEIGHT_DENOMINATOR - PROPOSER_WEIGHT)

    # Apply participant and proposer rewards
    all_pubkeys = [validator.pubkey for validator in state.validators]
    committee_indices = [
        ValidatorIndex(all_pubkeys.index(pubkey)) for pubkey in state.current_sync_committee.pubkeys
    ]
    for participant_index, participation_bit in zip(
        committee_indices, sync_aggregate.sync_committee_bits, strict=True
    ):
        if participation_bit:
            increase_balance(state, participant_index, participant_reward)
            increase_balance(state, get_beacon_proposer_index(state), proposer_reward)
        else:
            decrease_balance(state, participant_index, participant_reward)
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
    assert len(requests.consolidations) <= MAX_CONSOLIDATION_REQUESTS_PER_PAYLOAD
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
    for_ops(requests.consolidations, process_consolidation_request)
    for_ops(requests.builder_deposits, process_builder_deposit_request)
    for_ops(requests.builder_exits, process_builder_exit_request)
    # [Modified in PQ]
    # Removed `process_pq_registration_request`

    # Update parent payload availability and latest block hash
    state.execution_payload_availability[parent_slot % SLOTS_PER_HISTORICAL_ROOT] = Boolean(True)
    state.latest_block_hash = parent_bid.block_hash
```
