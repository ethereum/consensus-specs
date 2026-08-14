# EIP-8321 -- The Beacon Chain

*Note*: This document is a work-in-progress for researchers and implementers.

<!-- mdformat-toc start --slug=github --no-anchors --maxlevel=6 --minlevel=2 -->

- [Introduction](#introduction)
- [Types](#types)
  - [New `PendingRandaoCommitments`](#new-pendingrandaocommitments)
  - [New `RandaoCommitmentRegistrations`](#new-randaocommitmentregistrations)
  - [New `RandaoCommitments`](#new-randaocommitments)
- [Constants](#constants)
  - [Domains](#domains)
  - [Hash chain](#hash-chain)
- [Preset](#preset)
  - [Hash-chain RANDAO](#hash-chain-randao)
- [Containers](#containers)
  - [New containers](#new-containers)
    - [`PendingRandaoCommitment`](#pendingrandaocommitment)
    - [`RandaoCommitmentRegistration`](#randaocommitmentregistration)
    - [`SignedRandaoCommitmentRegistration`](#signedrandaocommitmentregistration)
  - [Modified containers](#modified-containers)
    - [`BeaconBlockBody`](#beaconblockbody)
    - [`BeaconState`](#beaconstate)
- [Helpers](#helpers)
  - [Crypto](#crypto)
    - [New `blake3`](#new-blake3)
  - [Validator registry](#validator-registry)
    - [Modified `add_validator_to_registry`](#modified-add_validator_to_registry)
  - [RANDAO verifications](#randao-verifications)
    - [New `verify_hash_chain_reveal`](#new-verify_hash_chain_reveal)
    - [New `verify_bls_randao_reveal`](#new-verify_bls_randao_reveal)
- [Beacon chain state transition function](#beacon-chain-state-transition-function)
  - [Epoch processing](#epoch-processing)
    - [Modified `process_epoch`](#modified-process_epoch)
    - [New `process_pending_randao_commitments`](#new-process_pending_randao_commitments)
  - [Block processing](#block-processing)
    - [Modified `process_randao`](#modified-process_randao)
    - [Operations](#operations)
      - [Modified `process_operations`](#modified-process_operations)
      - [RANDAO commitment registrations](#randao-commitment-registrations)
        - [New `process_randao_commitment_registration`](#new-process_randao_commitment_registration)

<!-- mdformat-toc end -->

## Introduction

This upgrade replaces the BLS-signature RANDAO reveal with a hash-chain
commit-reveal scheme, as part of the EIP-8321 upgrade.

RANDAO's resistance to grinding currently relies on BLS signatures being
*unique*, so that a proposer cannot bias its contribution. A hash chain relies
only on standard hash-function security instead: collision resistance replaces
BLS's uniqueness, and preimage resistance keeps each reveal unpredictable until
it is published. Both are believed to hold against a quantum adversary.

Each validator generates a hash chain off-chain and registers its tip as a
commitment. When proposing, the validator reveals the preimage of its currently
stored commitment; the state verifies the chain step, folds the raw preimage
into the RANDAO accumulator, and stores the preimage as the validator's new
commitment. The state therefore holds one 32-byte word per validator and walks
one link back per proposal.

A commitment is registered once, through a new per-block-capped beacon
operation. It cannot be updated in place, and a validator index keeps its
commitment for as long as the index exists, so the binding is one chain to one
public key to one validator index. A validator that ever needs a new chain
therefore obtains one the same way it would recover from a lost signing key: by
onboarding a new validator under a new public key. Validators that have not
registered a commitment continue to use the legacy BLS reveal; this is a
transitional path intended for removal in a later upgrade.

*Note*: This specification is built upon [Heze](../../heze/beacon-chain.md).

## Types

### New `PendingRandaoCommitments`

```python
class PendingRandaoCommitments(ProgressiveList[PendingRandaoCommitment]):
    """
    The queue of hash-chain RANDAO commitments awaiting activation.
    """
```

### New `RandaoCommitmentRegistrations`

```python
class RandaoCommitmentRegistrations(ProgressiveList[SignedRandaoCommitmentRegistration]):
    """
    The signed hash-chain RANDAO commitment registrations included in a beacon
    block.
    """
```

### New `RandaoCommitments`

```python
class RandaoCommitments(ProgressiveList[Bytes32]):
    """
    The current hash-chain RANDAO commitment of every validator. A zero entry
    means that the validator has not registered a commitment and reveals with
    the legacy BLS signature instead.
    """
```

## Constants

### Domains

| Name                                    | Value                      |
| --------------------------------------- | -------------------------- |
| `DOMAIN_RANDAO_COMMITMENT_REGISTRATION` | `DomainType('0x11000000')` |

### Hash chain

| Name                    | Value                  |
| ----------------------- | ---------------------- |
| `HASH_CHAIN_RANDAO_DST` | `b'HASH_CHAIN_RANDAO'` |

## Preset

### Hash-chain RANDAO

| Name                                  | Value                  |
| ------------------------------------- | ---------------------- |
| `COMMITMENT_REGISTRATION_DELAY`       | `Epoch(3)` (= 3)       |
| `MAX_RANDAO_COMMITMENT_REGISTRATIONS` | `Uint64(2**7)` (= 128) |

*Note*: `COMMITMENT_REGISTRATION_DELAY` must be at least
`MIN_SEED_LOOKAHEAD + 2` so that a registrant cannot know whether it proposes in
the activation epoch at the time its registration is included.

## Containers

### New containers

#### `PendingRandaoCommitment`

```python
class PendingRandaoCommitment(Container):
    validator_index: ValidatorIndex
    commitment: Bytes32
    activation_epoch: Epoch
```

#### `RandaoCommitmentRegistration`

```python
class RandaoCommitmentRegistration(Container):
    validator_index: ValidatorIndex
    commitment: Bytes32
```

#### `SignedRandaoCommitmentRegistration`

```python
class SignedRandaoCommitmentRegistration(Container):
    message: RandaoCommitmentRegistration
    signature: BLSSignature
```

### Modified containers

#### `BeaconBlockBody`

*Note*: `randao_reveal` is retained for validators that have not registered a
commitment. Exactly one of `randao_reveal` and `hash_chain_reveal` is populated;
the other is empty.

```python
class BeaconBlockBody(ProgressiveContainer(active_fields=[1] * 15)):
    randao_reveal: BLSSignature
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
    # [New in EIP8321]
    hash_chain_reveal: Bytes32
    # [New in EIP8321]
    randao_commitment_registrations: RandaoCommitmentRegistrations
```

#### `BeaconState`

```python
class BeaconState(ProgressiveContainer(active_fields=[1] * 48)):
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
    ptc_window: PTCWindow
    # [New in EIP8321]
    randao_commitments: RandaoCommitments
    # [New in EIP8321]
    pending_randao_commitments: PendingRandaoCommitments
```

## Helpers

### Crypto

#### New `blake3`

`def blake3(data: bytes) -> Bytes32` is the BLAKE3 hash function in its default
unkeyed hash mode, with no derive-key context, restricted to its default 32-byte
output.

All hashing introduced by this upgrade uses `blake3`; the `hash` helper
continues to serve the legacy reveal path.

### Validator registry

#### Modified `add_validator_to_registry`

*Note*: The function `add_validator_to_registry` is modified to initialize the
item in the `randao_commitments` list, preserving the invariant that it has one
entry per validator.

```python
def add_validator_to_registry(
    state: BeaconState, pubkey: BLSPubkey, withdrawal_credentials: Bytes32, amount: Uint64
) -> None:
    index = get_index_for_new_validator(state)
    validator = get_validator_from_deposit(pubkey, withdrawal_credentials, amount)
    set_or_append_list(state.validators, index, validator)
    set_or_append_list(state.balances, index, amount)
    set_or_append_list(state.previous_epoch_participation, index, ParticipationFlags(0b0000_0000))
    set_or_append_list(state.current_epoch_participation, index, ParticipationFlags(0b0000_0000))
    set_or_append_list(state.inactivity_scores, index, Uint64(0))
    # [New in EIP8321]
    set_or_append_list(state.randao_commitments, index, Bytes32())
```

### RANDAO verifications

#### New `verify_hash_chain_reveal`

```python
def verify_hash_chain_reveal(
    state: BeaconState, body: BeaconBlockBody, proposer_index: ValidatorIndex
) -> None:
    """
    Verify that ``body`` reveals the preimage of the proposer's stored commitment.
    """
    assert body.hash_chain_reveal != Bytes32()
    assert body.randao_reveal == G2_POINT_AT_INFINITY
    commitment = state.randao_commitments[proposer_index]
    assert blake3(HASH_CHAIN_RANDAO_DST + body.hash_chain_reveal) == commitment
```

#### New `verify_bls_randao_reveal`

```python
def verify_bls_randao_reveal(
    state: BeaconState, body: BeaconBlockBody, proposer_index: ValidatorIndex
) -> None:
    """
    Verify that ``body`` reveals the proposer's signature over the current epoch.
    """
    assert body.hash_chain_reveal == Bytes32()
    epoch = get_current_epoch(state)
    signing_root = compute_signing_root(epoch, get_domain(state, DOMAIN_RANDAO))
    pubkey = state.validators[proposer_index].pubkey
    assert bls.Verify(pubkey, signing_root, body.randao_reveal)
```

## Beacon chain state transition function

### Epoch processing

#### Modified `process_epoch`

*Note*: The function `process_epoch` is modified to call the new helper
`process_pending_randao_commitments`.

```python
def process_epoch(state: BeaconState) -> None:
    process_justification_and_finalization(state)
    process_inactivity_updates(state)
    process_rewards_and_penalties(state)
    process_registry_updates(state)
    # [New in EIP8321]
    process_pending_randao_commitments(state)
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
    process_sync_committee_updates(state)
    process_proposer_lookahead(state)
    process_ptc_window(state)
```

#### New `process_pending_randao_commitments`

*Note*: Commitments are queued with an activation epoch derived from the epoch
of inclusion, so the queue is ordered by activation epoch and can be drained
from the front.

```python
def process_pending_randao_commitments(state: BeaconState) -> None:
    next_epoch = Epoch(get_current_epoch(state) + 1)
    next_pending_commitment = 0
    for pending_commitment in state.pending_randao_commitments:
        if pending_commitment.activation_epoch > next_epoch:
            break

        index = pending_commitment.validator_index
        state.randao_commitments[index] = pending_commitment.commitment
        next_pending_commitment += 1

    state.pending_randao_commitments = state.pending_randao_commitments[next_pending_commitment:]
```

### Block processing

#### Modified `process_randao`

*Note*: A zero entry in `randao_commitments` means that the proposer has not
registered a hash chain, and the legacy BLS reveal applies. Rejecting a zero
reveal keeps that sentinel meaningful: without it, a validator revealing the
zero word would silently store the sentinel and fall back onto the legacy
branch.

*Note*: The hash-chain path folds in the raw reveal with a hash accumulator
rather than an `xor`. Commitments carry no identity and are copyable, so a
validator may register another's commitment. Doing so is self-defeating: the
copier does not hold the preimage, so it cannot propose at all until its victim
reveals, forfeiting every slot it is assigned in the meantime. Even once the
victim reveals, the accumulator has no efficiently computable inverse, so
re-injecting the copied reveal produces an unrelated mix rather than cancelling
the victim's contribution, which an `xor` accumulator would have allowed.

```python
def process_randao(state: BeaconState, body: BeaconBlockBody) -> None:
    epoch = get_current_epoch(state)
    proposer_index = get_beacon_proposer_index(state)

    # [New in EIP8321]
    if state.randao_commitments[proposer_index] != Bytes32():
        verify_hash_chain_reveal(state, body, proposer_index)
        mix = blake3(get_randao_mix(state, epoch) + body.hash_chain_reveal)
        state.randao_mixes[epoch % EPOCHS_PER_HISTORICAL_VECTOR] = mix
        state.randao_commitments[proposer_index] = body.hash_chain_reveal
    else:
        verify_bls_randao_reveal(state, body, proposer_index)
        mix = xor(get_randao_mix(state, epoch), hash(body.randao_reveal))
        state.randao_mixes[epoch % EPOCHS_PER_HISTORICAL_VECTOR] = mix
```

#### Operations

##### Modified `process_operations`

*Note*: The function `process_operations` is modified to process RANDAO
commitment registrations.

```python
def process_operations(
    state: BeaconState,
    body: BeaconBlockBody,
    parent_slot: Slot,
) -> None:
    assert len(body.deposits) == 0

    def for_ops(operations: Sequence[Any], fn: Callable[..., None], *args: Any) -> None:
        for operation in operations:
            fn(state, operation, *args)

    assert len(body.proposer_slashings) <= MAX_PROPOSER_SLASHINGS
    assert len(body.attester_slashings) <= MAX_ATTESTER_SLASHINGS_ELECTRA
    assert len(body.attestations) <= MAX_ATTESTATIONS_ELECTRA
    assert len(body.voluntary_exits) <= MAX_VOLUNTARY_EXITS
    assert len(body.bls_to_execution_changes) <= MAX_BLS_TO_EXECUTION_CHANGES
    assert len(body.payload_attestations) <= MAX_PAYLOAD_ATTESTATIONS
    # [New in EIP8321]
    assert len(body.randao_commitment_registrations) <= MAX_RANDAO_COMMITMENT_REGISTRATIONS

    for_ops(body.proposer_slashings, process_proposer_slashing)
    for_ops(body.attester_slashings, process_attester_slashing)
    for_ops(body.attestations, process_attestation, parent_slot)
    for_ops(body.voluntary_exits, process_voluntary_exit)
    for_ops(body.bls_to_execution_changes, process_bls_to_execution_change)
    for_ops(body.payload_attestations, process_payload_attestation)
    # [New in EIP8321]
    for_ops(body.randao_commitment_registrations, process_randao_commitment_registration)
```

##### RANDAO commitment registrations

###### New `process_randao_commitment_registration`

This is the one-time path that moves a validator from the legacy BLS reveal onto
its hash chain. It is valid only while the validator is unregistered, and only
while it has no other registration in flight. Nothing ever clears an entry of
`randao_commitments`, so a registered validator index keeps its chain for as
long as the index exists; replacing a lost chain means onboarding a new
validator under a new public key.

*Note*: Both checks are needed to make registration single-use. Once a
registration has activated, the stored commitment is non-zero and any replay
fails the first check. While it is still pending, the stored commitment is zero,
and the second check rejects the duplicate. The second check also rejects a
duplicate within a single block, since the first operation of the block appends
its entry to the queue.

*Note*: The activation delay is derived from the epoch of inclusion, the only
event the state observes. Signing a registration earlier only means committing
with less information.

```python
def process_randao_commitment_registration(
    state: BeaconState, signed_registration: SignedRandaoCommitmentRegistration
) -> None:
    registration = signed_registration.message
    index = registration.validator_index

    assert index < len(state.validators)
    assert registration.commitment != Bytes32()
    assert state.randao_commitments[index] == Bytes32()
    assert all(pending.validator_index != index for pending in state.pending_randao_commitments)

    # Fork-agnostic domain since registrations are valid across forks
    domain = compute_domain(
        DOMAIN_RANDAO_COMMITMENT_REGISTRATION,
        genesis_validators_root=state.genesis_validators_root,
    )
    signing_root = compute_signing_root(registration, domain)
    validator = state.validators[index]
    assert bls.Verify(validator.pubkey, signing_root, signed_registration.signature)

    state.pending_randao_commitments.append(
        PendingRandaoCommitment(
            validator_index=index,
            commitment=registration.commitment,
            activation_epoch=Epoch(get_current_epoch(state) + COMMITMENT_REGISTRATION_DELAY),
        )
    )
```
