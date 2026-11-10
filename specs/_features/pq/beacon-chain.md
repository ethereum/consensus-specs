# PQ -- The Beacon Chain

*Note*: This document is a work-in-progress for researchers and implementers.

<!-- mdformat-toc start --slug=github --no-anchors --maxlevel=6 --minlevel=2 -->

- [Introduction](#introduction)
- [Types](#types)
  - [New `VRFProof`](#new-vrfproof)
  - [New `AttestationProof`](#new-attestationproof)
  - [New `XMSSPubkey`](#new-xmsspubkey)
  - [New `XMSSSignature`](#new-xmsssignature)
  - [New `PreregistrationRequests`](#new-preregistrationrequests)
  - [New `ValidatorPreregistrations`](#new-validatorpreregistrations)
- [Constants](#constants)
  - [XMSS](#xmss)
  - [VRF](#vrf)
  - [XMSS leaf offsets](#xmss-leaf-offsets)
  - [XMSS reserved leaves](#xmss-reserved-leaves)
  - [Deposits](#deposits)
  - [Legacy domains](#legacy-domains)
  - [Domains](#domains)
  - [Execution-layer triggered requests](#execution-layer-triggered-requests)
- [Presets](#presets)
  - [XMSS](#xmss-1)
  - [Max operations per block](#max-operations-per-block)
  - [Execution](#execution)
- [Containers](#containers)
  - [Modified containers](#modified-containers)
    - [`Attestation`](#attestation)
    - [`BeaconBlockBody`](#beaconblockbody)
    - [`BeaconState`](#beaconstate)
    - [`Builder`](#builder)
    - [`BuilderDepositRequest`](#builderdepositrequest)
    - [`BuilderExitRequest`](#builderexitrequest)
    - [`ConsolidationRequest`](#consolidationrequest)
    - [`DepositRequest`](#depositrequest)
    - [`ExecutionRequests`](#executionrequests)
    - [`IndexedAttestation`](#indexedattestation)
    - [`PayloadAttestationMessage`](#payloadattestationmessage)
    - [`PendingDeposit`](#pendingdeposit)
    - [`SignedBeaconBlock`](#signedbeaconblock)
    - [`SignedBeaconBlockHeader`](#signedbeaconblockheader)
    - [`SignedExecutionPayloadBid`](#signedexecutionpayloadbid)
    - [`SignedExecutionPayloadEnvelope`](#signedexecutionpayloadenvelope)
    - [`SignedVoluntaryExit`](#signedvoluntaryexit)
    - [`SingleAttestation`](#singleattestation)
    - [`Validator`](#validator)
    - [`WithdrawalRequest`](#withdrawalrequest)
  - [New containers](#new-containers)
    - [`ValidatorPreregistration`](#validatorpreregistration)
    - [`PreregistrationRequest`](#preregistrationrequest)
    - [`StoredPreregistration`](#storedpreregistration)
- [Dataclasses](#dataclasses)
  - [New dataclasses](#new-dataclasses)
    - [`XMSSAggregateStatement`](#xmssaggregatestatement)
- [Helpers](#helpers)
  - [Crypto](#crypto)
    - [XMSS signatures](#xmss-signatures)
    - [STARK proofs](#stark-proofs)
  - [Misc](#misc)
    - [New `compute_deposit_pubkey`](#new-compute_deposit_pubkey)
    - [New `compute_deposit_vrf_root`](#new-compute_deposit_vrf_root)
    - [New `compute_xmss_attestation_leaf_index`](#new-compute_xmss_attestation_leaf_index)
    - [New `compute_xmss_leaf_index`](#new-compute_xmss_leaf_index)
  - [Predicates](#predicates)
    - [New `is_active_preregistration`](#new-is_active_preregistration)
    - [New `is_legacy_pubkey`](#new-is_legacy_pubkey)
    - [New `is_valid_preregistration_signature`](#new-is_valid_preregistration_signature)
    - [New `is_valid_vrf_proof`](#new-is_valid_vrf_proof)
    - [Modified `is_pending_validator`](#modified-is_pending_validator)
    - [Modified `is_valid_indexed_attestation`](#modified-is_valid_indexed_attestation)
  - [Beacon state accessors](#beacon-state-accessors)
    - [Modified `get_indexed_attestation`](#modified-get_indexed_attestation)
    - [New `get_attestation_statements`](#new-get_attestation_statements)
    - [New `get_stored_preregistration_index`](#new-get_stored_preregistration_index)
    - [New `get_active_preregistration`](#new-get_active_preregistration)
  - [Beacon state mutators](#beacon-state-mutators)
    - [Modified `queue_excess_active_balance`](#modified-queue_excess_active_balance)
    - [New `remove_stored_preregistration`](#new-remove_stored_preregistration)
- [Beacon chain state transition function](#beacon-chain-state-transition-function)
  - [Modified `verify_block_signature`](#modified-verify_block_signature)
  - [Epoch processing](#epoch-processing)
    - [Modified `process_epoch`](#modified-process_epoch)
    - [New `process_preregistration_expiry`](#new-process_preregistration_expiry)
    - [Modified `apply_pending_deposit`](#modified-apply_pending_deposit)
    - [Modified `process_pending_deposits`](#modified-process_pending_deposits)
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
      - [New `process_stark`](#new-process_stark)
      - [Modified `process_proposer_slashing`](#modified-process_proposer_slashing)
      - [Modified `process_voluntary_exit`](#modified-process_voluntary_exit)
      - [Attestations](#attestations)
        - [Modified `process_attestation`](#modified-process_attestation)
      - [Deposit requests](#deposit-requests)
        - [Modified `process_deposit_request`](#modified-process_deposit_request)
        - [Modified `get_validator_from_deposit`](#modified-get_validator_from_deposit)
        - [Modified `add_validator_to_registry`](#modified-add_validator_to_registry)
      - [Builder deposit requests](#builder-deposit-requests)
        - [Modified `add_builder_to_registry`](#modified-add_builder_to_registry)
        - [Modified `process_builder_deposit_request`](#modified-process_builder_deposit_request)
      - [Builder exit requests](#builder-exit-requests)
        - [Modified `process_builder_exit_request`](#modified-process_builder_exit_request)
      - [Execution-layer withdrawal requests](#execution-layer-withdrawal-requests)
        - [Modified `process_withdrawal_request`](#modified-process_withdrawal_request)
      - [Execution-layer consolidation requests](#execution-layer-consolidation-requests)
        - [Modified `is_valid_switch_to_compounding_request`](#modified-is_valid_switch_to_compounding_request)
        - [Modified `process_consolidation_request`](#modified-process_consolidation_request)
      - [Preregistration requests](#preregistration-requests)
        - [New `process_preregistration_request`](#new-process_preregistration_request)
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
with them the light client protocol.

XMSS is a stateful scheme. A key covers a fixed number of one-time leaves, and
signing two different messages at the same leaf breaks the key. This upgrade
therefore assigns every validator message a leaf derived from its slot and its
type, see `compute_xmss_leaf_index`. An attestation instead uses the leaf of its
target epoch, see `compute_xmss_attestation_leaf_index`. A message that a key
signs at most once, such as a voluntary exit, instead uses one of the first
`XMSS_RESERVED_LEAVES` leaves. An honest signer that never equivocates never
reuses a leaf. Each signature carries its leaf index, and verification checks it
against the expected one.

XMSS has no native aggregation. A STARK instead proves many XMSS signatures at
once, such as those of attestations in an `AttestationProof`.

XMSS signatures are not unique, so a proposer could grind a signature-based
RANDAO reveal. Each validator instead registers the root of a Merkle tree of
secret random values, one for each slot, as its VRF root. Its RANDAO reveal is
the leaf for the slot with the leaf's Merkle branch, a `VRFProof`, which the
proposer committed to before the fork. The same proof serves as its selection
proof when it aggregates.

A validator's record carries the XMSS public key and VRF root it registered with
EIP-8483 before the fork in place of its BLS public key, and a builder's record
the XMSS public key it registered. Validators and builders that did not register
are withdrawn at the fork. See [the fork document](./fork.md) for details.

Execution layer requests keep their formats. A request's 48-byte public key
field is 16 zero bytes followed by an XMSS public key. Deposits no longer carry
a signature. Instead, the first 32 bytes of a deposit's 96-byte signature field
are the VRF root of the validator it creates. A legacy request made before the
fork names a BLS public key instead, whose first byte always has its top bit
set. A legacy deposit's validator takes the XMSS public key and VRF root that a
validator that did not register takes at the fork, and it is exited at once, so
the validator sweep refunds its balance after the withdrawability delay. A
legacy builder deposit's builder is keyed the same way and initiates its exit at
once. A legacy withdrawal or consolidation request is ignored.

Without deposit signatures, anyone who sees the first deposit for a new XMSS
public key could get in first with a deposit of their own withdrawal credentials
and VRF root. As in [EIP-8205](../eip8205/beacon-chain.md), the holder of a key
can first bind the key to its withdrawal credentials and VRF root with a
preregistration request, signed by the key at `RESERVED_LEAF_PREREGISTRATION`.
While the binding is active, a deposit for the key is discarded unless it
matches the binding. A key signs only one binding, so a different binding needs
a new key.

`BLSToExecutionChange` is disabled, because its BLS signature could be forged.

Blocks no longer carry payload attestations, which spares proposers from
aggregating them. The payload timeliness committee still broadcasts its votes,
which fork choice uses as before.

Attestations no longer carry a signature. A block instead carries one `proof` of
the signatures of all its attestations, which replaces verifying each
attestation's aggregate signature in turn. An aggregate on the wire carries a
`proof` of its own in `AggregateAndProof`, and the proposer merges those into
the block's `proof`.

*Note*: This specification is built upon [EIP-8483](../eip8483/beacon-chain.md),
which is built upon [Gloas](../../gloas/beacon-chain.md).

## Types

### New `VRFProof`

```python
class VRFProof(Vector[Bytes32]):
    """
    A leaf of the tree under a validator's VRF root, followed by the leaf's
    Merkle branch.
    """

    LENGTH = VRF_TREE_DEPTH + 1
```

### New `AttestationProof`

```python
class AttestationProof(ByteList):
    """
    A STARK proof of the XMSS signatures of attestations.
    """

    LIMIT = MAX_STARK_PROOF_SIZE
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

### New `PreregistrationRequests`

```python
class PreregistrationRequests(ProgressiveList[PreregistrationRequest]):
    """
    The preregistration requests pertaining to a single execution payload.
    """
```

### New `ValidatorPreregistrations`

```python
class ValidatorPreregistrations(ProgressiveList[StoredPreregistration]):
    """
    The preregistrations stored in the beacon state, including expired
    records not yet garbage-collected.
    """
```

## Constants

### XMSS

| Name                      | Value                           |
| ------------------------- | ------------------------------- |
| `XMSS_SIGNATURE_SIZE`     | `Uint64(2404)`                  |
| `XMSS_RESERVED_LEAVES`    | `Uint64(2**15)` (= 32,768)      |
| `XMSS_ATTESTATION_LEAVES` | `Uint64(2**29)` (= 536,870,912) |
| `XMSS_LEAVES_PER_SLOT`    | `Uint64(2**3)` (= 8)            |

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

| Name                            | Value       |
| ------------------------------- | ----------- |
| `RESERVED_LEAF_PREREGISTRATION` | `Uint64(0)` |
| `RESERVED_LEAF_VOLUNTARY_EXIT`  | `Uint64(1)` |

### Deposits

| Name                  | Value       |
| --------------------- | ----------- |
| `XMSS_DEPOSIT_PREFIX` | `Bytes16()` |

### Legacy domains

| Name                        | Value            |
| --------------------------- | ---------------- |
| `LEGACY_XMSS_PUBKEY_DOMAIN` | `Bytes1("0x00")` |
| `LEGACY_VRF_ROOT_DOMAIN`    | `Bytes1("0x01")` |

### Domains

*Note*: As in EIP-8205, preregistration signatures use a fork-agnostic domain
bound to the chain through `genesis_validators_root`.

| Name                     | Value                      |
| ------------------------ | -------------------------- |
| `DOMAIN_PREREGISTRATION` | `DomainType("0x11000000")` |

### Execution-layer triggered requests

| Name                           | Value            |
| ------------------------------ | ---------------- |
| `PREREGISTRATION_REQUEST_TYPE` | `Bytes1("0x07")` |

## Presets

### XMSS

| Name                   | Value                         |
| ---------------------- | ----------------------------- |
| `MAX_STARK_PROOF_SIZE` | `Uint64(2**20)` (= 1,048,576) |

*Note*: `MAX_STARK_PROOF_SIZE` is a placeholder for the size of a STARK proof.
The reference concatenation fits at most
`MAX_STARK_PROOF_SIZE // XMSS_SIGNATURE_SIZE` signatures in a proof.

### Max operations per block

| Name                  | Value                 |
| --------------------- | --------------------- |
| `MAX_ATTESTATIONS_PQ` | `Uint64(2**4)` (= 16) |

### Execution

| Name                                       | Value                       |
| ------------------------------------------ | --------------------------- |
| `MAX_PREREGISTRATION_REQUESTS_PER_PAYLOAD` | `Uint64(2**2)` (= 4)        |
| `PREREGISTRATIONS_LIMIT`                   | `Uint64(2**19)` (= 524,288) |
| `PREREGISTRATION_EXPIRY_SLOTS`             | `Slot(2**18)` (= 262,144)   |

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
    proof: AttestationProof
```

#### `BeaconState`

```python
class BeaconState(ProgressiveContainer):
    ACTIVE_FIELDS = active_fields(width=49, gaps=(22, 23, 46, 47))

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
    # [New in EIP8205]
    validator_preregistrations: ValidatorPreregistrations
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
    pubkey: Bytes48
    withdrawal_credentials: Bytes32
    amount: Gwei
    # [Modified in PQ]
    signature: Bytes96
```

#### `BuilderExitRequest`

```python
class BuilderExitRequest(Container):
    source_address: ExecutionAddress
    # [Modified in PQ]
    pubkey: Bytes48
```

#### `ConsolidationRequest`

```python
class ConsolidationRequest(Container):
    source_address: ExecutionAddress
    # [Modified in PQ]
    source_pubkey: Bytes48
    # [Modified in PQ]
    target_pubkey: Bytes48
```

#### `DepositRequest`

```python
class DepositRequest(Container):
    # [Modified in PQ]
    pubkey: Bytes48
    withdrawal_credentials: Bytes32
    amount: Gwei
    # [Modified in PQ]
    signature: Bytes96
    index: Uint64
```

#### `ExecutionRequests`

```python
class ExecutionRequests(ProgressiveContainer):
    ACTIVE_FIELDS = active_fields(width=8, gaps=(5, 6))

    deposits: DepositRequests
    withdrawals: WithdrawalRequests
    consolidations: ConsolidationRequests
    builder_deposits: BuilderDepositRequests
    builder_exits: BuilderExitRequests
    # [Modified in PQ]
    # Removed `validator_pq_registrations`
    # [Modified in PQ]
    # Removed `builder_pq_registrations`
    # [New in EIP8205]
    preregistrations: PreregistrationRequests
```

#### `IndexedAttestation`

```python
class IndexedAttestation(ProgressiveContainer):
    ACTIVE_FIELDS = active_fields(width=3)

    attesting_indices: AttestingIndices
    data: AttestationData
    # [Modified in PQ]
    # Removed `signature`
    # [New in PQ]
    proof: AttestationProof
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
    pubkey: Bytes48
    withdrawal_credentials: Bytes32
    amount: Gwei
    # [Modified in PQ]
    signature: Bytes96
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

#### `Validator`

```python
class Validator(Container):
    # [Modified in PQ]
    pubkey: XMSSPubkey
    # [New in PQ]
    vrf_root: Root
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
    validator_pubkey: Bytes48
    amount: Gwei
```

### New containers

#### `ValidatorPreregistration`

*Note*: This is the signing container for preregistration signatures.

```python
class ValidatorPreregistration(Container):
    pubkey: XMSSPubkey
    withdrawal_credentials: Bytes32
    vrf_root: Root
```

#### `PreregistrationRequest`

```python
class PreregistrationRequest(Container):
    pubkey: XMSSPubkey
    withdrawal_credentials: Bytes32
    vrf_root: Root
    signature: XMSSSignature
```

#### `StoredPreregistration`

*Note*: `expiry_slot` is the absolute deadline computed when the preregistration
is stored. A later change to `PREREGISTRATION_EXPIRY_SLOTS` therefore affects
only newly stored records.

```python
class StoredPreregistration(Container):
    pubkey: XMSSPubkey
    withdrawal_credentials: Bytes32
    vrf_root: Root
    expiry_slot: Slot
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

`Verify` returns `True` only if `signature` was produced at `leaf_index`.

The above functions are accessed through the `xmss` module, e.g. `xmss.Verify`.

#### STARK proofs

This upgrade adds the following functions to prove many XMSS signatures at once:

- `def ProveAggregates(statements: Sequence[XMSSAggregateStatement], signatures: Sequence[Sequence[XMSSSignature]]) -> AttestationProof`
- `def MergeProofs(proofs: Sequence[AttestationProof]) -> AttestationProof`
- `def VerifyAggregates(statements: Sequence[XMSSAggregateStatement], proof: AttestationProof) -> bool`

`VerifyAggregates` returns `True` only if `proof` proves, for each statement and
each of its public keys, a signature that
`xmss.Verify(pubkey, statement.leaf_index, statement.message, signature)`
accepts. `ProveAggregates` takes those signatures for each statement in order,
and within a statement in the order of its public keys. `MergeProofs` turns
proofs of lists of statements into one proof of their concatenation, in order.

The above functions are accessed through the `stark` module, e.g.
`stark.VerifyAggregates`.

*Note*: The reference implementations of `ProveAggregates` and `MergeProofs`
concatenate their inputs, and `VerifyAggregates` checks each signature in turn.
They stand in for a recursive STARK, which would change the encoding of
`AttestationProof` but not how these functions are used.

### Misc

#### New `compute_deposit_pubkey`

```python
def compute_deposit_pubkey(pubkey: Bytes48) -> XMSSPubkey:
    """
    Return the XMSS public key that a deposit naming ``pubkey`` is for.
    """
    if is_legacy_pubkey(pubkey):
        return XMSSPubkey(sha256(pubkey + LEGACY_XMSS_PUBKEY_DOMAIN))
    return XMSSPubkey(pubkey[16:])
```

#### New `compute_deposit_vrf_root`

```python
def compute_deposit_vrf_root(deposit: PendingDeposit) -> Root:
    """
    Return the VRF root of the validator that ``deposit`` creates.
    """
    if is_legacy_pubkey(deposit.pubkey):
        return Root(sha256(deposit.pubkey + LEGACY_VRF_ROOT_DOMAIN))
    return Root(deposit.signature[:32])
```

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

### Predicates

#### New `is_active_preregistration`

*Note*: Activity is evaluated against the slot of the outstanding parent
payload, whose execution requests are the ones being applied during block
processing.

```python
def is_active_preregistration(state: BeaconState, preregistration: StoredPreregistration) -> bool:
    """
    Check if ``preregistration`` has not expired.
    """
    parent_slot = state.latest_execution_payload_bid.slot
    return parent_slot < preregistration.expiry_slot
```

#### New `is_legacy_pubkey`

*Note*: A request made after the upgrade names 16 zero bytes followed by an XMSS
public key. A request made before it names a compressed BLS public key, whose
first byte always has its top bit set as the compression flag.

```python
def is_legacy_pubkey(pubkey: Bytes48) -> bool:
    """
    Check if ``pubkey`` is a BLS public key rather than an XMSS public key.
    """
    return pubkey[:16] != XMSS_DEPOSIT_PREFIX
```

#### New `is_valid_preregistration_signature`

```python
def is_valid_preregistration_signature(state: BeaconState, request: PreregistrationRequest) -> bool:
    """
    Check if ``request`` is signed by its key.
    """
    preregistration = ValidatorPreregistration(
        pubkey=request.pubkey,
        withdrawal_credentials=request.withdrawal_credentials,
        vrf_root=request.vrf_root,
    )
    domain = compute_domain(
        DOMAIN_PREREGISTRATION,
        genesis_validators_root=state.genesis_validators_root,
    )
    signing_root = compute_signing_root(preregistration, domain)
    return xmss.Verify(
        request.pubkey, RESERVED_LEAF_PREREGISTRATION, signing_root, request.signature
    )
```

#### New `is_valid_vrf_proof`

```python
def is_valid_vrf_proof(
    state: BeaconState, validator_index: ValidatorIndex, slot: Slot, proof: VRFProof
) -> bool:
    """
    Check that ``proof`` opens the leaf at index ``slot`` of the tree under
    the VRF root of the validator at ``validator_index``.
    """
    return is_valid_merkle_branch(
        leaf=proof[0],
        branch=proof[1:],
        depth=VRF_TREE_DEPTH,
        index=slot,
        root=state.validators[validator_index].vrf_root,
    )
```

#### Modified `is_pending_validator`

*Note*: Deposits carry no signature, so any pending deposit for the key counts.

```python
def is_pending_validator(
    pending_deposits: Sequence[PendingDeposit],
    # [Modified in PQ]
    pubkey: XMSSPubkey,
) -> bool:
    """
    Check if a pending deposit is in the queue for the given pubkey.
    """
    for pending_deposit in pending_deposits:
        # [Modified in PQ]
        if compute_deposit_pubkey(pending_deposit.pubkey) == pubkey:
            return True
    return False
```

#### Modified `is_valid_indexed_attestation`

*Note*: The `proof` of an indexed attestation proves one statement, over the
public keys of its attesting indices in order.

```python
def is_valid_indexed_attestation(
    state: BeaconState, indexed_attestation: IndexedAttestation
) -> bool:
    """
    Check if ``indexed_attestation`` is not empty, has sorted and unique indices and has a valid stark proof.
    """
    # Verify indices are sorted and unique
    indices = indexed_attestation.attesting_indices
    if (
        len(indices) == 0
        or len(indices) > MAX_VALIDATORS_PER_COMMITTEE * MAX_COMMITTEES_PER_SLOT
        or list(indices) != sorted(set(indices))
    ):
        return False
    # [Modified in PQ]
    # Verify the proof of the attesters' signatures
    pubkeys = [state.validators[index].pubkey for index in indices]
    domain = get_domain(state, DOMAIN_BEACON_ATTESTER, indexed_attestation.data.target.epoch)
    signing_root = compute_signing_root(indexed_attestation.data, domain)
    leaf_index = compute_xmss_attestation_leaf_index(indexed_attestation.data.target.epoch)
    statement = XMSSAggregateStatement(pubkeys=pubkeys, leaf_index=leaf_index, message=signing_root)
    return stark.VerifyAggregates([statement], indexed_attestation.proof)
```

### Beacon state accessors

#### Modified `get_indexed_attestation`

```python
def get_indexed_attestation(
    state: BeaconState,
    attestation: Attestation,
    # [New in PQ]
    proof: AttestationProof,
) -> IndexedAttestation:
    """
    Return the indexed attestation corresponding to ``attestation`` and the
    ``proof`` of its attesters' signatures.
    """
    attesting_indices = get_attesting_indices(state, attestation)

    return IndexedAttestation(
        attesting_indices=AttestingIndices(data=sorted(attesting_indices)),
        data=attestation.data,
        # [Modified in PQ]
        proof=proof,
    )
```

#### New `get_attestation_statements`

*Note*: A network aggregate covers one committee, so its `proof` proves one
statement. Statements are per committee so that the proposer can merge those
proofs into the block's `proof`.

```python
def get_attestation_statements(
    state: BeaconState, attestation: Attestation
) -> Sequence[XMSSAggregateStatement]:
    """
    Return, for each committee of ``attestation`` in order, the statement that the
    signatures of its attesters in that committee prove.
    """
    domain = get_domain(state, DOMAIN_BEACON_ATTESTER, attestation.data.target.epoch)
    message = compute_signing_root(attestation.data, domain)
    leaf_index = compute_xmss_attestation_leaf_index(attestation.data.target.epoch)
    statements = []
    committee_offset = 0
    for committee_index in get_committee_indices(attestation.committee_bits):
        committee = get_beacon_committee(state, attestation.data.slot, committee_index)
        pubkeys = [
            state.validators[validator_index].pubkey
            for i, validator_index in enumerate(committee)
            if attestation.aggregation_bits[committee_offset + i]
        ]
        statements.append(
            XMSSAggregateStatement(pubkeys=pubkeys, leaf_index=leaf_index, message=message)
        )
        committee_offset += len(committee)
    return statements
```

#### New `get_stored_preregistration_index`

```python
def get_stored_preregistration_index(state: BeaconState, pubkey: XMSSPubkey) -> Uint64 | None:
    """
    Return the index of the stored preregistration of ``pubkey``, if any.
    """
    for index, preregistration in enumerate(state.validator_preregistrations):
        if preregistration.pubkey == pubkey:
            return Uint64(index)
    return None
```

#### New `get_active_preregistration`

```python
def get_active_preregistration(
    state: BeaconState, pubkey: XMSSPubkey
) -> StoredPreregistration | None:
    """
    Return the active preregistration of ``pubkey``, if any.
    """
    index = get_stored_preregistration_index(state, pubkey)
    if index is None:
        return None
    preregistration = state.validator_preregistrations[index]
    if not is_active_preregistration(state, preregistration):
        return None
    return preregistration
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
        # Use an empty signature field as a placeholder
        # and GENESIS_SLOT to distinguish from a pending deposit request
        state.pending_deposits.append(
            PendingDeposit(
                # [Modified in PQ]
                pubkey=Bytes48(XMSS_DEPOSIT_PREFIX + validator.pubkey),
                withdrawal_credentials=validator.withdrawal_credentials,
                amount=excess_balance,
                # [Modified in PQ]
                signature=Bytes96(),
                slot=GENESIS_SLOT,
            )
        )
```

#### New `remove_stored_preregistration`

*Note*: Removal preserves the order of the remaining records, which the state
root commits to.

```python
def remove_stored_preregistration(state: BeaconState, pubkey: XMSSPubkey) -> None:
    """
    Remove the stored preregistration of ``pubkey``.
    """
    state.validator_preregistrations = ValidatorPreregistrations(
        data=[
            preregistration
            for preregistration in state.validator_preregistrations
            if preregistration.pubkey != pubkey
        ]
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
    # [New in EIP8205]
    process_preregistration_expiry(state)
```

#### New `process_preregistration_expiry`

*Note*: The sweep is garbage collection only. Bindings are enforced through
`is_active_preregistration`, so the timing of the sweep has no effect on whether
a binding is enforced or a request is admitted.

```python
def process_preregistration_expiry(state: BeaconState) -> None:
    state.validator_preregistrations = ValidatorPreregistrations(
        data=[
            preregistration
            for preregistration in state.validator_preregistrations
            if is_active_preregistration(state, preregistration)
        ]
    )
```

#### Modified `apply_pending_deposit`

*Note*: Deposits carry no signature, so a deposit for a new validator is not
verified. The validator of a legacy deposit is exited at once without consuming
exit churn, since it was never active, and becomes withdrawable after
`MIN_VALIDATOR_WITHDRAWABILITY_DELAY` epochs, as after any exit.

```python
def apply_pending_deposit(state: BeaconState, deposit: PendingDeposit) -> None:
    """
    Applies ``deposit`` to the ``state``.
    """
    # [Modified in PQ]
    pubkey = compute_deposit_pubkey(deposit.pubkey)
    validator_pubkeys = [validator.pubkey for validator in state.validators]
    if pubkey not in validator_pubkeys:
        # [New in PQ]
        index = get_index_for_new_validator(state)
        add_validator_to_registry(
            state,
            pubkey,
            # [New in PQ]
            compute_deposit_vrf_root(deposit),
            deposit.withdrawal_credentials,
            deposit.amount,
        )
        # [New in PQ]
        if is_legacy_pubkey(deposit.pubkey):
            epoch = get_current_epoch(state)
            validator = state.validators[index]
            validator.exit_epoch = epoch
            validator.withdrawable_epoch = epoch + MIN_VALIDATOR_WITHDRAWABILITY_DELAY
    else:
        validator_index = ValidatorIndex(validator_pubkeys.index(pubkey))
        increase_balance(state, validator_index, deposit.amount)
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
        # [Modified in PQ]
        pubkey = compute_deposit_pubkey(deposit.pubkey)
        validator_pubkeys = [validator.pubkey for validator in state.validators]
        if pubkey in validator_pubkeys:
            validator = state.validators[ValidatorIndex(validator_pubkeys.index(pubkey))]
            is_validator_exited = validator.exit_epoch < FAR_FUTURE_EPOCH
            is_validator_withdrawn = validator.withdrawable_epoch < next_epoch

        # [Modified in PQ]
        if is_validator_withdrawn or is_legacy_pubkey(deposit.pubkey):
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

*Note*: The reveal is the proposer's VRF proof for the slot. The proposer
committed to its leaves when it registered its VRF root, so it cannot grind the
reveal and can only withhold its block, as with BLS.

```python
def process_randao(state: BeaconState, body: BeaconBlockBody) -> None:
    epoch = get_current_epoch(state)
    # [Modified in PQ]
    # Verify RANDAO reveal
    assert is_valid_vrf_proof(
        state,
        get_beacon_proposer_index(state),
        state.slot,
        body.randao_reveal,
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
        (CONSOLIDATION_REQUEST_TYPE, execution_requests.consolidations),
        (BUILDER_DEPOSIT_REQUEST_TYPE, execution_requests.builder_deposits),
        (BUILDER_EXIT_REQUEST_TYPE, execution_requests.builder_exits),
        # [Modified in PQ]
        # Removed `VALIDATOR_PQ_REGISTRATION_REQUEST_TYPE`
        # [Modified in PQ]
        # Removed `BUILDER_PQ_REGISTRATION_REQUEST_TYPE`
        # [New in EIP8205]
        (PREREGISTRATION_REQUEST_TYPE, execution_requests.preregistrations),
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
    assert stark.VerifyAggregates(statements, body.proof)
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
            payment.weight += state.validators[index].effective_balance

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

##### Deposit requests

###### Modified `process_deposit_request`

```python
def process_deposit_request(state: BeaconState, deposit_request: DepositRequest) -> None:
    # [New in EIP8205]
    pubkey = compute_deposit_pubkey(deposit_request.pubkey)
    preregistration = get_active_preregistration(state, pubkey)
    if preregistration is not None:
        if deposit_request.withdrawal_credentials != preregistration.withdrawal_credentials:
            return
        if Root(deposit_request.signature[:32]) != preregistration.vrf_root:
            return
        remove_stored_preregistration(state, pubkey)

    state.pending_deposits.append(
        PendingDeposit(
            pubkey=deposit_request.pubkey,
            withdrawal_credentials=deposit_request.withdrawal_credentials,
            amount=deposit_request.amount,
            signature=deposit_request.signature,
            slot=state.slot,
        )
    )
```

###### Modified `get_validator_from_deposit`

```python
def get_validator_from_deposit(
    # [Modified in PQ]
    pubkey: XMSSPubkey,
    # [New in PQ]
    vrf_root: Root,
    withdrawal_credentials: Bytes32,
    amount: Gwei,
) -> Validator:
    validator = Validator(
        pubkey=pubkey,
        # [New in PQ]
        vrf_root=vrf_root,
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

###### Modified `add_validator_to_registry`

```python
def add_validator_to_registry(
    state: BeaconState,
    # [Modified in PQ]
    pubkey: XMSSPubkey,
    # [New in PQ]
    vrf_root: Root,
    withdrawal_credentials: Bytes32,
    amount: Gwei,
) -> None:
    index = get_index_for_new_validator(state)
    # [Modified in PQ]
    validator = get_validator_from_deposit(pubkey, vrf_root, withdrawal_credentials, amount)
    set_or_append_list(state.validators, index, validator)
    set_or_append_list(state.balances, index, amount)
    set_or_append_list(state.previous_epoch_participation, index, ParticipationFlags(0b0000_0000))
    set_or_append_list(state.current_epoch_participation, index, ParticipationFlags(0b0000_0000))
    set_or_append_list(state.inactivity_scores, index, Uint64(0))
```

##### Builder deposit requests

###### Modified `add_builder_to_registry`

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

###### Modified `process_builder_deposit_request`

*Note*: Builder deposits carry no signature, so a deposit for a new builder is
not verified. A builder has no VRF root, so `request.signature` is ignored. The
builder of a legacy deposit initiates its exit at once, so the builder sweep
refunds its balance.

```python
def process_builder_deposit_request(state: BeaconState, request: BuilderDepositRequest) -> None:
    # Ignore deposits with unexpected withdrawal credential prefixes
    if not is_builder_withdrawal_credential(request.withdrawal_credentials):
        return

    # [Modified in PQ]
    pubkey = compute_deposit_pubkey(request.pubkey)
    builder_pubkeys = [builder.pubkey for builder in state.builders]
    if pubkey not in builder_pubkeys:
        # [New in PQ]
        builder_index = get_index_for_new_builder(state)
        add_builder_to_registry(
            state,
            pubkey,
            PAYLOAD_BUILDER_VERSION,
            ExecutionAddress(request.withdrawal_credentials[12:]),
            request.amount,
            state.slot,
        )
        # [New in PQ]
        if is_legacy_pubkey(request.pubkey):
            initiate_builder_exit(state, builder_index)
    else:
        builder_index = BuilderIndex(builder_pubkeys.index(pubkey))
        builder = state.builders[builder_index]

        # If exited and swept, reset the withdrawable epoch
        if builder.withdrawable_epoch != FAR_FUTURE_EPOCH and builder.balance == 0:
            epoch = get_current_epoch(state)
            builder.withdrawable_epoch = epoch + MIN_BUILDER_WITHDRAWABILITY_DELAY

        # Increase balance by deposit amount
        builder.balance += request.amount
```

##### Builder exit requests

###### Modified `process_builder_exit_request`

```python
def process_builder_exit_request(state: BeaconState, request: BuilderExitRequest) -> None:
    # [Modified in PQ]
    pubkey = XMSSPubkey(request.pubkey[16:])
    builder_pubkeys = [builder.pubkey for builder in state.builders]
    if pubkey not in builder_pubkeys:
        return

    builder_index = BuilderIndex(builder_pubkeys.index(pubkey))
    builder = state.builders[builder_index]

    if not is_active_builder(state, builder_index):
        return
    if builder.execution_address != request.source_address:
        return
    if get_pending_balance_to_withdraw_for_builder(state, builder_index) != 0:
        return

    initiate_builder_exit(state, builder_index)
```

##### Execution-layer withdrawal requests

###### Modified `process_withdrawal_request`

```python
def process_withdrawal_request(state: BeaconState, withdrawal_request: WithdrawalRequest) -> None:
    # [New in PQ]
    # Ignore requests that name a BLS public key
    if is_legacy_pubkey(withdrawal_request.validator_pubkey):
        return

    amount = withdrawal_request.amount
    is_full_exit_request = amount == FULL_EXIT_REQUEST_AMOUNT

    # If partial withdrawal queue is full, only full exits are processed
    if (
        len(state.pending_partial_withdrawals) == PENDING_PARTIAL_WITHDRAWALS_LIMIT
        and not is_full_exit_request
    ):
        return

    validator_pubkeys = [validator.pubkey for validator in state.validators]
    # [Modified in PQ]
    # Verify pubkey exists
    request_pubkey = XMSSPubkey(withdrawal_request.validator_pubkey[16:])
    if request_pubkey not in validator_pubkeys:
        return
    index = ValidatorIndex(validator_pubkeys.index(request_pubkey))
    validator = state.validators[index]

    # Verify withdrawal credentials
    has_correct_credential = has_execution_withdrawal_credential(validator)
    is_correct_source_address = (
        validator.withdrawal_credentials[12:] == withdrawal_request.source_address
    )
    if not (has_correct_credential and is_correct_source_address):
        return
    # Verify the validator is active
    if not is_active_validator(validator, get_current_epoch(state)):
        return
    # Verify exit has not been initiated
    if validator.exit_epoch != FAR_FUTURE_EPOCH:
        return
    # Verify the validator has been active long enough
    if get_current_epoch(state) < validator.activation_epoch + SHARD_COMMITTEE_PERIOD:
        return

    pending_balance_to_withdraw = get_pending_balance_to_withdraw(state, index)

    if is_full_exit_request:
        # Only exit validator if it has no pending withdrawals in the queue
        if pending_balance_to_withdraw == 0:
            initiate_validator_exit(state, index)
        return

    has_sufficient_effective_balance = validator.effective_balance >= MIN_ACTIVATION_BALANCE
    has_excess_balance = (
        state.balances[index] > MIN_ACTIVATION_BALANCE + pending_balance_to_withdraw
    )

    # Only allow partial withdrawals with compounding withdrawal credentials
    if (
        has_compounding_withdrawal_credential(validator)
        and has_sufficient_effective_balance
        and has_excess_balance
    ):
        to_withdraw = min(
            state.balances[index] - MIN_ACTIVATION_BALANCE - pending_balance_to_withdraw, amount
        )
        exit_queue_epoch = compute_exit_epoch_and_update_churn(state, to_withdraw)
        withdrawable_epoch = exit_queue_epoch + MIN_VALIDATOR_WITHDRAWABILITY_DELAY
        state.pending_partial_withdrawals.append(
            PendingPartialWithdrawal(
                validator_index=index,
                amount=to_withdraw,
                withdrawable_epoch=withdrawable_epoch,
            )
        )
```

##### Execution-layer consolidation requests

###### Modified `is_valid_switch_to_compounding_request`

```python
def is_valid_switch_to_compounding_request(
    state: BeaconState, consolidation_request: ConsolidationRequest
) -> bool:
    # Switch to compounding requires source and target be equal
    if consolidation_request.source_pubkey != consolidation_request.target_pubkey:
        return False

    # [Modified in PQ]
    # Verify pubkey exists
    source_pubkey = XMSSPubkey(consolidation_request.source_pubkey[16:])
    validator_pubkeys = [validator.pubkey for validator in state.validators]
    if source_pubkey not in validator_pubkeys:
        return False

    source_validator = state.validators[ValidatorIndex(validator_pubkeys.index(source_pubkey))]

    # Verify request has been authorized
    if source_validator.withdrawal_credentials[12:] != consolidation_request.source_address:
        return False

    # Verify source withdrawal credentials
    if not has_eth1_withdrawal_credential(source_validator):
        return False

    # Verify the source is active
    current_epoch = get_current_epoch(state)
    if not is_active_validator(source_validator, current_epoch):
        return False

    # Verify exit for source has not been initiated
    if source_validator.exit_epoch != FAR_FUTURE_EPOCH:
        return False

    return True
```

###### Modified `process_consolidation_request`

```python
def process_consolidation_request(
    state: BeaconState, consolidation_request: ConsolidationRequest
) -> None:
    # [New in PQ]
    # Ignore requests that name a BLS public key
    if is_legacy_pubkey(consolidation_request.source_pubkey):
        return
    if is_legacy_pubkey(consolidation_request.target_pubkey):
        return

    if is_valid_switch_to_compounding_request(state, consolidation_request):
        validator_pubkeys = [validator.pubkey for validator in state.validators]
        # [Modified in PQ]
        request_source_pubkey = XMSSPubkey(consolidation_request.source_pubkey[16:])
        source_index = ValidatorIndex(validator_pubkeys.index(request_source_pubkey))
        switch_to_compounding_validator(state, source_index)
        return

    # Verify that source != target, so a consolidation cannot be used as an exit
    if consolidation_request.source_pubkey == consolidation_request.target_pubkey:
        return
    # If the pending consolidations queue is full, consolidation requests are ignored
    if len(state.pending_consolidations) == PENDING_CONSOLIDATIONS_LIMIT:
        return
    # If there is too little available consolidation churn limit, consolidation requests are ignored
    if get_consolidation_churn_limit(state) <= MIN_ACTIVATION_BALANCE:
        return

    validator_pubkeys = [validator.pubkey for validator in state.validators]
    # [Modified in PQ]
    # Verify pubkeys exists
    request_source_pubkey = XMSSPubkey(consolidation_request.source_pubkey[16:])
    request_target_pubkey = XMSSPubkey(consolidation_request.target_pubkey[16:])
    if request_source_pubkey not in validator_pubkeys:
        return
    if request_target_pubkey not in validator_pubkeys:
        return
    source_index = ValidatorIndex(validator_pubkeys.index(request_source_pubkey))
    target_index = ValidatorIndex(validator_pubkeys.index(request_target_pubkey))
    source_validator = state.validators[source_index]
    target_validator = state.validators[target_index]

    # Verify source withdrawal credentials
    has_correct_credential = has_execution_withdrawal_credential(source_validator)
    is_correct_source_address = (
        source_validator.withdrawal_credentials[12:] == consolidation_request.source_address
    )
    if not (has_correct_credential and is_correct_source_address):
        return

    # Verify that target has compounding withdrawal credentials
    if not has_compounding_withdrawal_credential(target_validator):
        return

    # Verify the source and the target are active
    current_epoch = get_current_epoch(state)
    if not is_active_validator(source_validator, current_epoch):
        return
    if not is_active_validator(target_validator, current_epoch):
        return
    # Verify exits for source and target have not been initiated
    if source_validator.exit_epoch != FAR_FUTURE_EPOCH:
        return
    if target_validator.exit_epoch != FAR_FUTURE_EPOCH:
        return
    # Verify the source has been active long enough
    if current_epoch < source_validator.activation_epoch + SHARD_COMMITTEE_PERIOD:
        return
    # Verify the source has no pending withdrawals in the queue
    if get_pending_balance_to_withdraw(state, source_index) > 0:
        return

    # Initiate source validator exit and append pending consolidation
    source_validator.exit_epoch = compute_consolidation_epoch_and_update_churn(
        state, source_validator.effective_balance
    )
    source_validator.withdrawable_epoch = (
        source_validator.exit_epoch + MIN_VALIDATOR_WITHDRAWABILITY_DELAY
    )
    state.pending_consolidations.append(
        PendingConsolidation(source_index=source_index, target_index=target_index)
    )
```

##### Preregistration requests

###### New `process_preregistration_request`

```python
def process_preregistration_request(state: BeaconState, request: PreregistrationRequest) -> None:
    pubkey = request.pubkey

    # An active binding for this pubkey makes the new request a no-op
    if get_active_preregistration(state, pubkey) is not None:
        return

    # A pubkey with an existing validator cannot be preregistered
    if pubkey in [validator.pubkey for validator in state.validators]:
        return

    # A pubkey with a pending deposit cannot be preregistered
    if is_pending_validator(state.pending_deposits, pubkey):
        return

    # The capacity check counts only active records, so the timing of the
    # garbage-collection sweep does not affect admission
    active_preregistrations = [
        preregistration
        for preregistration in state.validator_preregistrations
        if is_active_preregistration(state, preregistration)
    ]
    if len(active_preregistrations) >= PREREGISTRATIONS_LIMIT:
        return

    if not is_valid_preregistration_signature(state, request):
        return

    preregistration = StoredPreregistration(
        pubkey=pubkey,
        withdrawal_credentials=request.withdrawal_credentials,
        vrf_root=request.vrf_root,
        expiry_slot=state.slot + PREREGISTRATION_EXPIRY_SLOTS,
    )
    index = get_stored_preregistration_index(state, pubkey)
    if index is not None:
        # Replace the expired record in place
        state.validator_preregistrations[index] = preregistration
    else:
        state.validator_preregistrations.append(preregistration)
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
    # Removed the validator and builder PQ registration request limits
    # [New in EIP8205]
    assert len(requests.preregistrations) <= MAX_PREREGISTRATION_REQUESTS_PER_PAYLOAD

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
    # Removed `process_validator_pq_registration_request`
    # [Modified in PQ]
    # Removed `process_builder_pq_registration_request`
    # [New in EIP8205]
    for_ops(requests.preregistrations, process_preregistration_request)

    # Update parent payload availability and latest block hash
    state.execution_payload_availability[parent_slot % SLOTS_PER_HISTORICAL_ROOT] = Boolean(True)
    state.latest_block_hash = parent_bid.block_hash
```
