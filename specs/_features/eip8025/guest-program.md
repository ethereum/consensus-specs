# EIP-8025 -- Recursive Proof Guest Program

*Note*: This document is a work-in-progress for researchers and implementers.

## Table of contents

<!-- mdformat-toc start --slug=github --no-anchors --maxlevel=6 --minlevel=2 -->

- [Table of contents](#table-of-contents)
- [Introduction](#introduction)
- [Guest inputs](#guest-inputs)
  - [New `GuestPublicInput`](#new-guestpublicinput)
  - [New `BeaconBlockBidWitness`](#new-beaconblockbidwitness)
  - [New `BeaconStateWitness`](#new-beaconstatewitness)
  - [New `BeaconChainWitness`](#new-beaconchainwitness)
  - [New `PrivateInput`](#new-privateinput)
- [Guest interface](#guest-interface)
  - [New `verify_execution_proof`](#new-verify_execution_proof)
  - [Execution-specs `verify_stateless_new_payload`](#execution-specs-verify_stateless_new_payload)
- [Guest processing](#guest-processing)
  - [New `verify_beacon_block_bid_witness`](#new-verify_beacon_block_bid_witness)
  - [New `verify_beacon_state_field`](#new-verify_beacon_state_field)
  - [New `get_progressive_list_element_field_gindex`](#new-get_progressive_list_element_field_gindex)
  - [New `verify_execution_transition`](#new-verify_execution_transition)
- [Availability boundary](#availability-boundary)

<!-- mdformat-toc end -->

## Introduction

This document defines the private witness interface and processing logic for a
recursive guest program that produces an `ExecutionProof`. The execution proof
commitment is the `GuestPublicInput` defined below. The gossiped
`ExecutionProofClaim` omits the local chain-configuration commitment.

Proofs are produced only for *full* beacon blocks. Headers for intervening
*empty* beacon blocks are included in the next proof's `beacon_lineage`. The
target post-state's authenticated `latest_block_hash` establishes that the
execution head did not change across those intervening blocks.

## Guest inputs

The guest inputs are implementation-level dataclasses, not consensus SSZ
containers. Only the returned `GuestPublicInput` is public.

### New `GuestPublicInput`

```python
class GuestPublicInput(ProgressiveContainer(active_fields=[1] * 3)):
    origin: ExecutionCheckpoint
    head: ExecutionCheckpoint
    chain_config_root: Root
```

`GuestPublicInput` is the complete public input committed by the guest program.
The local `chain_config_root` is injected at the proof-engine API boundary and
is not transmitted in execution-proof gossip.

### New `BeaconBlockBidWitness`

```python
@dataclass
class BeaconBlockBidWitness:
    signed_bid: SignedExecutionPayloadBid
    signed_bid_merkle_witness: Sequence[Bytes32]
```

### New `BeaconStateWitness`

```python
@dataclass
class BeaconStateWitness:
    genesis_time: Uint64
    genesis_time_merkle_witness: Sequence[Bytes32]
    fork: Fork
    fork_merkle_witness: Sequence[Bytes32]
    genesis_validators_root: Root
    genesis_validators_root_merkle_witness: Sequence[Bytes32]
    payload_expected_withdrawals: Withdrawals
    payload_expected_withdrawals_merkle_witness: Sequence[Bytes32]
    latest_block_hash: Hash32
    latest_block_hash_merkle_witness: Sequence[Bytes32]
    envelope_signer_pubkey: BLSPubkey
    envelope_signer_pubkey_merkle_witness: Sequence[Bytes32]
```

Each branch is opened against the target beacon block header's `state_root`. The
signer branch is opened at either the target proposer validator's `pubkey` or
the selected builder's `pubkey`, as determined by `builder_index`.

### New `BeaconChainWitness`

```python
@dataclass
class BeaconChainWitness:
    origin: Optional[ExecutionCheckpoint]
    previous_proof: Optional[ExecutionProof]
    previous_bid: Optional[BeaconBlockBidWitness]
    beacon_lineage: Sequence[BeaconBlockHeader]
    target_bid: BeaconBlockBidWitness
    signed_envelope: SignedExecutionPayloadEnvelope
    target_state: BeaconStateWitness
```

Exactly one of `origin` and `previous_proof` MUST be present. `origin` starts a
base proof with `origin` equal to its target. `previous_proof` advances an
existing recursive proof. `beacon_lineage` starts with the selected origin or
previous head and ends with the target head block. Slot gaps represent missed
slots. In a recursive proof, `previous_bid` authenticates the execution block
hash proven at the previous head. `target_bid` authenticates the target
envelope's bid. Intermediate blocks need only their headers because the target
state's authenticated `latest_block_hash` establishes that none changed the
execution head.

### New `PrivateInput`

```python
@dataclass
class PrivateInput:
    beacon_chain_witness: BeaconChainWitness
    execution_witness: Any
    chain_config: Any
    public_keys: Sequence[bytes]
```

`execution_witness`, `chain_config`, and `public_keys` have the execution-specs
types `ExecutionWitness`, `ChainConfig`, and `Sequence[Bytes]`, respectively.
They are represented as `Any` and `Sequence[bytes]` only because those types are
owned by the execution specifications and are not redefined by the executable
consensus reference model.

The guest authenticates and reconstructs `NewPayloadRequest` from
`beacon_chain_witness`. It combines that request with `execution_witness`,
`chain_config`, and `public_keys` to construct the execution-specs
`StatelessInput`. Supplying `chain_config` keeps the guest program generic
across networks that use the supported execution fork.

## Guest interface

The proof-system adapter implements the operations below. Their concrete
cryptographic encodings are deliberately outside the consensus specification.

### New `verify_execution_proof`

```python
def verify_execution_proof(
    self: Guest,
    previous_proof: ExecutionProof,
    chain_config_root: Root,
) -> bool:
    """
    Recursively verify ``previous_proof`` against ``GuestPublicInput`` rebuilt
    from its claim and ``chain_config_root``.
    Return ``True`` only if its proof type is bound to this guest program.
    """
```

### Execution-specs `verify_stateless_new_payload`

```python
def verify_stateless_new_payload(
    self: Guest,
    new_payload_request: NewPayloadRequest,
    execution_witness: Any,
    chain_config: Any,
    public_keys: Sequence[bytes],
) -> Any:
    """
    Construct the execution-specs ``StatelessInput``, invoke
    ``verify_stateless_new_payload``, and return its
    ``StatelessValidationResult``.
    """
```

This operation is an integration boundary, not a second execution-validation
algorithm. The adapter constructs exactly one execution-specs `StatelessInput`
from the private arguments. A typed implementation invokes
`verify_stateless_new_payload` directly. A serialized zkVM implementation MAY
invoke `run_stateless_guest` and decode its output. In both cases the logical
operations and guarantees MUST match the execution specifications, including
chain-configuration validation, parent-header authentication, block-hash
validation, versioned-hash validation, transaction execution, and output-root
checks. The returned `StatelessValidationResult.chain_config` MUST be the exact
configuration used by that validation. This interface does not return a
`new_payload_request_root`.

## Guest processing

### New `verify_beacon_block_bid_witness`

```python
def verify_beacon_block_bid_witness(
    header: BeaconBlockHeader,
    witness: BeaconBlockBidWitness,
) -> None:
    bid = witness.signed_bid.message
    gindex = get_generalized_index(BeaconBlockBody, "signed_execution_payload_bid")

    assert bid.slot == header.slot
    assert bid.parent_block_root == header.parent_root
    assert is_valid_merkle_branch(
        leaf=hash_tree_root(witness.signed_bid),
        branch=witness.signed_bid_merkle_witness,
        depth=floorlog2(gindex),
        index=get_subtree_index(gindex),
        root=header.body_root,
    )
```

The signed bid is authenticated as a complete field of an already accepted
beacon block. Its BLS signature is not reverified by the guest.

### New `verify_beacon_state_field`

```python
def verify_beacon_state_field(
    value: Any,
    branch: Sequence[Bytes32],
    generalized_index: GeneralizedIndex,
    state_root: Root,
) -> None:
    assert is_valid_merkle_branch(
        leaf=hash_tree_root(value),
        branch=branch,
        depth=floorlog2(generalized_index),
        index=get_subtree_index(generalized_index),
        root=state_root,
    )
```

### New `get_progressive_list_element_field_gindex`

```python
def get_progressive_list_element_field_gindex(
    container_type: Any,
    container_field: str,
    list_type: Any,
    element_index: int,
    element_type: Any,
    element_field: str,
) -> GeneralizedIndex:
    """Return the state-relative gindex of a field in a progressive-list item."""
    indices = (
        get_generalized_index(container_type, container_field),
        GeneralizedIndex(list_type.chunk_to_gindex(element_index)),
        get_generalized_index(element_type, element_field),
    )
    result = GeneralizedIndex(1)
    for index in indices:
        depth = int(floorlog2(index))
        result = GeneralizedIndex((int(result) << depth) | (int(index) ^ (1 << depth)))
    return result
```

Progressive lists have index-dependent paths, so their element fields cannot be
located with the static `get_generalized_index` helper alone.

### New `verify_execution_transition`

```python
def verify_execution_transition(
    guest: Guest,
    private_input: PrivateInput,
    chain_config_root: Root,
) -> GuestPublicInput:
    beacon_chain_witness = private_input.beacon_chain_witness

    previous_proof = beacon_chain_witness.previous_proof
    if previous_proof is None:
        origin = beacon_chain_witness.origin
        assert origin is not None
        previous_head = origin
    else:
        assert beacon_chain_witness.origin is None
        assert guest.verify_execution_proof(previous_proof, chain_config_root)
        origin = previous_proof.claim.origin
        previous_head = previous_proof.claim.head

    lineage = beacon_chain_witness.beacon_lineage
    assert len(lineage) >= 1

    checkpoint_header = lineage[0]
    assert checkpoint_header.slot == previous_head.slot
    assert hash_tree_root(checkpoint_header) == previous_head.beacon_block_root

    parent_beacon_block_root = previous_head.beacon_block_root
    previous_slot = previous_head.slot

    for header in lineage[1:]:
        assert header.slot > previous_slot
        assert header.parent_root == parent_beacon_block_root

        parent_beacon_block_root = hash_tree_root(header)
        previous_slot = header.slot

    target_header = lineage[-1]
    verify_beacon_block_bid_witness(target_header, beacon_chain_witness.target_bid)
    target_bid = beacon_chain_witness.target_bid.signed_bid.message
    envelope = beacon_chain_witness.signed_envelope.message
    payload = envelope.payload
    target_state = beacon_chain_witness.target_state

    target_checkpoint = ExecutionCheckpoint(
        slot=target_header.slot,
        beacon_block_root=hash_tree_root(target_header),
    )
    previous_execution_block_hash: Optional[Hash32] = None
    if previous_proof is None:
        assert len(lineage) == 1
        assert beacon_chain_witness.previous_bid is None
        assert origin == target_checkpoint
    else:
        assert len(lineage) >= 2
        previous_bid = beacon_chain_witness.previous_bid
        assert previous_bid is not None
        verify_beacon_block_bid_witness(
            checkpoint_header,
            previous_bid,
        )
        previous_execution_block_hash = previous_bid.signed_bid.message.block_hash

    # Authenticate every state-dependent input used below against the accepted
    # target block's post-state root.
    verify_beacon_state_field(
        target_state.genesis_time,
        target_state.genesis_time_merkle_witness,
        get_generalized_index(BeaconState, "genesis_time"),
        target_header.state_root,
    )
    verify_beacon_state_field(
        target_state.fork,
        target_state.fork_merkle_witness,
        get_generalized_index(BeaconState, "fork"),
        target_header.state_root,
    )
    verify_beacon_state_field(
        target_state.genesis_validators_root,
        target_state.genesis_validators_root_merkle_witness,
        get_generalized_index(BeaconState, "genesis_validators_root"),
        target_header.state_root,
    )
    verify_beacon_state_field(
        target_state.payload_expected_withdrawals,
        target_state.payload_expected_withdrawals_merkle_witness,
        get_generalized_index(BeaconState, "payload_expected_withdrawals"),
        target_header.state_root,
    )
    verify_beacon_state_field(
        target_state.latest_block_hash,
        target_state.latest_block_hash_merkle_witness,
        get_generalized_index(BeaconState, "latest_block_hash"),
        target_header.state_root,
    )

    if previous_execution_block_hash is not None:
        assert target_state.latest_block_hash == previous_execution_block_hash

    if envelope.builder_index == BUILDER_INDEX_SELF_BUILD:
        signer_gindex = get_progressive_list_element_field_gindex(
            BeaconState,
            "validators",
            Validators,
            target_header.proposer_index,
            Validator,
            "pubkey",
        )
    else:
        signer_gindex = get_progressive_list_element_field_gindex(
            BeaconState,
            "builders",
            Builders,
            envelope.builder_index,
            Builder,
            "pubkey",
        )
    verify_beacon_state_field(
        target_state.envelope_signer_pubkey,
        target_state.envelope_signer_pubkey_merkle_witness,
        signer_gindex,
        target_header.state_root,
    )

    # Bind the payload envelope to the authenticated target bid and beacon
    # block header.
    target_beacon_block_root = target_checkpoint.beacon_block_root
    assert envelope.beacon_block_root == target_beacon_block_root
    assert envelope.parent_beacon_block_root == target_header.parent_root
    assert envelope.builder_index == target_bid.builder_index
    assert payload.block_hash == target_bid.block_hash
    assert payload.prev_randao == target_bid.prev_randao
    assert payload.gas_limit == target_bid.gas_limit
    assert hash_tree_root(envelope.execution_requests) == target_bid.execution_requests_root
    assert payload.slot_number == target_header.slot
    assert payload.parent_hash == target_state.latest_block_hash
    assert payload.timestamp == Uint64(
        target_state.genesis_time + (target_header.slot - GENESIS_SLOT) * SLOT_DURATION_MS // 1000
    )
    assert hash_tree_root(payload.withdrawals) == hash_tree_root(
        target_state.payload_expected_withdrawals
    )

    # Enforce the same count bounds as execution-payload-envelope gossip.
    assert len(envelope.execution_requests.withdrawals) <= MAX_WITHDRAWAL_REQUESTS_PER_PAYLOAD
    assert len(envelope.execution_requests.consolidations) <= MAX_CONSOLIDATION_REQUESTS_PER_PAYLOAD
    assert (
        len(envelope.execution_requests.builder_deposits)
        <= MAX_BUILDER_DEPOSIT_REQUESTS_PER_PAYLOAD
    )
    assert len(envelope.execution_requests.builder_exits) <= MAX_BUILDER_EXIT_REQUESTS_PER_PAYLOAD
    assert len(payload.withdrawals) <= MAX_WITHDRAWALS_PER_PAYLOAD

    envelope_epoch = compute_epoch_at_slot(target_header.slot)
    fork_version = (
        target_state.fork.previous_version
        if envelope_epoch < target_state.fork.epoch
        else target_state.fork.current_version
    )
    domain = compute_domain(
        DOMAIN_BEACON_BUILDER,
        fork_version,
        target_state.genesis_validators_root,
    )
    signing_root = compute_signing_root(envelope, domain)
    assert bls.Verify(
        target_state.envelope_signer_pubkey,
        signing_root,
        beacon_chain_witness.signed_envelope.signature,
    )

    new_payload_request = NewPayloadRequest(
        execution_payload=payload,
        versioned_hashes=[
            kzg_commitment_to_versioned_hash(commitment)
            for commitment in target_bid.blob_kzg_commitments
        ],
        parent_beacon_block_root=envelope.parent_beacon_block_root,
        execution_requests=envelope.execution_requests,
    )

    execution_result = guest.verify_stateless_new_payload(
        new_payload_request,
        private_input.execution_witness,
        private_input.chain_config,
        private_input.public_keys,
    )
    assert execution_result.successful_validation
    assert hash_tree_root(execution_result.chain_config) == chain_config_root

    return GuestPublicInput(
        origin=origin,
        head=ExecutionCheckpoint(
            slot=target_header.slot,
            beacon_block_root=target_beacon_block_root,
        ),
        chain_config_root=chain_config_root,
    )
```

## Availability boundary

The guest proves the payload-envelope and execution-engine validity checks; it
does not prove payload data availability. The block-in-blob availability design
provides that separate guarantee. Verification and storage of an execution proof
do not change fork choice, beacon-chain consensus processing, or Gloas payload
status. Any client policy that uses a stored proof to avoid payload retrieval is
outside this specification.
