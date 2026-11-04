# PQ -- The Beacon Chain

*Note*: This document is a work-in-progress for researchers and implementers.

<!-- mdformat-toc start --slug=github --no-anchors --maxlevel=6 --minlevel=2 -->

- [Introduction](#introduction)
- [Types](#types)
  - [New `PQBuilders`](#new-pqbuilders)
  - [New `PQValidators`](#new-pqvalidators)
  - [New `VRFProof`](#new-vrfproof)
  - [New `StarkProof`](#new-starkproof)
  - [New `XMSSAggregateSignature`](#new-xmssaggregatesignature)
  - [New `XMSSPubkey`](#new-xmsspubkey)
  - [New `XMSSSignature`](#new-xmsssignature)
- [Constants](#constants)
  - [XMSS](#xmss)
  - [VRF](#vrf)
  - [XMSS leaf offsets](#xmss-leaf-offsets)
  - [XMSS reserved leaves](#xmss-reserved-leaves)
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
    - [`PQBuilder`](#pqbuilder)
    - [`PQValidator`](#pqvalidator)
- [Dataclasses](#dataclasses)
  - [New dataclasses](#new-dataclasses)
    - [`XMSSAggregateStatement`](#xmssaggregatestatement)
- [Helpers](#helpers)
  - [Crypto](#crypto)
    - [XMSS signatures](#xmss-signatures)
    - [STARK proofs](#stark-proofs)
  - [Misc](#misc)
    - [New `compute_xmss_attestation_leaf_index`](#new-compute_xmss_attestation_leaf_index)
    - [New `compute_xmss_leaf_index`](#new-compute_xmss_leaf_index)
    - [Modified `can_builder_cover_bid`](#modified-can_builder_cover_bid)
    - [Modified `compute_balance_weighted_selection`](#modified-compute_balance_weighted_selection)
    - [Modified `get_max_effective_balance`](#modified-get_max_effective_balance)
  - [Predicates](#predicates)
    - [New `is_valid_vrf_proof`](#new-is_valid_vrf_proof)
    - [Modified `is_valid_indexed_attestation`](#modified-is_valid_indexed_attestation)
    - [Modified `has_compounding_withdrawal_credential`](#modified-has_compounding_withdrawal_credential)
    - [Modified `has_eth1_withdrawal_credential`](#modified-has_eth1_withdrawal_credential)
    - [Modified `has_execution_withdrawal_credential`](#modified-has_execution_withdrawal_credential)
    - [Modified `is_active_builder`](#modified-is_active_builder)
    - [Modified `is_active_validator`](#modified-is_active_validator)
    - [Modified `is_eligible_for_activation`](#modified-is_eligible_for_activation)
    - [Modified `is_eligible_for_activation_queue`](#modified-is_eligible_for_activation_queue)
    - [Modified `is_eligible_for_partial_withdrawals`](#modified-is_eligible_for_partial_withdrawals)
    - [Modified `is_fully_withdrawable_validator`](#modified-is_fully_withdrawable_validator)
    - [Modified `is_partially_withdrawable_validator`](#modified-is_partially_withdrawable_validator)
    - [Modified `is_slashable_validator`](#modified-is_slashable_validator)
  - [Beacon state accessors](#beacon-state-accessors)
    - [Modified `get_indexed_attestation`](#modified-get_indexed_attestation)
    - [New `get_attestation_statements`](#new-get_attestation_statements)
    - [Modified `get_active_validator_indices`](#modified-get_active_validator_indices)
    - [Modified `get_base_reward`](#modified-get_base_reward)
    - [Modified `get_beacon_proposer_indices`](#modified-get_beacon_proposer_indices)
    - [Modified `get_eligible_validator_indices`](#modified-get_eligible_validator_indices)
    - [Modified `get_flag_index_deltas`](#modified-get_flag_index_deltas)
    - [Modified `get_inactivity_penalty_deltas`](#modified-get_inactivity_penalty_deltas)
    - [Modified `get_total_balance`](#modified-get_total_balance)
    - [Modified `get_unslashed_participating_indices`](#modified-get_unslashed_participating_indices)
  - [Beacon state mutators](#beacon-state-mutators)
    - [Modified `initiate_builder_exit`](#modified-initiate_builder_exit)
    - [Modified `initiate_validator_exit`](#modified-initiate_validator_exit)
    - [Modified `slash_validator`](#modified-slash_validator)
- [Beacon chain state transition function](#beacon-chain-state-transition-function)
  - [Modified `verify_block_signature`](#modified-verify_block_signature)
  - [Epoch processing](#epoch-processing)
    - [Modified `process_epoch`](#modified-process_epoch)
    - [Modified `process_effective_balance_updates`](#modified-process_effective_balance_updates)
    - [Modified `process_participation_flag_updates`](#modified-process_participation_flag_updates)
    - [Modified `process_pending_consolidations`](#modified-process_pending_consolidations)
    - [Modified `process_pending_deposits`](#modified-process_pending_deposits)
    - [Modified `apply_pending_deposit`](#modified-apply_pending_deposit)
    - [Modified `process_registry_updates`](#modified-process_registry_updates)
    - [Modified `process_rewards_and_penalties`](#modified-process_rewards_and_penalties)
    - [Modified `process_slashings`](#modified-process_slashings)
  - [Block processing](#block-processing)
    - [Modified `process_block`](#modified-process_block)
    - [Modified `process_block_header`](#modified-process_block_header)
    - [Modified `process_randao`](#modified-process_randao)
    - [Execution payload](#execution-payload)
      - [Modified `get_execution_requests_list`](#modified-get_execution_requests_list)
      - [Modified `verify_execution_payload_envelope_signature`](#modified-verify_execution_payload_envelope_signature)
    - [Execution payload bid](#execution-payload-bid)
      - [Modified `verify_execution_payload_bid_signature`](#modified-verify_execution_payload_bid_signature)
      - [Modified `process_execution_payload_bid`](#modified-process_execution_payload_bid)
    - [Operations](#operations)
      - [Modified `process_operations`](#modified-process_operations)
      - [New `process_stark`](#new-process_stark)
      - [Modified `process_proposer_slashing`](#modified-process_proposer_slashing)
      - [Modified `process_voluntary_exit`](#modified-process_voluntary_exit)
      - [Attestations](#attestations)
        - [Modified `process_attestation`](#modified-process_attestation)
      - [Modified `process_attester_slashing`](#modified-process_attester_slashing)
      - [Builder deposit requests](#builder-deposit-requests)
        - [Modified `process_builder_deposit_request`](#modified-process_builder_deposit_request)
      - [Builder exit requests](#builder-exit-requests)
        - [Modified `process_builder_exit_request`](#modified-process_builder_exit_request)
      - [Execution-layer withdrawal requests](#execution-layer-withdrawal-requests)
        - [Modified `process_withdrawal_request`](#modified-process_withdrawal_request)
    - [Parent execution payload](#parent-execution-payload)
      - [Modified `apply_parent_execution_payload`](#modified-apply_parent_execution_payload)
    - [Withdrawals](#withdrawals)
      - [Modified `apply_withdrawals`](#modified-apply_withdrawals)
      - [Modified `get_builder_balance_after_withdrawals`](#modified-get_builder_balance_after_withdrawals)
      - [Modified `get_builders_sweep_withdrawals`](#modified-get_builders_sweep_withdrawals)
      - [Modified `get_pending_partial_withdrawals`](#modified-get_pending_partial_withdrawals)
      - [Modified `get_validators_sweep_withdrawals`](#modified-get_validators_sweep_withdrawals)
      - [Modified `update_next_withdrawal_builder_index`](#modified-update_next_withdrawal_builder_index)
      - [Modified `update_next_withdrawal_validator_index`](#modified-update_next_withdrawal_validator_index)

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
type, see `compute_xmss_leaf_index`. An attestation instead uses the leaf of its
target epoch, see `compute_xmss_attestation_leaf_index`. A message that a key
signs at most once, such as a voluntary exit, instead uses one of the first
`XMSS_RESERVED_LEAVES` leaves. An honest signer that never equivocates never
reuses a leaf. Each signature carries its leaf index, and verification checks it
against the expected one.

XMSS has no native aggregation. Aggregates are opaque `XMSSAggregateSignature`
values, produced and checked by `xmss.Aggregate` and `xmss.AggregateVerify`. The
reference implementation concatenates signatures as a stand-in for a succinct
aggregation scheme.

XMSS signatures are not unique, so a proposer could grind a signature-based
RANDAO reveal. Each validator instead registers the root of a Merkle tree of
secret random values, one for each slot, as its VRF data. Its RANDAO reveal is
the leaf for the slot with the leaf's Merkle branch, a `VRFProof`, which the
proposer committed to before the fork. The same proof serves as its selection
proof when it aggregates.

The validator and builder registries move to `state.pq_validators` and
`state.pq_builders`. A validator's record carries the XMSS public key and VRF
data it registered with EIP-8483 before the fork. The fork copies every
validator and builder into them at the same index. From then on the state
transition reads and writes only the new registries, and `state.validators` and
`state.builders` are frozen. A builder's record carries the XMSS public key it
registered. Validators and builders that did not register are exited at the
fork. See [the fork document](./fork.md) for details.

Execution layer requests still name validators and builders by BLS public key,
which the new registries do not hold. Withdrawal and builder exit requests are
therefore ignored, and every builder deposit waits in
`state.pending_builder_deposits`, until a later upgrade changes the system
contracts to name them by XMSS public key.

*Note*: Pending deposits still find their validator by BLS public key in
`state.validators`. A deposit for a public key that is not in the registry
cannot create a validator, because it carries no XMSS public key. It stays in
`state.pending_deposits` and is postponed every epoch without consuming churn. A
way to register keys after the fork is left open.

`BLSToExecutionChange` is disabled, because its BLS signature could be forged.
Balances behind `0x00` withdrawal credentials stay locked until a later upgrade
adds a quantum-safe way to change them.

Consolidation requests are deprecated, so the execution layer must stop
producing them at the fork. Pending consolidations still complete.

Blocks no longer carry payload attestations, which spares proposers from
aggregating them. The payload timeliness committee still broadcasts its votes,
which fork choice uses as before.

Attestations no longer carry a signature. A block instead carries one `stark`
proof of the aggregate signatures of all its attestations, which replaces
verifying each attestation's aggregate in turn. An aggregate on the wire carries
a `stark` of its own in `AggregateAndProof`, and the proposer merges those into
the block's `stark`.

*Note*: This specification is built upon [PQReg](../pqreg/beacon-chain.md),
which is built upon [Gloas](../../gloas/beacon-chain.md).

## Types

### New `PQBuilders`

```python
class PQBuilders(ProgressiveList[PQBuilder]):
    """
    The builder registry, which replaces ``Builders`` from PQ onwards.
    """
```

### New `PQValidators`

```python
class PQValidators(ProgressiveList[PQValidator]):
    """
    The validator registry, which replaces ``Validators`` from PQ onwards.
    """
```

### New `VRFProof`

```python
class VRFProof(Vector[Bytes32]):
    """
    A leaf of the tree whose root is a validator's VRF data, followed by the
    leaf's Merkle branch.
    """

    LENGTH = VRF_TREE_DEPTH + 1
```

### New `StarkProof`

```python
class StarkProof(ByteList):
    """
    A STARK proof of the aggregate signatures of a block's attestations.
    """

    LIMIT = MAX_STARK_PROOF_SIZE
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

| Name                      | Value                             |
| ------------------------- | --------------------------------- |
| `XMSS_SIGNATURE_SIZE`     | `Uint64(2404)`                    |
| `XMSS_RESERVED_LEAVES`    | `Uint64(2**15)` (= 32,768)        |
| `XMSS_ATTESTATION_LEAVES` | `Uint64(2**31)` (= 2,147,483,648) |
| `XMSS_LEAVES_PER_SLOT`    | `Uint64(2**3)` (= 8)              |

### VRF

| Name             | Value        |
| ---------------- | ------------ |
| `VRF_TREE_DEPTH` | `Uint64(31)` |

### XMSS leaf offsets

| Name                                     | Value       |
| ---------------------------------------- | ----------- |
| `LEAF_OFFSET_BEACON_PROPOSER`            | `Uint64(0)` |
| `LEAF_OFFSET_AGGREGATE_AND_PROOF`        | `Uint64(1)` |
| `LEAF_OFFSET_PTC_ATTESTER`               | `Uint64(2)` |
| `LEAF_OFFSET_PROPOSER_PREFERENCES`       | `Uint64(3)` |
| `LEAF_OFFSET_EXECUTION_PAYLOAD_BID`      | `Uint64(4)` |
| `LEAF_OFFSET_EXECUTION_PAYLOAD_ENVELOPE` | `Uint64(5)` |

### XMSS reserved leaves

| Name                           | Value       |
| ------------------------------ | ----------- |
| `RESERVED_LEAF_VOLUNTARY_EXIT` | `Uint64(0)` |

## Presets

### XMSS

| Name                                | Value                         |
| ----------------------------------- | ----------------------------- |
| `MAX_XMSS_AGGREGATE_SIGNATURE_SIZE` | `Uint64(2**20)` (= 1,048,576) |
| `MAX_STARK_PROOF_SIZE`              | `Uint64(2**20)` (= 1,048,576) |

*Note*: `MAX_XMSS_AGGREGATE_SIGNATURE_SIZE` and `MAX_STARK_PROOF_SIZE` are
placeholders for the proof sizes of a succinct aggregation scheme and a STARK.
The reference concatenation fits at most
`MAX_XMSS_AGGREGATE_SIGNATURE_SIZE // XMSS_SIGNATURE_SIZE` signatures in an
aggregate, and `MAX_STARK_PROOF_SIZE // XMSS_SIGNATURE_SIZE` signatures in a
proof.

### Max operations per block

| Name                  | Value                 |
| --------------------- | --------------------- |
| `MAX_ATTESTATIONS_PQ` | `Uint64(2**4)` (= 16) |

## Containers

### Modified containers

#### `Attestation`

```python
class Attestation(ProgressiveContainer):
    ACTIVE_FIELDS = active_fields(width=4, gaps=(2,))

    aggregation_bits: AggregationBits
    data: AttestationData
    # [Modified in PQ]
    # Removed `signature`
    committee_bits: CommitteeBits
```

#### `BeaconBlockBody`

```python
class BeaconBlockBody(ProgressiveContainer):
    ACTIVE_FIELDS = active_fields(width=14, gaps=(8, 9, 11))

    # [Modified in PQ]
    randao_reveal: VRFProof
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
    # [New in PQ]
    stark: StarkProof
```

#### `BeaconState`

```python
class BeaconState(ProgressiveContainer):
    ACTIVE_FIELDS = active_fields(width=51, gaps=(22, 23, 46, 47))

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
    # Removed `validator_pq_registrations`
    # [Modified in PQ]
    # Removed `builder_pq_registrations`
    # [New in PQ]
    pq_validators: PQValidators
    # [New in PQ]
    pq_builders: PQBuilders
    # [New in PQ]
    pending_builder_deposits: PendingDeposits
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
    # Removed `validator_pq_registrations`
    # [Modified in PQ]
    # Removed `builder_pq_registrations`
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

#### `PQBuilder`

```python
class PQBuilder(Container):
    pubkey: XMSSPubkey
    version: Uint8
    execution_address: ExecutionAddress
    balance: Gwei
    deposit_epoch: Epoch
    withdrawable_epoch: Epoch
```

#### `PQValidator`

```python
class PQValidator(Container):
    pubkey: XMSSPubkey
    vrf_data: Root
    withdrawal_credentials: Bytes32
    effective_balance: Gwei
    slashed: Boolean
    activation_eligibility_epoch: Epoch
    activation_epoch: Epoch
    exit_epoch: Epoch
    withdrawable_epoch: Epoch
```

## Dataclasses

### New dataclasses

#### `XMSSAggregateStatement`

```python
@dataclass
class XMSSAggregateStatement:
    pubkeys: Sequence[XMSSPubkey]
    leaf_index: Uint64
    message: Bytes32
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

#### STARK proofs

This upgrade adds the following functions to prove many aggregates at once:

- `def ProveAggregates(statements: Sequence[XMSSAggregateStatement], aggregates: Sequence[XMSSAggregateSignature]) -> StarkProof`
- `def MergeProofs(proofs: Sequence[StarkProof]) -> StarkProof`
- `def VerifyAggregates(statements: Sequence[XMSSAggregateStatement], proof: StarkProof) -> bool`

`VerifyAggregates` returns `True` only if `proof` proves, for each statement, an
aggregate that
`xmss.AggregateVerify(statement.pubkeys, statement.leaf_index, statement.message, aggregate)`
accepts. `ProveAggregates` takes those aggregates in the order of the
statements. `MergeProofs` turns proofs of lists of statements into one proof of
their concatenation, in order.

The above functions are accessed through the `stark` module, e.g.
`stark.VerifyAggregates`.

*Note*: The reference implementations of `ProveAggregates` and `MergeProofs`
concatenate their inputs, and `VerifyAggregates` checks each aggregate in turn.
They stand in for a recursive STARK, which would change the encoding of
`StarkProof` but not how these functions are used.

### Misc

#### New `compute_xmss_attestation_leaf_index`

*Note*: The first `XMSS_RESERVED_LEAVES` leaves are reserved for messages that a
key signs at most once. The next `XMSS_ATTESTATION_LEAVES` leaves hold one
attestation per target epoch, since a validator that attests twice for the same
target epoch is slashed for a double vote.

```python
def compute_xmss_attestation_leaf_index(epoch: Epoch) -> Uint64:
    """
    Return the XMSS leaf at which an attestation is signed for target ``epoch``.
    """
    return Uint64(XMSS_RESERVED_LEAVES + epoch)
```

#### New `compute_xmss_leaf_index`

*Note*: The leaves of each slot follow the reserved and attestation leaves. A
key covers `2**32` leaves, so it lasts
`(2**32 - XMSS_RESERVED_LEAVES - XMSS_ATTESTATION_LEAVES) // XMSS_LEAVES_PER_SLOT`
slots.

```python
def compute_xmss_leaf_index(slot: Slot, leaf_offset: Uint64) -> Uint64:
    """
    Return the XMSS leaf at which a message of the type given by ``leaf_offset``
    is signed for ``slot``.
    """
    return Uint64(
        XMSS_RESERVED_LEAVES + XMSS_ATTESTATION_LEAVES + slot * XMSS_LEAVES_PER_SLOT + leaf_offset
    )
```

#### Modified `can_builder_cover_bid`

```python
def can_builder_cover_bid(
    state: BeaconState, builder_index: BuilderIndex, bid_amount: Gwei
) -> bool:
    # [Modified in PQ]
    builder_balance = state.pq_builders[builder_index].balance
    pending_withdrawals_amount = get_pending_balance_to_withdraw_for_builder(state, builder_index)
    min_balance = MIN_DEPOSIT_AMOUNT + pending_withdrawals_amount
    if builder_balance < min_balance:
        return False
    return builder_balance - min_balance >= bid_amount
```

#### Modified `compute_balance_weighted_selection`

```python
def compute_balance_weighted_selection(
    state: BeaconState,
    indices: Sequence[ValidatorIndex],
    seed: Bytes32,
    size: Uint64,
    shuffle_indices: bool,
) -> Sequence[ValidatorIndex]:
    """
    Return ``size`` indices sampled by effective balance, using ``indices``
    as candidates. If ``shuffle_indices`` is ``True``, candidate indices
    are themselves sampled from ``indices`` by shuffling it, otherwise
    ``indices`` is traversed in order. The returned list can contain duplicates.
    """
    MAX_RANDOM_VALUE = 2**16 - 1
    total = Uint64(len(indices))
    assert total > 0
    # [Modified in PQ]
    effective_balances = [state.pq_validators[index].effective_balance for index in indices]
    selected: list[ValidatorIndex] = []
    i = Uint64(0)
    while len(selected) < size:
        offset = i % 16 * 2
        if offset == 0:
            random_bytes = sha256(seed + uint_to_bytes(i // 16))
        next_index = i % total
        if shuffle_indices:
            next_index = compute_shuffled_index(next_index, total, seed)
        weight = effective_balances[next_index] * MAX_RANDOM_VALUE
        random_value = bytes_to_uint64(random_bytes[offset : offset + 2])
        threshold = MAX_EFFECTIVE_BALANCE_ELECTRA * random_value
        if weight >= threshold:
            selected.append(indices[next_index])
        i += 1
    return selected
```

#### Modified `get_max_effective_balance`

```python
def get_max_effective_balance(
    # [Modified in PQ]
    validator: PQValidator,
) -> Gwei:
    """
    Get max effective balance for ``validator``.
    """
    if has_compounding_withdrawal_credential(validator):
        return MAX_EFFECTIVE_BALANCE_ELECTRA
    else:
        return MIN_ACTIVATION_BALANCE
```

### Predicates

#### New `is_valid_vrf_proof`

```python
def is_valid_vrf_proof(
    state: BeaconState, validator_index: ValidatorIndex, slot: Slot, proof: VRFProof
) -> bool:
    """
    Check that ``proof`` opens the leaf at index ``slot`` of the tree whose root
    is the VRF data of the validator at ``validator_index``.
    """
    return is_valid_merkle_branch(
        leaf=proof[0],
        branch=proof[1:],
        depth=VRF_TREE_DEPTH,
        index=slot,
        root=state.pq_validators[validator_index].vrf_data,
    )
```

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
    pubkeys = [state.pq_validators[index].pubkey for index in indices]
    domain = get_domain(state, DOMAIN_BEACON_ATTESTER, indexed_attestation.data.target.epoch)
    signing_root = compute_signing_root(indexed_attestation.data, domain)
    # [Modified in PQ]
    leaf_index = compute_xmss_attestation_leaf_index(indexed_attestation.data.target.epoch)
    return xmss.AggregateVerify(pubkeys, leaf_index, signing_root, indexed_attestation.signature)
```

#### Modified `has_compounding_withdrawal_credential`

```python
def has_compounding_withdrawal_credential(
    # [Modified in PQ]
    validator: PQValidator,
) -> bool:
    """
    Check if ``validator`` has an 0x02 prefixed "compounding" withdrawal credential.
    """
    return is_compounding_withdrawal_credential(validator.withdrawal_credentials)
```

#### Modified `has_eth1_withdrawal_credential`

```python
def has_eth1_withdrawal_credential(
    # [Modified in PQ]
    validator: PQValidator,
) -> bool:
    """
    Check if ``validator`` has an 0x01 prefixed "eth1" withdrawal credential.
    """
    return validator.withdrawal_credentials[:1] == ETH1_ADDRESS_WITHDRAWAL_PREFIX
```

#### Modified `has_execution_withdrawal_credential`

```python
def has_execution_withdrawal_credential(
    # [Modified in PQ]
    validator: PQValidator,
) -> bool:
    """
    Check if ``validator`` has a 0x01 or 0x02 prefixed withdrawal credential.
    """
    return (
        has_eth1_withdrawal_credential(validator)  # 0x01
        or has_compounding_withdrawal_credential(validator)  # 0x02
    )
```

#### Modified `is_active_builder`

```python
def is_active_builder(state: BeaconState, builder_index: BuilderIndex) -> bool:
    """
    Check if the builder at ``builder_index`` is active for the given ``state``.
    """
    # [Modified in PQ]
    builder = state.pq_builders[builder_index]
    return (
        # Placement in builder list is finalized
        builder.deposit_epoch < state.finalized_checkpoint.epoch
        # Has not initiated exit
        and builder.withdrawable_epoch == FAR_FUTURE_EPOCH
    )
```

#### Modified `is_active_validator`

```python
def is_active_validator(
    # [Modified in PQ]
    validator: PQValidator,
    epoch: Epoch,
) -> bool:
    """
    Check if ``validator`` is active.
    """
    return validator.activation_epoch <= epoch < validator.exit_epoch
```

#### Modified `is_eligible_for_activation`

```python
def is_eligible_for_activation(
    state: BeaconState,
    # [Modified in PQ]
    validator: PQValidator,
) -> bool:
    """
    Check if ``validator`` is eligible for activation.
    """
    return (
        # Placement in queue is finalized
        validator.activation_eligibility_epoch <= state.finalized_checkpoint.epoch
        # Has not yet been activated
        and validator.activation_epoch == FAR_FUTURE_EPOCH
    )
```

#### Modified `is_eligible_for_activation_queue`

```python
def is_eligible_for_activation_queue(
    # [Modified in PQ]
    validator: PQValidator,
) -> bool:
    """
    Check if ``validator`` is eligible to be placed into the activation queue.
    """
    return (
        validator.activation_eligibility_epoch == FAR_FUTURE_EPOCH
        and validator.effective_balance >= MIN_ACTIVATION_BALANCE
    )
```

#### Modified `is_eligible_for_partial_withdrawals`

```python
def is_eligible_for_partial_withdrawals(
    # [Modified in PQ]
    validator: PQValidator,
    balance: Gwei,
) -> bool:
    """
    Check if ``validator`` can process a pending partial withdrawal.
    """
    has_sufficient_effective_balance = validator.effective_balance >= MIN_ACTIVATION_BALANCE
    has_excess_balance = balance > MIN_ACTIVATION_BALANCE
    return (
        validator.exit_epoch == FAR_FUTURE_EPOCH
        and has_sufficient_effective_balance
        and has_excess_balance
    )
```

#### Modified `is_fully_withdrawable_validator`

```python
def is_fully_withdrawable_validator(
    # [Modified in PQ]
    validator: PQValidator,
    balance: Gwei,
    epoch: Epoch,
) -> bool:
    """
    Check if ``validator`` is fully withdrawable.
    """
    return (
        has_execution_withdrawal_credential(validator)
        and validator.withdrawable_epoch <= epoch
        and balance > 0
    )
```

#### Modified `is_partially_withdrawable_validator`

```python
def is_partially_withdrawable_validator(
    # [Modified in PQ]
    validator: PQValidator,
    balance: Gwei,
) -> bool:
    """
    Check if ``validator`` is partially withdrawable.
    """
    max_effective_balance = get_max_effective_balance(validator)
    has_max_effective_balance = validator.effective_balance == max_effective_balance
    has_excess_balance = balance > max_effective_balance
    return (
        has_execution_withdrawal_credential(validator)
        and has_max_effective_balance
        and has_excess_balance
    )
```

#### Modified `is_slashable_validator`

```python
def is_slashable_validator(
    # [Modified in PQ]
    validator: PQValidator,
    epoch: Epoch,
) -> bool:
    """
    Check if ``validator`` is slashable.
    """
    return (not validator.slashed) and (
        validator.activation_epoch <= epoch < validator.withdrawable_epoch
    )
```

### Beacon state accessors

#### Modified `get_indexed_attestation`

```python
def get_indexed_attestation(
    state: BeaconState,
    attestation: Attestation,
    # [New in PQ]
    signature: XMSSAggregateSignature,
) -> IndexedAttestation:
    """
    Return the indexed attestation corresponding to ``attestation`` and its
    aggregate ``signature``.
    """
    attesting_indices = get_attesting_indices(state, attestation)

    return IndexedAttestation(
        attesting_indices=AttestingIndices(data=sorted(attesting_indices)),
        data=attestation.data,
        # [Modified in PQ]
        signature=signature,
    )
```

#### New `get_attestation_statements`

*Note*: A network aggregate covers one committee, so its `stark` proves one
statement. Statements are per committee so that the proposer can merge those
proofs into the block's `stark`.

```python
def get_attestation_statements(
    state: BeaconState, attestation: Attestation
) -> Sequence[XMSSAggregateStatement]:
    """
    Return, for each committee of ``attestation`` in order, the statement that the
    aggregate signature of its attesters in that committee proves.
    """
    domain = get_domain(state, DOMAIN_BEACON_ATTESTER, attestation.data.target.epoch)
    message = compute_signing_root(attestation.data, domain)
    leaf_index = compute_xmss_attestation_leaf_index(attestation.data.target.epoch)
    statements = []
    committee_offset = 0
    for committee_index in get_committee_indices(attestation.committee_bits):
        committee = get_beacon_committee(state, attestation.data.slot, committee_index)
        pubkeys = [
            state.pq_validators[validator_index].pubkey
            for i, validator_index in enumerate(committee)
            if attestation.aggregation_bits[committee_offset + i]
        ]
        statements.append(
            XMSSAggregateStatement(pubkeys=pubkeys, leaf_index=leaf_index, message=message)
        )
        committee_offset += len(committee)
    return statements
```

#### Modified `get_active_validator_indices`

```python
def get_active_validator_indices(state: BeaconState, epoch: Epoch) -> Sequence[ValidatorIndex]:
    """
    Return the sequence of active validator indices at ``epoch``.
    """
    return [
        ValidatorIndex(index)
        # [Modified in PQ]
        for index, validator in enumerate(state.pq_validators)
        if is_active_validator(validator, epoch)
    ]
```

#### Modified `get_base_reward`

```python
def get_base_reward(state: BeaconState, index: ValidatorIndex) -> Gwei:
    """
    Return the base reward for the validator defined by ``index`` with respect to the current ``state``.
    """
    # [Modified in PQ]
    increments = state.pq_validators[index].effective_balance // EFFECTIVE_BALANCE_INCREMENT
    return increments * get_base_reward_per_increment(state)
```

#### Modified `get_beacon_proposer_indices`

```python
def get_beacon_proposer_indices(state: BeaconState, epoch: Epoch) -> ProposerIndices:
    """
    Return the proposer indices for the given ``epoch``.
    """
    indices = [
        index
        for index in get_active_validator_indices(state, epoch)
        # [Modified in PQ]
        if not state.pq_validators[index].slashed
    ]
    seed = get_seed(state, epoch, DOMAIN_BEACON_PROPOSER)
    return compute_proposer_indices(state, epoch, seed, indices)
```

#### Modified `get_eligible_validator_indices`

```python
def get_eligible_validator_indices(state: BeaconState) -> Sequence[ValidatorIndex]:
    previous_epoch = get_previous_epoch(state)
    return [
        ValidatorIndex(index)
        # [Modified in PQ]
        for index, validator in enumerate(state.pq_validators)
        if is_active_validator(validator, previous_epoch)
        or (validator.slashed and previous_epoch + 1 < validator.withdrawable_epoch)
    ]
```

#### Modified `get_flag_index_deltas`

```python
def get_flag_index_deltas(
    state: BeaconState, flag_index: int
) -> tuple[Sequence[Gwei], Sequence[Gwei]]:
    """
    Return the deltas for a given ``flag_index`` by scanning through the participation flags.
    """
    # [Modified in PQ]
    rewards = [Gwei(0)] * len(state.pq_validators)
    # [Modified in PQ]
    penalties = [Gwei(0)] * len(state.pq_validators)
    previous_epoch = get_previous_epoch(state)
    unslashed_participating_indices = get_unslashed_participating_indices(
        state, flag_index, previous_epoch
    )
    weight = PARTICIPATION_FLAG_WEIGHTS[flag_index]
    unslashed_participating_balance = get_total_balance(state, unslashed_participating_indices)
    unslashed_participating_increments = (
        unslashed_participating_balance // EFFECTIVE_BALANCE_INCREMENT
    )
    active_increments = get_total_active_balance(state) // EFFECTIVE_BALANCE_INCREMENT
    for index in get_eligible_validator_indices(state):
        base_reward = get_base_reward(state, index)
        if index in unslashed_participating_indices:
            if not is_in_inactivity_leak(state):
                reward_numerator = base_reward * weight * unslashed_participating_increments
                rewards[index] += reward_numerator // (active_increments * WEIGHT_DENOMINATOR)
        elif flag_index != TIMELY_HEAD_FLAG_INDEX:
            penalties[index] += base_reward * weight // WEIGHT_DENOMINATOR
    return rewards, penalties
```

#### Modified `get_inactivity_penalty_deltas`

```python
def get_inactivity_penalty_deltas(state: BeaconState) -> tuple[Sequence[Gwei], Sequence[Gwei]]:
    """
    Return the inactivity penalty deltas by considering timely target participation flags and inactivity scores.
    """
    # [Modified in PQ]
    rewards = [Gwei(0)] * len(state.pq_validators)
    # [Modified in PQ]
    penalties = [Gwei(0)] * len(state.pq_validators)
    previous_epoch = get_previous_epoch(state)
    matching_target_indices = get_unslashed_participating_indices(
        state, TIMELY_TARGET_FLAG_INDEX, previous_epoch
    )
    for index in get_eligible_validator_indices(state):
        if index not in matching_target_indices:
            penalty_numerator = (
                # [Modified in PQ]
                state.pq_validators[index].effective_balance * state.inactivity_scores[index]
            )
            penalty_denominator = INACTIVITY_SCORE_BIAS * INACTIVITY_PENALTY_QUOTIENT_BELLATRIX
            penalties[index] += penalty_numerator // penalty_denominator
    return rewards, penalties
```

#### Modified `get_total_balance`

```python
def get_total_balance(state: BeaconState, indices: set[ValidatorIndex]) -> Gwei:
    """
    Return the combined effective balance of the ``indices``.
    ``EFFECTIVE_BALANCE_INCREMENT`` Gwei minimum to avoid divisions by zero.
    Math safe up to ~10B ETH, after which this overflows Uint64.
    """
    return Gwei(
        max(
            EFFECTIVE_BALANCE_INCREMENT,
            # [Modified in PQ]
            sum([state.pq_validators[index].effective_balance for index in indices]),
        )
    )
```

#### Modified `get_unslashed_participating_indices`

```python
def get_unslashed_participating_indices(
    state: BeaconState, flag_index: int, epoch: Epoch
) -> set[ValidatorIndex]:
    """
    Return the set of validator indices that are both active and unslashed for the given ``flag_index`` and ``epoch``.
    """
    assert epoch in (get_previous_epoch(state), get_current_epoch(state))
    if epoch == get_current_epoch(state):
        epoch_participation = state.current_epoch_participation
    else:
        epoch_participation = state.previous_epoch_participation
    active_validator_indices = get_active_validator_indices(state, epoch)
    participating_indices = [
        index
        for index in active_validator_indices
        if has_flag(epoch_participation[index], flag_index)
    ]
    # [Modified in PQ]
    return set(filter(lambda index: not state.pq_validators[index].slashed, participating_indices))
```

### Beacon state mutators

#### Modified `initiate_builder_exit`

```python
def initiate_builder_exit(state: BeaconState, builder_index: BuilderIndex) -> None:
    """
    Initiate the exit of the builder with index ``index``.
    """
    # Set builder exit epoch
    # [Modified in PQ]
    builder = state.pq_builders[builder_index]
    builder.withdrawable_epoch = get_current_epoch(state) + MIN_BUILDER_WITHDRAWABILITY_DELAY
```

#### Modified `initiate_validator_exit`

```python
def initiate_validator_exit(state: BeaconState, index: ValidatorIndex) -> None:
    """
    Initiate the exit of the validator with index ``index``.
    """
    # Return if validator already initiated exit
    # [Modified in PQ]
    validator = state.pq_validators[index]
    if validator.exit_epoch != FAR_FUTURE_EPOCH:
        return

    # Compute exit queue epoch [Modified in Electra:EIP7251]
    exit_queue_epoch = compute_exit_epoch_and_update_churn(state, validator.effective_balance)

    # Set validator exit epoch and withdrawable epoch
    validator.exit_epoch = exit_queue_epoch
    validator.withdrawable_epoch = validator.exit_epoch + MIN_VALIDATOR_WITHDRAWABILITY_DELAY
```

#### Modified `slash_validator`

```python
def slash_validator(
    state: BeaconState,
    slashed_index: ValidatorIndex,
    whistleblower_index: ValidatorIndex | None = None,
) -> None:
    """
    Slash the validator with index ``slashed_index``.
    """
    epoch = get_current_epoch(state)
    initiate_validator_exit(state, slashed_index)
    # [Modified in PQ]
    validator = state.pq_validators[slashed_index]
    validator.slashed = Boolean(True)
    validator.withdrawable_epoch = max(
        validator.withdrawable_epoch, epoch + EPOCHS_PER_SLASHINGS_VECTOR
    )
    state.slashings[epoch % EPOCHS_PER_SLASHINGS_VECTOR] += validator.effective_balance
    slashing_penalty = validator.effective_balance // MIN_SLASHING_PENALTY_QUOTIENT_ELECTRA
    decrease_balance(state, slashed_index, slashing_penalty)

    # Apply proposer and whistleblower rewards
    proposer_index = get_beacon_proposer_index(state)
    if whistleblower_index is None:
        whistleblower_index = proposer_index
    whistleblower_reward = validator.effective_balance // WHISTLEBLOWER_REWARD_QUOTIENT_ELECTRA
    proposer_reward = whistleblower_reward * PROPOSER_WEIGHT // WEIGHT_DENOMINATOR
    increase_balance(state, proposer_index, proposer_reward)
    increase_balance(state, whistleblower_index, whistleblower_reward - proposer_reward)

    # Remove pending builder payments for blocks proposed by the slashed validator
    for payment_index, payment in enumerate(state.builder_pending_payments):
        if payment.proposer_index == slashed_index:
            state.builder_pending_payments[payment_index] = BuilderPendingPayment.empty()
```

## Beacon chain state transition function

### Modified `verify_block_signature`

```python
def verify_block_signature(state: BeaconState, signed_block: SignedBeaconBlock) -> bool:
    # [Modified in PQ]
    proposer = state.pq_validators[signed_block.message.proposer_index]
    signing_root = compute_signing_root(
        signed_block.message, get_domain(state, DOMAIN_BEACON_PROPOSER)
    )
    # [Modified in PQ]
    leaf_index = compute_xmss_leaf_index(signed_block.message.slot, LEAF_OFFSET_BEACON_PROPOSER)
    return xmss.Verify(proposer.pubkey, leaf_index, signing_root, signed_block.signature)
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

#### Modified `process_effective_balance_updates`

```python
def process_effective_balance_updates(state: BeaconState) -> None:
    # Update effective balances with hysteresis
    # [Modified in PQ]
    for index, validator in enumerate(state.pq_validators):
        balance = state.balances[index]
        HYSTERESIS_INCREMENT = Uint64(EFFECTIVE_BALANCE_INCREMENT // HYSTERESIS_QUOTIENT)
        DOWNWARD_THRESHOLD = HYSTERESIS_INCREMENT * HYSTERESIS_DOWNWARD_MULTIPLIER
        UPWARD_THRESHOLD = HYSTERESIS_INCREMENT * HYSTERESIS_UPWARD_MULTIPLIER
        max_effective_balance = get_max_effective_balance(validator)

        if (
            balance + DOWNWARD_THRESHOLD < validator.effective_balance
            or validator.effective_balance + UPWARD_THRESHOLD < balance
        ):
            validator.effective_balance = min(
                balance - balance % EFFECTIVE_BALANCE_INCREMENT, max_effective_balance
            )
```

#### Modified `process_participation_flag_updates`

```python
def process_participation_flag_updates(state: BeaconState) -> None:
    state.previous_epoch_participation = state.current_epoch_participation
    state.current_epoch_participation = EpochParticipation(
        # [Modified in PQ]
        data=[ParticipationFlags(0b0000_0000) for _ in range(len(state.pq_validators))]
    )
```

#### Modified `process_pending_consolidations`

```python
def process_pending_consolidations(state: BeaconState) -> None:
    next_epoch = get_current_epoch(state) + 1
    next_pending_consolidation = 0
    for pending_consolidation in state.pending_consolidations:
        # [Modified in PQ]
        source_validator = state.pq_validators[pending_consolidation.source_index]
        if source_validator.slashed:
            next_pending_consolidation += 1
            continue
        if source_validator.withdrawable_epoch > next_epoch:
            break

        # Calculate the consolidated balance
        source_effective_balance = min(
            state.balances[pending_consolidation.source_index], source_validator.effective_balance
        )

        # Move active balance to target. Excess balance is withdrawable.
        decrease_balance(state, pending_consolidation.source_index, source_effective_balance)
        increase_balance(state, pending_consolidation.target_index, source_effective_balance)
        next_pending_consolidation += 1

    state.pending_consolidations = state.pending_consolidations[next_pending_consolidation:]
```

#### Modified `process_pending_deposits`

```python
def process_pending_deposits(state: BeaconState) -> None:
    next_epoch = get_current_epoch(state) + 1
    # Deposits still consume the activation-only churn budget in Gloas.
    available_for_processing = state.deposit_balance_to_consume + get_activation_churn_limit(state)
    processed_amount = 0
    next_deposit_index = 0
    deposits_to_postpone = []
    is_churn_limit_reached = False
    finalized_slot = compute_start_slot_at_epoch(state.finalized_checkpoint.epoch)

    for deposit in state.pending_deposits:
        # Check if deposit has been finalized, otherwise, stop processing.
        if deposit.slot > finalized_slot:
            break

        # Check if number of processed deposits has not reached the limit, otherwise, stop processing.
        if next_deposit_index >= MAX_PENDING_DEPOSITS_PER_EPOCH:
            break

        # Read validator state
        is_validator_exited = False
        is_validator_withdrawn = False
        validator_pubkeys = [validator.pubkey for validator in state.validators]
        if deposit.pubkey in validator_pubkeys:
            # [Modified in PQ]
            validator = state.pq_validators[ValidatorIndex(validator_pubkeys.index(deposit.pubkey))]
            is_validator_exited = validator.exit_epoch < FAR_FUTURE_EPOCH
            is_validator_withdrawn = validator.withdrawable_epoch < next_epoch

        # [Modified in PQ]
        if deposit.pubkey not in validator_pubkeys:
            # A new validator has no XMSS public key, postpone the deposit without consuming churn
            deposits_to_postpone.append(deposit)
        elif is_validator_withdrawn:
            # Deposited balance will never become active. Increase balance but do not consume churn
            apply_pending_deposit(state, deposit)
        elif is_validator_exited:
            # Validator is exiting, postpone the deposit until after withdrawable epoch
            deposits_to_postpone.append(deposit)
        else:
            # Check if deposit fits in the churn, otherwise, do no more deposit processing in this epoch.
            is_churn_limit_reached = processed_amount + deposit.amount > available_for_processing
            if is_churn_limit_reached:
                break

            # Consume churn and apply deposit.
            processed_amount += deposit.amount
            apply_pending_deposit(state, deposit)

        # Regardless of how the deposit was handled, we move on in the queue.
        next_deposit_index += 1

    state.pending_deposits = state.pending_deposits[next_deposit_index:] + deposits_to_postpone

    # Accumulate churn only if the churn limit has been hit.
    if is_churn_limit_reached:
        state.deposit_balance_to_consume = available_for_processing - processed_amount
    else:
        state.deposit_balance_to_consume = Gwei(0)
```

#### Modified `apply_pending_deposit`

*Note*: `process_pending_deposits` postpones every deposit for a new public key,
so a pending deposit is only ever applied to an existing validator.

```python
def apply_pending_deposit(state: BeaconState, deposit: PendingDeposit) -> None:
    """
    Applies ``deposit`` to the ``state``.
    """
    validator_pubkeys = [validator.pubkey for validator in state.validators]
    # [Modified in PQ]
    # Removed the creation of a new validator
    validator_index = ValidatorIndex(validator_pubkeys.index(deposit.pubkey))
    increase_balance(state, validator_index, deposit.amount)
```

#### Modified `process_registry_updates`

```python
def process_registry_updates(state: BeaconState) -> None:
    current_epoch = get_current_epoch(state)
    activation_epoch = compute_activation_exit_epoch(current_epoch)

    # Process activation eligibility, ejections, and activations
    # [Modified in PQ]
    for index, validator in enumerate(state.pq_validators):
        if is_eligible_for_activation_queue(validator):
            validator.activation_eligibility_epoch = current_epoch + 1
        elif (
            is_active_validator(validator, current_epoch)
            and validator.effective_balance <= EJECTION_BALANCE
        ):
            initiate_validator_exit(state, ValidatorIndex(index))
        elif is_eligible_for_activation(state, validator):
            validator.activation_epoch = activation_epoch
```

#### Modified `process_rewards_and_penalties`

```python
def process_rewards_and_penalties(state: BeaconState) -> None:
    # No rewards are applied at the end of `GENESIS_EPOCH` because rewards are for work done in the previous epoch
    if get_current_epoch(state) == GENESIS_EPOCH:
        return

    flag_deltas = [
        get_flag_index_deltas(state, flag_index)
        for flag_index in range(len(PARTICIPATION_FLAG_WEIGHTS))
    ]
    deltas = flag_deltas + [get_inactivity_penalty_deltas(state)]
    for rewards, penalties in deltas:
        # [Modified in PQ]
        for index in range(len(state.pq_validators)):
            increase_balance(state, ValidatorIndex(index), rewards[index])
            decrease_balance(state, ValidatorIndex(index), penalties[index])
```

#### Modified `process_slashings`

```python
def process_slashings(state: BeaconState) -> None:
    epoch = get_current_epoch(state)
    total_balance = get_total_active_balance(state)
    adjusted_total_slashing_balance = min(
        Gwei(sum(state.slashings)) * PROPORTIONAL_SLASHING_MULTIPLIER_BELLATRIX, total_balance
    )
    increment = (
        EFFECTIVE_BALANCE_INCREMENT  # Factored out from total balance to avoid Uint64 overflow
    )
    penalty_per_effective_balance_increment = adjusted_total_slashing_balance // (
        total_balance // increment
    )
    # [Modified in PQ]
    for index, validator in enumerate(state.pq_validators):
        if (
            validator.slashed
            and epoch + EPOCHS_PER_SLASHINGS_VECTOR // 2 == validator.withdrawable_epoch
        ):
            effective_balance_increments = validator.effective_balance // increment
            penalty = penalty_per_effective_balance_increment * effective_balance_increments
            decrease_balance(state, ValidatorIndex(index), penalty)
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

#### Modified `process_block_header`

```python
def process_block_header(state: BeaconState, block: BeaconBlock) -> None:
    # Verify that the slots match
    assert block.slot == state.slot
    # Verify that the block is newer than latest block header
    assert block.slot > state.latest_block_header.slot
    # Verify that proposer index is the correct index
    assert block.proposer_index == get_beacon_proposer_index(state)
    # Verify that the parent matches
    assert block.parent_root == hash_tree_root(state.latest_block_header)
    # Cache current block as the new latest block
    state.latest_block_header = BeaconBlockHeader(
        slot=block.slot,
        proposer_index=block.proposer_index,
        parent_root=block.parent_root,
        state_root=Root(),  # Overwritten in the next process_slot call
        body_root=hash_tree_root(block.body),
    )

    # Verify proposer is not slashed
    # [Modified in PQ]
    proposer = state.pq_validators[block.proposer_index]
    assert not proposer.slashed
```

#### Modified `process_randao`

*Note*: The reveal is the proposer's VRF proof for the slot. The proposer
committed to its leaves when it registered its VRF data, so it cannot grind the
reveal and can only withhold its block, as with BLS.

```python
def process_randao(state: BeaconState, body: BeaconBlockBody) -> None:
    epoch = get_current_epoch(state)
    # [Modified in PQ]
    # Verify RANDAO reveal
    assert is_valid_vrf_proof(
        state, get_beacon_proposer_index(state), state.slot, body.randao_reveal
    )
    # [Modified in PQ]
    # Mix in RANDAO reveal
    prev_randao = get_randao_mix(state, epoch)
    mix = sha256(prev_randao + body.randao_reveal[0] + DOMAIN_RANDAO)
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
        # Removed `VALIDATOR_PQ_REGISTRATION_REQUEST_TYPE`
        # [Modified in PQ]
        # Removed `BUILDER_PQ_REGISTRATION_REQUEST_TYPE`
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
        pubkey = state.pq_validators[validator_index].pubkey
    else:
        # [Modified in PQ]
        pubkey = state.pq_builders[builder_index].pubkey

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
    # [Modified in PQ]
    builder = state.pq_builders[signed_bid.message.builder_index]
    signing_root = compute_signing_root(
        signed_bid.message, get_domain(state, DOMAIN_BEACON_BUILDER)
    )
    # [Modified in PQ]
    leaf_index = compute_xmss_leaf_index(signed_bid.message.slot, LEAF_OFFSET_EXECUTION_PAYLOAD_BID)
    return xmss.Verify(builder.pubkey, leaf_index, signing_root, signed_bid.signature)
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
        # [Modified in PQ]
        assert state.pq_builders[builder_index].version == PAYLOAD_BUILDER_VERSION
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
    # [New in PQ]
    process_stark(state, body)
    for_ops(body.voluntary_exits, process_voluntary_exit)
    # [Modified in PQ]
    # Removed `process_bls_to_execution_change`
    # [Modified in PQ]
    # Removed `process_payload_attestation`
```

##### New `process_stark`

```python
def process_stark(state: BeaconState, body: BeaconBlockBody) -> None:
    statements = []
    for attestation in body.attestations:
        statements.extend(get_attestation_statements(state, attestation))
    assert stark.VerifyAggregates(statements, body.stark)
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
    # [Modified in PQ]
    proposer = state.pq_validators[header_1.proposer_index]
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
    # [Modified in PQ]
    validator = state.pq_validators[voluntary_exit.validator_index]
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
    assert xmss.Verify(
        validator.pubkey,
        RESERVED_LEAF_VOLUNTARY_EXIT,
        signing_root,
        signed_voluntary_exit.signature,
    )
    # Initiate exit
    initiate_validator_exit(state, voluntary_exit.validator_index)
```

##### Attestations

###### Modified `process_attestation`

*Note*: An attestation no longer carries a signature, so `process_stark`
verifies the signatures of all attestations in the block instead.

```python
def process_attestation(
    state: BeaconState,
    attestation: Attestation,
    parent_slot: Slot,
) -> None:
    data = attestation.data
    assert data.target.epoch in (get_previous_epoch(state), get_current_epoch(state))
    assert data.target.epoch == compute_epoch_at_slot(data.slot)
    assert data.slot + MIN_ATTESTATION_INCLUSION_DELAY <= state.slot

    assert data.index < 2
    committee_indices = get_committee_indices(attestation.committee_bits)
    committee_offset = 0
    for committee_index in committee_indices:
        assert committee_index < get_committee_count_per_slot(state, data.target.epoch)
        committee = get_beacon_committee(state, data.slot, committee_index)
        committee_attesters = {
            attester_index
            for index, attester_index in enumerate(committee)
            if attestation.aggregation_bits[committee_offset + index]
        }
        assert len(committee_attesters) > 0
        committee_offset += len(committee)

    # Bitfield length matches total number of participants
    assert len(attestation.aggregation_bits) == committee_offset

    # Participation flag indices
    participation_flag_indices = get_attestation_participation_flag_indices(
        state, data, state.slot - data.slot, parent_slot
    )

    if data.target.epoch == get_current_epoch(state):
        current_epoch_target = True
        epoch_participation = state.current_epoch_participation
        payment = state.builder_pending_payments[SLOTS_PER_EPOCH + data.slot % SLOTS_PER_EPOCH]
    else:
        current_epoch_target = False
        epoch_participation = state.previous_epoch_participation
        payment = state.builder_pending_payments[data.slot % SLOTS_PER_EPOCH]

    proposer_reward_numerator = 0
    for index in get_attesting_indices(state, attestation):
        had_no_participation = epoch_participation[index] == 0b0000_0000
        will_set_new_flag = False

        for flag_index, weight in enumerate(PARTICIPATION_FLAG_WEIGHTS):
            if flag_index in participation_flag_indices and not has_flag(
                epoch_participation[index], flag_index
            ):
                epoch_participation[index] = add_flag(epoch_participation[index], flag_index)
                proposer_reward_numerator += get_base_reward(state, index) * weight
                will_set_new_flag = True

        if (
            will_set_new_flag
            and had_no_participation
            and is_attestation_same_slot(state, data)
            and payment.withdrawal.amount > 0
        ):
            # [Modified in PQ]
            payment.weight += state.pq_validators[index].effective_balance

    # Reward proposer
    proposer_reward_denominator = (
        (WEIGHT_DENOMINATOR - PROPOSER_WEIGHT) * WEIGHT_DENOMINATOR // PROPOSER_WEIGHT
    )
    proposer_reward = Gwei(proposer_reward_numerator // proposer_reward_denominator)
    increase_balance(state, get_beacon_proposer_index(state), proposer_reward)

    # Update builder payment weight
    if current_epoch_target:
        state.builder_pending_payments[SLOTS_PER_EPOCH + data.slot % SLOTS_PER_EPOCH] = payment
    else:
        state.builder_pending_payments[data.slot % SLOTS_PER_EPOCH] = payment
```

##### Modified `process_attester_slashing`

```python
def process_attester_slashing(state: BeaconState, attester_slashing: AttesterSlashing) -> None:
    attestation_1 = attester_slashing.attestation_1
    attestation_2 = attester_slashing.attestation_2
    assert is_slashable_attestation_data(attestation_1.data, attestation_2.data)
    assert is_valid_indexed_attestation(state, attestation_1)
    assert is_valid_indexed_attestation(state, attestation_2)

    slashed_any = False
    indices = set(attestation_1.attesting_indices).intersection(attestation_2.attesting_indices)
    for index in sorted(indices):
        # [Modified in PQ]
        if is_slashable_validator(state.pq_validators[index], get_current_epoch(state)):
            slash_validator(state, index)
            slashed_any = True
    assert slashed_any
```

##### Builder deposit requests

###### Modified `process_builder_deposit_request`

*Note*: A builder deposit names its builder by BLS public key, which
`state.pq_builders` does not hold, so it waits in
`state.pending_builder_deposits`, which no function processes yet.

```python
def process_builder_deposit_request(state: BeaconState, request: BuilderDepositRequest) -> None:
    # Ignore deposits with unexpected withdrawal credential prefixes
    if not is_builder_withdrawal_credential(request.withdrawal_credentials):
        return

    # [Modified in PQ]
    state.pending_builder_deposits.append(
        PendingDeposit(
            pubkey=request.pubkey,
            withdrawal_credentials=request.withdrawal_credentials,
            amount=request.amount,
            signature=request.signature,
            slot=state.slot,
        )
    )
```

##### Builder exit requests

###### Modified `process_builder_exit_request`

*Note*: A builder exit request names its builder by BLS public key, which
`state.pq_builders` does not hold, so it is ignored.

```python
def process_builder_exit_request(state: BeaconState, request: BuilderExitRequest) -> None:
    # [Modified in PQ]
    # Removed the processing of the request
    pass
```

##### Execution-layer withdrawal requests

###### Modified `process_withdrawal_request`

*Note*: A withdrawal request names its validator by BLS public key, which
`state.pq_validators` does not hold, so it is ignored.

```python
def process_withdrawal_request(state: BeaconState, withdrawal_request: WithdrawalRequest) -> None:
    # [Modified in PQ]
    # Removed the processing of the request
    pass
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
    # Removed the validator and builder PQ registration request limits

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
    # Removed `process_validator_pq_registration_request`
    # [Modified in PQ]
    # Removed `process_builder_pq_registration_request`

    # Update parent payload availability and latest block hash
    state.execution_payload_availability[parent_slot % SLOTS_PER_HISTORICAL_ROOT] = Boolean(True)
    state.latest_block_hash = parent_bid.block_hash
```

#### Withdrawals

##### Modified `apply_withdrawals`

```python
def apply_withdrawals(state: BeaconState, withdrawals: Sequence[Withdrawal]) -> None:
    for withdrawal in withdrawals:
        if is_builder_index(withdrawal.validator_index):
            builder_index = convert_validator_index_to_builder_index(withdrawal.validator_index)
            # [Modified in PQ]
            state.pq_builders[builder_index].balance = saturating_sub(
                # [Modified in PQ]
                state.pq_builders[builder_index].balance,
                withdrawal.amount,
            )
        else:
            decrease_balance(state, withdrawal.validator_index, withdrawal.amount)
```

##### Modified `get_builder_balance_after_withdrawals`

```python
def get_builder_balance_after_withdrawals(
    state: BeaconState, builder_index: BuilderIndex, withdrawals: Sequence[Withdrawal]
) -> Gwei:
    validator_index = convert_builder_index_to_validator_index(builder_index)
    withdrawn = Gwei(
        sum(
            withdrawal.amount
            for withdrawal in withdrawals
            if withdrawal.validator_index == validator_index
        )
    )
    # [Modified in PQ]
    return saturating_sub(state.pq_builders[builder_index].balance, withdrawn)
```

##### Modified `get_builders_sweep_withdrawals`

```python
def get_builders_sweep_withdrawals(
    state: BeaconState,
    withdrawal_index: WithdrawalIndex,
    prior_withdrawals: Sequence[Withdrawal],
) -> tuple[Sequence[Withdrawal], WithdrawalIndex, Uint64]:
    epoch = get_current_epoch(state)
    # [Modified in PQ]
    builders_limit = min(len(state.pq_builders), MAX_BUILDERS_PER_WITHDRAWALS_SWEEP)
    withdrawals_limit = MAX_WITHDRAWALS_PER_PAYLOAD - 1
    assert len(prior_withdrawals) <= withdrawals_limit

    processed_count = Uint64(0)
    withdrawals: list[Withdrawal] = []
    builder_index = state.next_withdrawal_builder_index
    for _ in range(builders_limit):
        all_withdrawals = list(prior_withdrawals) + withdrawals
        has_reached_limit = len(all_withdrawals) >= withdrawals_limit
        if has_reached_limit:
            break

        # [Modified in PQ]
        builder = state.pq_builders[builder_index]
        balance = get_builder_balance_after_withdrawals(state, builder_index, all_withdrawals)
        if builder.withdrawable_epoch <= epoch and balance > 0:
            withdrawals.append(
                Withdrawal(
                    index=withdrawal_index,
                    validator_index=convert_builder_index_to_validator_index(builder_index),
                    address=builder.execution_address,
                    amount=balance,
                )
            )
            withdrawal_index += 1

        # [Modified in PQ]
        builder_index = (builder_index + 1) % len(state.pq_builders)
        processed_count += 1

    return withdrawals, withdrawal_index, processed_count
```

##### Modified `get_pending_partial_withdrawals`

```python
def get_pending_partial_withdrawals(
    state: BeaconState,
    withdrawal_index: WithdrawalIndex,
    prior_withdrawals: Sequence[Withdrawal],
) -> tuple[Sequence[Withdrawal], WithdrawalIndex, Uint64]:
    epoch = get_current_epoch(state)
    withdrawals_limit = min(
        len(prior_withdrawals) + MAX_PENDING_PARTIALS_PER_WITHDRAWALS_SWEEP,
        MAX_WITHDRAWALS_PER_PAYLOAD - 1,
    )
    assert len(prior_withdrawals) <= withdrawals_limit

    processed_count = Uint64(0)
    withdrawals: list[Withdrawal] = []
    for withdrawal in state.pending_partial_withdrawals:
        all_withdrawals = list(prior_withdrawals) + withdrawals
        is_withdrawable = withdrawal.withdrawable_epoch <= epoch
        has_reached_limit = len(all_withdrawals) >= withdrawals_limit
        if not is_withdrawable or has_reached_limit:
            break

        validator_index = withdrawal.validator_index
        # [Modified in PQ]
        validator = state.pq_validators[validator_index]
        balance = get_balance_after_withdrawals(state, validator_index, all_withdrawals)
        if is_eligible_for_partial_withdrawals(validator, balance):
            withdrawal_amount = min(balance - MIN_ACTIVATION_BALANCE, withdrawal.amount)
            withdrawals.append(
                Withdrawal(
                    index=withdrawal_index,
                    validator_index=validator_index,
                    address=ExecutionAddress(validator.withdrawal_credentials[12:]),
                    amount=withdrawal_amount,
                )
            )
            withdrawal_index += 1

        processed_count += 1

    return withdrawals, withdrawal_index, processed_count
```

##### Modified `get_validators_sweep_withdrawals`

```python
def get_validators_sweep_withdrawals(
    state: BeaconState,
    withdrawal_index: WithdrawalIndex,
    prior_withdrawals: Sequence[Withdrawal],
) -> tuple[Sequence[Withdrawal], WithdrawalIndex, Uint64]:
    epoch = get_current_epoch(state)
    # [Modified in PQ]
    validators_limit = min(len(state.pq_validators), MAX_VALIDATORS_PER_WITHDRAWALS_SWEEP)
    withdrawals_limit = MAX_WITHDRAWALS_PER_PAYLOAD
    # There must be at least one space reserved for validator sweep withdrawals
    assert len(prior_withdrawals) < withdrawals_limit

    processed_count = Uint64(0)
    withdrawals: list[Withdrawal] = []
    validator_index = state.next_withdrawal_validator_index
    for _ in range(validators_limit):
        all_withdrawals = list(prior_withdrawals) + withdrawals
        has_reached_limit = len(all_withdrawals) >= withdrawals_limit
        if has_reached_limit:
            break

        # [Modified in PQ]
        validator = state.pq_validators[validator_index]
        balance = get_balance_after_withdrawals(state, validator_index, all_withdrawals)
        if is_fully_withdrawable_validator(validator, balance, epoch):
            withdrawals.append(
                Withdrawal(
                    index=withdrawal_index,
                    validator_index=validator_index,
                    address=ExecutionAddress(validator.withdrawal_credentials[12:]),
                    amount=balance,
                )
            )
            withdrawal_index += 1
        elif is_partially_withdrawable_validator(validator, balance):
            withdrawals.append(
                Withdrawal(
                    index=withdrawal_index,
                    validator_index=validator_index,
                    address=ExecutionAddress(validator.withdrawal_credentials[12:]),
                    amount=balance - get_max_effective_balance(validator),
                )
            )
            withdrawal_index += 1

        # [Modified in PQ]
        validator_index = (validator_index + 1) % len(state.pq_validators)
        processed_count += 1

    return withdrawals, withdrawal_index, processed_count
```

##### Modified `update_next_withdrawal_builder_index`

```python
def update_next_withdrawal_builder_index(
    state: BeaconState, processed_builders_sweep_count: Uint64
) -> None:
    # [Modified in PQ]
    if len(state.pq_builders) > 0:
        # Update the next builder index to start the next withdrawal sweep
        next_index = state.next_withdrawal_builder_index + processed_builders_sweep_count
        # [Modified in PQ]
        next_builder_index = next_index % len(state.pq_builders)
        state.next_withdrawal_builder_index = next_builder_index
```

##### Modified `update_next_withdrawal_validator_index`

```python
def update_next_withdrawal_validator_index(
    state: BeaconState, withdrawals: Sequence[Withdrawal]
) -> None:
    # Update the next validator index to start the next withdrawal sweep
    if len(withdrawals) == MAX_WITHDRAWALS_PER_PAYLOAD:
        # Next sweep starts after the latest withdrawal's validator index
        # [Modified in PQ]
        next_validator_index = (withdrawals[-1].validator_index + 1) % len(state.pq_validators)
        state.next_withdrawal_validator_index = next_validator_index
    else:
        # Advance sweep by the max length of the sweep if there was not a full set of withdrawals
        next_index = state.next_withdrawal_validator_index + MAX_VALIDATORS_PER_WITHDRAWALS_SWEEP
        # [Modified in PQ]
        next_validator_index = next_index % len(state.pq_validators)
        state.next_withdrawal_validator_index = next_validator_index
```
