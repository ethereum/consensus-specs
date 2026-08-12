# EIP-8025 -- Networking

This document contains the networking specifications for EIP-8025.

*Note*: This specification is built upon [Gloas](../../gloas/p2p-interface.md)
and imports proof types from [beacon-chain.md](./beacon-chain.md).

EIP-8025 proofs propagate exclusively through gossip. No EIP-8025-specific
Req/Resp protocol is defined.

## Table of contents

<!-- mdformat-toc start --slug=github --no-anchors --maxlevel=6 --minlevel=2 -->

- [Table of contents](#table-of-contents)
- [Constants](#constants)
  - [Type-specific SSZ bounds](#type-specific-ssz-bounds)
- [Helpers](#helpers)
  - [Modified `Seen`](#modified-seen)
- [The gossip domain: gossipsub](#the-gossip-domain-gossipsub)
  - [Topics and messages](#topics-and-messages)
    - [Global topics](#global-topics)
      - [New `execution_proof`](#new-execution_proof)
- [The discovery domain: discv5](#the-discovery-domain-discv5)
  - [ENR structure](#enr-structure)
    - [Execution proof awareness](#execution-proof-awareness)

<!-- mdformat-toc end -->

## Constants

### Type-specific SSZ bounds

| Name                              | Value                        |
| --------------------------------- | ---------------------------- |
| `MAX_SIGNED_EXECUTION_PROOF_SIZE` | `Uint64(4194497)` (= ~4 MiB) |

## Helpers

### Modified `Seen`

```python
@dataclass
class Seen:
    proposer_slots: Set[Tuple[Slot, ValidatorIndex]]
    aggregator_epochs: Set[Tuple[Epoch, ValidatorIndex]]
    aggregate_data_roots: Dict[Tuple[Root, CommitteeIndex], Set[Tuple[Boolean, ...]]]
    voluntary_exit_indices: Set[ValidatorIndex]
    proposer_slashing_indices: Set[ValidatorIndex]
    attester_slashing_indices: Set[ValidatorIndex]
    attestation_validator_epochs: Set[Tuple[Epoch, ValidatorIndex]]
    sync_contribution_aggregator_slots: Set[Tuple[Slot, ValidatorIndex, Uint64]]
    sync_contribution_data: Dict[Tuple[Slot, Root, Uint64], Set[Tuple[Boolean, ...]]]
    sync_message_validator_slots: Set[Tuple[Slot, ValidatorIndex, Uint64]]
    bls_to_execution_change_indices: Set[ValidatorIndex]
    data_column_sidecar_tuples: Set[Tuple[Root, ColumnIndex]]
    execution_payloads: Dict[Hash32, ExecutionPayload]
    execution_payload_envelopes: Set[Tuple[Root, BuilderIndex]]
    payload_attestation_validators: Set[Tuple[Slot, ValidatorIndex]]
    execution_payload_bids: Set[Tuple[Slot, Hash32, Root, BuilderIndex]]
    best_execution_payload_bid: Dict[Tuple[Slot, Hash32, Root], Gwei]
    proposer_preferences: Dict[Tuple[Root, Slot], ProposerPreferences]
    # [New in EIP8025]
    execution_proof_provers: Set[Tuple[Root, ProofType, ValidatorIndex]]
```

## The gossip domain: gossipsub

### Topics and messages

#### Global topics

##### New `execution_proof`

This topic is used to propagate `SignedExecutionProof` messages.

```python
def validate_execution_proof_gossip(
    seen: Seen,
    store: Store,
    state: BeaconState,
    signed_execution_proof: SignedExecutionProof,
    trusted_execution_checkpoint: ExecutionCheckpoint,
    supported_proof_types: Set[ProofType],
) -> None:
    """
    Validate a SignedExecutionProof for gossip propagation.
    Raises GossipIgnore or GossipReject on validation failure.
    """
    proof = signed_execution_proof.message
    head = proof.claim.head
    head_root = head.beacon_block_root

    # [REJECT] The proof data is non-empty and within the size limit
    if len(proof.proof_data) == 0:
        raise GossipReject("execution proof data is empty")
    if len(proof.proof_data) > MAX_PROOF_SIZE:
        raise GossipReject("execution proof data exceeds the size limit")

    # [REJECT] The proof type is supported
    if proof.proof_type not in supported_proof_types:
        raise GossipReject("execution proof type is unsupported")

    # [REJECT] The prover validator index is valid
    validator_index = signed_execution_proof.validator_index
    if validator_index >= len(state.validators):
        raise GossipReject("execution proof's validator index is invalid")

    # [REJECT] The prover is an active validator
    validator = state.validators[validator_index]
    if not is_active_validator(validator, get_current_epoch(state)):
        raise GossipReject("execution proof's validator is not active")

    # [IGNORE] The proof's head block has been seen
    if head_root not in store.blocks:
        raise GossipIgnore("execution proof's head block has not been seen")

    # [REJECT] The proof's head block passes validation
    if head_root not in store.block_states:
        raise GossipReject("execution proof's head block failed validation")

    # [IGNORE] No verified proof is known for this head and proof type
    proof_key = (head_root, proof.proof_type)
    if proof_key in store.execution_proofs:
        raise GossipIgnore("verified proof already known for this head and proof type")

    # [IGNORE] This is the prover's first valid or invalid proof for this key
    prover_key = (head_root, proof.proof_type, validator_index)
    if prover_key in seen.execution_proof_provers:
        raise GossipIgnore("proof already seen from this prover for this head and proof type")

    # [REJECT] The proof starts at the locally trusted checkpoint
    if proof.claim.origin != trusted_execution_checkpoint:
        raise GossipReject("execution proof's origin is not the trusted checkpoint")

    # [REJECT] The proof's head identifies the accepted beacon block
    block = store.blocks[head_root]
    if head.slot != block.slot:
        raise GossipReject("execution proof's head does not identify the accepted block")

    # [REJECT] The prover signature is valid
    domain = get_domain(state, DOMAIN_EXECUTION_PROOF, compute_epoch_at_slot(state.slot))
    signing_root = compute_signing_root(proof, domain)
    if not bls.Verify(validator.pubkey, signing_root, signed_execution_proof.signature):
        raise GossipReject("execution proof's signature is invalid")

    # Mark the authenticated prover attempt as seen
    seen.execution_proof_provers.add(prover_key)
```

## The discovery domain: discv5

### ENR structure

#### Execution proof awareness

A new field is added to the ENR under the key `eproof` to facilitate discovery
and peering between nodes that participate in execution-proof gossip.

| Key      | Value                                    |
| -------- | ---------------------------------------- |
| `eproof` | Execution layer proof awareness, `Uint8` |

A node is considered execution proof-aware if the `eproof` key is present and
its value is not `0`. An execution proof-aware node subscribes to the
`execution_proof` gossip topic and implements its validation rules. Clients MAY
prefer execution proof-aware nodes when selecting peers for execution-proof
gossip.
