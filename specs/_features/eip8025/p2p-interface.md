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

| Name                                       | Value                        |
| ------------------------------------------ | ---------------------------- |
| `MAX_SIGNED_EXECUTION_PROOF_ENVELOPE_SIZE` | `Uint64(4194449)` (= ~4 MiB) |

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
    execution_proof_roots: Dict[Root, Set[Root]]
    # [New in EIP8025]
    execution_proof_provers: Set[Tuple[Root, ProofType, ValidatorIndex]]
```

## The gossip domain: gossipsub

### Topics and messages

#### Global topics

##### New `execution_proof`

This topic is used to propagate `SignedExecutionProofEnvelope` messages.

```python
def validate_execution_proof_gossip(
    seen: Seen,
    store: Store,
    signed_proof_envelope: SignedExecutionProofEnvelope,
    proof_engine: ProofEngine,
) -> None:
    """Validate a SignedExecutionProofEnvelope for gossip propagation."""
    proof_envelope = signed_proof_envelope.message
    beacon_block_root = proof_envelope.beacon_block_root
    proof_root = hash_tree_root(proof_envelope)

    # [IGNORE] The proof has not already been processed
    if proof_root in seen.execution_proof_roots.get(beacon_block_root, set()):
        raise GossipIgnore("execution proof has already been processed")

    # [IGNORE] The proof's beacon block has been seen
    if beacon_block_root not in store.blocks:
        raise GossipIgnore("execution proof's beacon block has not been seen")

    # [REJECT] The proof's beacon block has passed consensus validation
    if beacon_block_root not in store.block_states:
        raise GossipReject("execution proof's beacon block failed validation")

    state = store.block_states[beacon_block_root]

    # [IGNORE] The proof's execution payload is available
    if beacon_block_root not in store.payloads:
        raise GossipIgnore("execution proof's payload is unavailable")

    payload_envelope = store.payloads[beacon_block_root]

    # [IGNORE] No valid proof is known for this beacon block and proof type
    if proof_envelope.proof_type in store.execution_proofs.get(beacon_block_root, {}):
        raise GossipIgnore("verified proof already known for this beacon block and proof type")

    # [IGNORE] This is the prover's first valid or invalid proof for this key
    validator_index = signed_proof_envelope.validator_index
    prover_key = (beacon_block_root, proof_envelope.proof_type, validator_index)
    if prover_key in seen.execution_proof_provers:
        raise GossipIgnore(
            "proof already seen from this prover for this beacon block and proof type"
        )

    # [REJECT] The execution proof envelope passes validation
    proof = validate_execution_proof_envelope(
        state,
        signed_proof_envelope,
        payload_envelope,
    )

    # Mark the authenticated proof and prover attempt as seen
    if beacon_block_root not in seen.execution_proof_roots:
        seen.execution_proof_roots[beacon_block_root] = set()
    seen.execution_proof_roots[beacon_block_root].add(proof_root)
    seen.execution_proof_provers.add(prover_key)

    # [REJECT] The execution proof is valid
    if not proof_engine.verify_execution_proof(proof):
        raise GossipReject("execution proof is invalid")
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
