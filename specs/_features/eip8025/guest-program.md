# EIP-8025 -- Recursive Proof Guest Program

*Note*: This document is a work-in-progress for researchers and implementers.

## Table of contents

<!-- mdformat-toc start --slug=github --no-anchors --maxlevel=6 --minlevel=2 -->

- [Table of contents](#table-of-contents)
- [Introduction](#introduction)
- [Constants](#constants)
  - [Generalized indices](#generalized-indices)
- [Guest inputs](#guest-inputs)
  - [New `BeaconBlockBidWitness`](#new-beaconblockbidwitness)
  - [New `BeaconChainWitness`](#new-beaconchainwitness)
  - [New `PrivateInput`](#new-privateinput)
- [Guest interface](#guest-interface)
  - [New `verify_execution_proof`](#new-verify_execution_proof)
  - [Execution-specs `verify_stateless_new_payload`](#execution-specs-verify_stateless_new_payload)
- [Guest processing](#guest-processing)
  - [New `verify_beacon_block_bid_witness`](#new-verify_beacon_block_bid_witness)
  - [New `process_private_input`](#new-process_private_input)
- [Signature boundary](#signature-boundary)

<!-- mdformat-toc end -->

## Introduction

This document defines the private witness interface and processing logic for a
recursive guest program that produces an `ExecutionProof`. The execution proof
commitment is the `PublicInput` defined in [beacon-chain.md](./beacon-chain.md).

Proofs are produced only for *full* beacon blocks. *Empty* beacon blocks are
included in the next proof's `beacon_lineage`, where their empty status is
established by the next authenticated bid continuing from each empty block's
parent execution block hash.

## Constants

### Generalized indices

| Name                                  | Value                                                                            |
| ------------------------------------- | -------------------------------------------------------------------------------- |
| `SIGNED_EXECUTION_PAYLOAD_BID_GINDEX` | `get_generalized_index(BeaconBlockBody, 'signed_execution_payload_bid')` (= 357) |

## Guest inputs

The guest inputs are implementation-level dataclasses, not consensus SSZ
containers. Only the returned `PublicInput` is public.

### New `BeaconBlockBidWitness`

```python
@dataclass
class BeaconBlockBidWitness:
    header: BeaconBlockHeader
    signed_bid: SignedExecutionPayloadBid
    signed_bid_merkle_witness: Sequence[Bytes32]
```

### New `BeaconChainWitness`

```python
@dataclass
class BeaconChainWitness:
    origin: Optional[ExecutionCheckpoint]
    previous_proof: Optional[ExecutionProof]
    beacon_lineage: Sequence[BeaconBlockBidWitness]
    signed_envelope: SignedExecutionPayloadEnvelope
```

Exactly one of `origin` and `previous_proof` MUST be present. `origin` starts a
base proof. `previous_proof` advances an existing recursive proof.
`beacon_lineage` starts with the selected origin or previous head, ends with the
target head block. The only intervening blocks are produced *empty* beacon
blocks; missed slots contribute no witness. Its first witness opens the
checkpoint's signed execution payload bid and supplies its execution block hash
to the next transition.

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
) -> bool:
    """
    Recursively verify ``previous_proof`` and its committed public input.
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
from the arguments. A typed implementation invokes
`verify_stateless_new_payload` directly. A serialized zkVM implementation MAY
invoke `run_stateless_guest`, decode its output, and MUST check that the
returned `new_payload_request_root` equals `compute_new_payload_request_root`
for the constructed input before exposing the result. In both cases the logical
operations and guarantees MUST match the execution specifications, including
chain-configuration validation, parent-header authentication, block-hash
validation, versioned-hash validation, transaction execution, and output-root
checks.

## Guest processing

### New `verify_beacon_block_bid_witness`

```python
def verify_beacon_block_bid_witness(witness: BeaconBlockBidWitness) -> None:
    header = witness.header
    bid = witness.signed_bid.message

    assert bid.slot == header.slot
    assert bid.parent_block_root == header.parent_root
    assert is_valid_merkle_branch(
        leaf=hash_tree_root(witness.signed_bid),
        branch=witness.signed_bid_merkle_witness,
        depth=floorlog2(SIGNED_EXECUTION_PAYLOAD_BID_GINDEX),
        index=get_subtree_index(SIGNED_EXECUTION_PAYLOAD_BID_GINDEX),
        root=header.body_root,
    )
```

### New `process_private_input`

```python
def process_private_input(
    guest: Guest,
    private_input: PrivateInput,
) -> PublicInput:
    beacon_chain_witness = private_input.beacon_chain_witness

    previous_proof = beacon_chain_witness.previous_proof
    if previous_proof is None:
        origin = beacon_chain_witness.origin
        assert origin is not None
        previous_head = origin
    else:
        assert beacon_chain_witness.origin is None
        assert guest.verify_execution_proof(previous_proof)
        origin = previous_proof.public_input.origin
        previous_head = previous_proof.public_input.head

    lineage = beacon_chain_witness.beacon_lineage
    assert len(lineage) >= 2

    checkpoint_witness = lineage[0]
    verify_beacon_block_bid_witness(checkpoint_witness)
    assert checkpoint_witness.header.slot == previous_head.slot
    assert hash_tree_root(checkpoint_witness.header) == previous_head.beacon_block_root

    parent_beacon_block_root = previous_head.beacon_block_root
    previous_slot = previous_head.slot
    parent_execution_block_hash = checkpoint_witness.signed_bid.message.block_hash
    previous_bid = None

    for witness in lineage[1:]:
        header = witness.header
        bid = witness.signed_bid.message

        # Slots omitted from the lineage are missed slots. Every included block
        # must advance the canonical beacon-block ancestry.
        assert header.slot > previous_slot
        assert header.parent_root == parent_beacon_block_root

        # Authenticate the complete signed bid against the block body root.
        verify_beacon_block_bid_witness(witness)

        # Until the target payload is applied, every produced block continues
        # from the execution head committed by the predecessor proof.
        assert bid.parent_block_hash == parent_execution_block_hash

        # The current bid establishes that the preceding produced block after
        # the checkpoint was empty.
        if previous_bid is not None:
            assert bid.parent_block_hash != previous_bid.block_hash

        parent_beacon_block_root = hash_tree_root(header)
        previous_slot = header.slot
        previous_bid = bid

    target = lineage[-1]
    target_header = target.header
    target_bid = target.signed_bid.message
    envelope = beacon_chain_witness.signed_envelope.message
    payload = envelope.payload

    # Bind the payload envelope to the authenticated target bid and beacon
    # block header.
    target_beacon_block_root = hash_tree_root(target_header)
    assert envelope.beacon_block_root == target_beacon_block_root
    assert envelope.parent_beacon_block_root == target_header.parent_root
    assert envelope.builder_index == target_bid.builder_index
    assert payload.block_hash == target_bid.block_hash
    assert payload.prev_randao == target_bid.prev_randao
    assert payload.gas_limit == target_bid.gas_limit
    assert hash_tree_root(envelope.execution_requests) == target_bid.execution_requests_root
    assert payload.slot_number == target_header.slot
    assert payload.parent_hash == parent_execution_block_hash

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
    assert execution_result.chain_config == private_input.chain_config

    return PublicInput(
        origin=origin,
        head=ExecutionCheckpoint(
            slot=target_header.slot,
            beacon_block_root=target_beacon_block_root,
        ),
    )
```

## Signature boundary

*TODO*: Determine whether the guest should verify the bid and envelope BLS
signatures and, if so, define how it authenticates the signer public key and
signing domain from consensus state.

`SignedExecutionPayloadBid` and `SignedExecutionPayloadEnvelope` are used as the
standard consensus wire objects. The guest authenticates the complete signed bid
through the beacon block body root, but does not verify either BLS signature.
Consensus clients MUST perform the normal Gloas signature, builder, timing,
withdrawal, availability, and state-dependent checks before accepting the block
and envelope. The guest proves the consensus/execution binding and the execution
transition itself.
