# EIP-8450 -- The Beacon Chain

*Note*: This document is a work-in-progress for researchers and implementers.

<!-- mdformat-toc start --slug=github --no-anchors --maxlevel=6 --minlevel=2 -->

- [Introduction](#introduction)
- [Types](#types)
  - [New `XMSSPublicKey`](#new-xmsspublickey)
  - [New `XMSSSignature`](#new-xmsssignature)
  - [New `VRFRoot`](#new-vrfroot)
  - [New `ValidatorPQPublicKeys`](#new-validatorpqpublickeys)
  - [New `ValidatorPQKeyChangeEpochs`](#new-validatorpqkeychangeepochs)
  - [New `BuilderPQPublicKeys`](#new-builderpqpublickeys)
  - [New `BuilderPQKeyChangeEpochs`](#new-builderpqkeychangeepochs)
  - [New `PQKeyRegistrations`](#new-pqkeyregistrations)
- [Constants](#constants)
  - [Domains](#domains)
  - [Registry](#registry)
- [Presets](#presets)
  - [Post-quantum key registry](#post-quantum-key-registry)
- [Containers](#containers)
  - [New containers](#new-containers)
    - [`PQPublicKeys`](#pqpublickeys)
    - [`PQKeyRegistration`](#pqkeyregistration)
    - [`PQKeyPossession`](#pqkeypossession)
    - [`SignedPQKeyRegistration`](#signedpqkeyregistration)
  - [Modified containers](#modified-containers)
    - [`BeaconBlockBody`](#beaconblockbody)
    - [`BeaconState`](#beaconstate)
- [Helpers](#helpers)
  - [Crypto](#crypto)
    - [Hash-based primitives](#hash-based-primitives)
    - [New `xmss_signature_index`](#new-xmss_signature_index)
  - [Predicates](#predicates)
    - [New `is_pq_public_key_in_use`](#new-is_pq_public_key_in_use)
    - [New `is_valid_pq_possession_proof`](#new-is_valid_pq_possession_proof)
  - [Validator registry](#validator-registry)
    - [Modified `add_validator_to_registry`](#modified-add_validator_to_registry)
  - [Builder registry](#builder-registry)
    - [Modified `add_builder_to_registry`](#modified-add_builder_to_registry)
- [Beacon chain state transition function](#beacon-chain-state-transition-function)
  - [Block processing](#block-processing)
    - [Operations](#operations)
      - [Modified `process_operations`](#modified-process_operations)
      - [Post-quantum key registrations](#post-quantum-key-registrations)
        - [New `process_pq_key_registration`](#new-process_pq_key_registration)

<!-- mdformat-toc end -->

## Introduction

This upgrade adds a post-quantum public key registry to the beacon state, as
part of the EIP-8450 upgrade.

Each validator registers two hash-based commitments, bound to its existing
validator index: a leanXMSS public key, used for every message the validator
signs once duties switch to it, and the root of a VRF tree, which fixes one
verifiable random output per index. Each builder registers a leanXMSS public key
for its existing builder index through the same operation.

Registration is a new beacon block operation carrying the keys and a proof of
possession that binds the leanXMSS key to the BLS public key of the validator or
builder. It is authorized by that BLS signing key, which can also replace
registered keys, at most once every `MIN_PQ_KEY_CHANGE_DELAY` epochs. The
registered keys are dormant: no duty is authenticated with them in this upgrade.

*Note*: This specification is built upon [Heze](../../heze/beacon-chain.md).

## Types

### New `XMSSPublicKey`

```python
class XMSSPublicKey(ByteVector):
    """
    A leanXMSS public key.
    """

    LENGTH = 32
```

### New `XMSSSignature`

```python
class XMSSSignature(ByteVector):
    """
    A leanXMSS signature.
    """

    LENGTH = 2404
```

### New `VRFRoot`

```python
class VRFRoot(Bytes32):
    """
    The root of a VRF tree.
    """
```

### New `ValidatorPQPublicKeys`

```python
class ValidatorPQPublicKeys(ProgressiveList[PQPublicKeys]):
    """
    The registered post-quantum keys of every validator, by validator index. A
    validator without keys holds the all-zero entry.
    """
```

### New `ValidatorPQKeyChangeEpochs`

```python
class ValidatorPQKeyChangeEpochs(ProgressiveList[Epoch]):
    """
    The epoch of the last registration or change of every validator's keys, by
    validator index. ``FAR_FUTURE_EPOCH`` marks a validator that has never
    registered keys.
    """
```

### New `BuilderPQPublicKeys`

```python
class BuilderPQPublicKeys(ProgressiveList[PQPublicKeys]):
    """
    The registered post-quantum keys of every builder, by builder index. A
    builder without keys holds the all-zero entry.
    """
```

### New `BuilderPQKeyChangeEpochs`

```python
class BuilderPQKeyChangeEpochs(ProgressiveList[Epoch]):
    """
    The epoch of the last registration or change of every builder's keys, by
    builder index. The builder's deposit epoch marks a builder that has never
    registered keys.
    """
```

### New `PQKeyRegistrations`

```python
class PQKeyRegistrations(ProgressiveList[SignedPQKeyRegistration]):
    """
    The post-quantum key registrations included in a beacon block.
    """
```

## Constants

### Domains

| Name                         | Value                      |
| ---------------------------- | -------------------------- |
| `DOMAIN_PQ_KEY_REGISTRATION` | `DomainType("0x12000000")` |
| `DOMAIN_PQ_KEY_POSSESSION`   | `DomainType("0x13000000")` |

### Registry

| Name                       | Value       |
| -------------------------- | ----------- |
| `PQ_POSSESSION_XMSS_INDEX` | `Uint32(0)` |

## Presets

### Post-quantum key registry

| Name                       | Value                 |
| -------------------------- | --------------------- |
| `MAX_PQ_KEY_REGISTRATIONS` | `Uint64(2**3)` (= 8)  |
| `MIN_PQ_KEY_CHANGE_DELAY`  | `Epoch(2**8)` (= 256) |

*Note*: In every preset, `MIN_PQ_KEY_CHANGE_DELAY` must be at least `1`, since
replay protection relies on a change being applied in a later epoch than the
change it names.

## Containers

### New containers

#### `PQPublicKeys`

*Note*: A builder registers a zero `vrf_root`, since builders make no selection
proofs.

```python
class PQPublicKeys(Container):
    xmss_public_key: XMSSPublicKey
    vrf_root: VRFRoot
```

#### `PQKeyRegistration`

*Note*: An `index` with `BUILDER_INDEX_FLAG` set names a builder, as for builder
withdrawals.

```python
class PQKeyRegistration(Container):
    # Validator index, or builder index with ``BUILDER_INDEX_FLAG`` set
    index: ValidatorIndex
    public_keys: PQPublicKeys
    # Epoch of the last change, or the never-registered marker of the index:
    # ``FAR_FUTURE_EPOCH`` for a validator, the deposit epoch for a builder
    previous_change_epoch: Epoch
```

#### `PQKeyPossession`

*Note*: The validator or builder is named by its BLS public key, which never
changes and is known before it has an index. The message does not depend on the
rest of the registration, so a key signs it only once.

```python
class PQKeyPossession(Container):
    pubkey: BLSPubkey
    xmss_public_key: XMSSPublicKey
```

#### `SignedPQKeyRegistration`

```python
class SignedPQKeyRegistration(Container):
    message: PQKeyRegistration
    # Signature of the ``PQKeyPossession`` by the registered leanXMSS key
    possession: XMSSSignature
    # Signature of ``message`` by the BLS signing key of the validator or builder
    signature: BLSSignature
```

### Modified containers

#### `BeaconBlockBody`

```python
class BeaconBlockBody(ProgressiveContainer):
    ACTIVE_FIELDS = active_fields(width=14, gaps=(1, 6))

    randao_reveal: BLSSignature
    graffiti: Bytes32
    proposer_slashings: ProposerSlashings
    attester_slashings: AttesterSlashings
    attestations: Attestations
    voluntary_exits: VoluntaryExits
    sync_aggregate: SyncAggregate
    bls_to_execution_changes: BLSToExecutionChanges
    signed_execution_payload_bid: SignedExecutionPayloadBid
    payload_attestations: PayloadAttestations
    parent_execution_requests: ExecutionRequests
    # [New in EIP8450]
    pq_key_registrations: PQKeyRegistrations
```

#### `BeaconState`

*Note*: The keys are stored in lists parallel to `validators` and `builders`, so
the `Validator` and `Builder` containers and their generalized indices are
unchanged.

```python
class BeaconState(ProgressiveContainer):
    ACTIVE_FIELDS = active_fields(width=50, gaps=(8, 9, 10, 28))

    genesis_time: Uint64
    genesis_validators_root: Root
    slot: Slot
    fork: Fork
    latest_block_header: BeaconBlockHeader
    block_roots: BlockRoots
    state_roots: StateRoots
    historical_roots: HistoricalRoots
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
    # [New in EIP8450]
    pq_public_keys: ValidatorPQPublicKeys
    # [New in EIP8450]
    pq_key_change_epochs: ValidatorPQKeyChangeEpochs
    # [New in EIP8450]
    builder_pq_public_keys: BuilderPQPublicKeys
    # [New in EIP8450]
    builder_pq_key_change_epochs: BuilderPQKeyChangeEpochs
```

## Helpers

### Crypto

#### Hash-based primitives

This upgrade uses two hash-based primitives through the interface below: a
stateful signature scheme, leanXMSS, and a verifiable random function, a VRF
tree. Their constructions are specified outside this upgrade. Key generation,
signing, and opening are not consensus-critical.

- `def xmss.Verify(public_key: XMSSPublicKey, message: Bytes32, signature: XMSSSignature) -> bool`:
  return whether `signature` is a valid signature of `message` under
  `public_key`, at the leaf index it carries. Return `False`, without raising,
  for a key or signature that does not decode.
- `def vrf.Verify(root: VRFRoot, index: Uint32, opening: bytes) -> Optional[Bytes32]`:
  return the output of the VRF tree with root `root` at `index` if `opening` is
  a valid opening of it, and `None` otherwise. This upgrade does not call it.

Signatures are unforgeable as long as each leaf index of a key signs at most
once. Signing is not assumed to be deterministic, so signing the same message
twice at one leaf index is also a reuse. For a given root and index, at most one
VRF output verifies, unless a hash collision is known.

#### New `xmss_signature_index`

```python
def xmss_signature_index(signature: XMSSSignature) -> Uint32:
    """
    Return the leaf index that ``signature`` carries, in its first four bytes.
    """
    return Uint32(int.from_bytes(signature[0:4], "little"))
```

### Predicates

#### New `is_pq_public_key_in_use`

*Note*: An entry without keys holds the all-zero key, which a registration never
carries, so it never matches. Consensus rejects a leanXMSS key that a validator
or builder currently holds, including the one registering, so a change never
keeps the current key, and changing only the VRF root requires a new leanXMSS
key. Earlier keys are not recorded, so a key that its holder has released can be
registered again, by a validator and a builder that share a BLS public key even
with the same proof bytes. The signer rules in the
[validator guide](./validator.md#leaf-index-rules) forbid that. Clients are
expected to maintain a map from registered keys to indices, as they do for BLS
public keys.

```python
def is_pq_public_key_in_use(state: BeaconState, xmss_public_key: XMSSPublicKey) -> bool:
    """
    Check if any validator or builder holds ``xmss_public_key``.
    """
    entries = list(state.pq_public_keys) + list(state.builder_pq_public_keys)
    return any(entry.xmss_public_key == xmss_public_key for entry in entries)
```

#### New `is_valid_pq_possession_proof`

*Note*: Leaf index `PQ_POSSESSION_XMSS_INDEX` is reserved for the proof of
possession. The domain uses the genesis fork version, so a proof stays valid
across forks.

```python
def is_valid_pq_possession_proof(
    state: BeaconState,
    pubkey: BLSPubkey,
    xmss_public_key: XMSSPublicKey,
    proof: XMSSSignature,
) -> bool:
    """
    Check if ``proof`` is a signature, by ``xmss_public_key``, of the key itself
    for the validator or builder holding ``pubkey``.
    """
    if xmss_signature_index(proof) != PQ_POSSESSION_XMSS_INDEX:
        return False

    possession = PQKeyPossession(
        pubkey=pubkey,
        xmss_public_key=xmss_public_key,
    )
    domain = compute_domain(
        DOMAIN_PQ_KEY_POSSESSION,
        genesis_validators_root=state.genesis_validators_root,
    )
    signing_root = compute_signing_root(possession, domain)
    return xmss.Verify(xmss_public_key, signing_root, proof)
```

### Validator registry

#### Modified `add_validator_to_registry`

*Note*: The function `add_validator_to_registry` is modified to initialize the
items in the `pq_public_keys` and `pq_key_change_epochs` lists, preserving the
invariant that they have one entry per validator.

```python
def add_validator_to_registry(
    state: BeaconState, pubkey: BLSPubkey, withdrawal_credentials: Bytes32, amount: Gwei
) -> None:
    index = get_index_for_new_validator(state)
    validator = get_validator_from_deposit(pubkey, withdrawal_credentials, amount)
    set_or_append_list(state.validators, index, validator)
    set_or_append_list(state.balances, index, amount)
    set_or_append_list(state.previous_epoch_participation, index, ParticipationFlags(0b0000_0000))
    set_or_append_list(state.current_epoch_participation, index, ParticipationFlags(0b0000_0000))
    set_or_append_list(state.inactivity_scores, index, Uint64(0))
    # [New in EIP8450]
    set_or_append_list(state.pq_public_keys, index, PQPublicKeys.empty())
    # [New in EIP8450]
    set_or_append_list(state.pq_key_change_epochs, index, FAR_FUTURE_EPOCH)
```

### Builder registry

#### Modified `add_builder_to_registry`

*Note*: The function `add_builder_to_registry` is modified to write a fresh item
in the `builder_pq_public_keys` and `builder_pq_key_change_epochs` lists at the
builder's index, preserving the invariant that they have one entry per builder.
A reused builder index gets a fresh entry, whose change epoch is the new
builder's deposit epoch.

```python
def add_builder_to_registry(
    state: BeaconState,
    pubkey: BLSPubkey,
    version: Uint8,
    execution_address: ExecutionAddress,
    amount: Gwei,
    slot: Slot,
) -> None:
    index = get_index_for_new_builder(state)
    builder = Builder(
        pubkey=pubkey,
        version=version,
        execution_address=execution_address,
        balance=amount,
        deposit_epoch=compute_epoch_at_slot(slot),
        withdrawable_epoch=FAR_FUTURE_EPOCH,
    )
    set_or_append_list(state.builders, index, builder)
    # [New in EIP8450]
    set_or_append_list(state.builder_pq_public_keys, index, PQPublicKeys.empty())
    # [New in EIP8450]
    set_or_append_list(state.builder_pq_key_change_epochs, index, builder.deposit_epoch)
```

## Beacon chain state transition function

### Block processing

#### Operations

##### Modified `process_operations`

*Note*: Registrations are processed after every other operation of the block,
and after the parent's execution requests, so a registration for a validator or
builder whose exit is initiated earlier in the same block is invalid.

```python
def process_operations(state: BeaconState, body: BeaconBlockBody, parent_slot: Slot) -> None:
    def for_ops(operations: Sequence[Any], fn: Callable[..., None], *args: Any) -> None:
        for operation in operations:
            fn(state, operation, *args)

    assert len(body.proposer_slashings) <= MAX_PROPOSER_SLASHINGS
    assert len(body.attester_slashings) <= MAX_ATTESTER_SLASHINGS_ELECTRA
    assert len(body.attestations) <= MAX_ATTESTATIONS_ELECTRA
    assert len(body.voluntary_exits) <= MAX_VOLUNTARY_EXITS
    assert len(body.bls_to_execution_changes) <= MAX_BLS_TO_EXECUTION_CHANGES
    assert len(body.payload_attestations) <= MAX_PAYLOAD_ATTESTATIONS
    # [New in EIP8450]
    assert len(body.pq_key_registrations) <= MAX_PQ_KEY_REGISTRATIONS

    for_ops(body.proposer_slashings, process_proposer_slashing)
    for_ops(body.attester_slashings, process_attester_slashing)
    for_ops(body.attestations, process_attestation, parent_slot)
    for_ops(body.voluntary_exits, process_voluntary_exit)
    for_ops(body.bls_to_execution_changes, process_bls_to_execution_change)
    for_ops(body.payload_attestations, process_payload_attestation)
    # [New in EIP8450]
    for_ops(body.pq_key_registrations, process_pq_key_registration)
```

##### Post-quantum key registrations

###### New `process_pq_key_registration`

*Note*: The same operation registers keys for a validator or builder that has
none and replaces the keys of a registered one. An entry holds keys exactly when
its leanXMSS key is not all-zero, since a registration writes a nonzero key and
the current epoch together, and onboarding writes the all-zero key and the
never-registered marker together. Each registration names the epoch of the last
change. A first registration stores the current epoch, which is never the
marker: `FAR_FUTURE_EPOCH` for a validator, and for a builder its deposit epoch,
which is before the finalized epoch of an active builder. With a delay of at
least one epoch, a later change is applied in an epoch after the change it
names. Every applied registration therefore moves the stored epoch forward, and
none can be included twice. Builder indices are reused once a builder has
withdrawn, so a builder's marker is its deposit epoch rather than
`FAR_FUTURE_EPOCH`, and a registration signed for an earlier builder at the same
index names an earlier epoch.

```python
def process_pq_key_registration(
    state: BeaconState, signed_registration: SignedPQKeyRegistration
) -> None:
    registration = signed_registration.message
    public_keys = registration.public_keys

    if is_builder_index(registration.index):
        index = convert_validator_index_to_builder_index(registration.index)
        assert index < len(state.builders)
        # Verify the builder is active, so its deposit epoch is finalized
        assert is_active_builder(state, index)
        # Builders make no selection proofs, so they register no VRF root
        assert public_keys.vrf_root == VRFRoot()
        pubkey = state.builders[index].pubkey
        keys = state.builder_pq_public_keys
        change_epochs = state.builder_pq_key_change_epochs
    else:
        index = registration.index
        assert index < len(state.validators)
        # Verify the validator has not initiated an exit
        assert state.validators[index].exit_epoch == FAR_FUTURE_EPOCH
        pubkey = state.validators[index].pubkey
        keys = state.pq_public_keys
        change_epochs = state.pq_key_change_epochs

    # Verify the registration applies to the current entry
    assert registration.previous_change_epoch == change_epochs[index]

    # Changes of registered keys are rate-limited
    if keys[index].xmss_public_key != XMSSPublicKey():
        assert get_current_epoch(state) >= change_epochs[index] + MIN_PQ_KEY_CHANGE_DELAY

    # Fork-agnostic domain since registrations are valid across forks
    domain = compute_domain(
        DOMAIN_PQ_KEY_REGISTRATION,
        genesis_validators_root=state.genesis_validators_root,
    )
    signing_root = compute_signing_root(registration, domain)
    assert bls.Verify(pubkey, signing_root, signed_registration.signature)

    # Verify the leanXMSS key is new, and that its possession is proven
    assert public_keys.xmss_public_key != XMSSPublicKey()
    assert not is_pq_public_key_in_use(state, public_keys.xmss_public_key)
    assert is_valid_pq_possession_proof(
        state, pubkey, public_keys.xmss_public_key, signed_registration.possession
    )

    keys[index] = public_keys
    change_epochs[index] = get_current_epoch(state)
```
