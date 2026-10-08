# EIP-9998 -- Networking

*Note*: This document is a work-in-progress for researchers and implementers.

This document contains the networking specifications for EIP-9998.

*Note*: This specification is built upon
[EIP-8025](../eip8025/p2p-interface.md).

## Table of contents

<!-- mdformat-toc start --slug=github --no-anchors --maxlevel=6 --minlevel=2 -->

- [Table of contents](#table-of-contents)
- [Constants](#constants)
  - [Type-specific SSZ bounds](#type-specific-ssz-bounds)
- [The gossip domain: gossipsub](#the-gossip-domain-gossipsub)
  - [Topics and messages](#topics-and-messages)
    - [Global topics](#global-topics)
      - [Modified `execution_proof`](#modified-execution_proof)

<!-- mdformat-toc end -->

## Constants

### Type-specific SSZ bounds

| Name                              | Value             |
| --------------------------------- | ----------------- |
| `MAX_SIGNED_EXECUTION_PROOF_SIZE` | `Uint64(4194481)` |

*Note*: `MAX_SIGNED_EXECUTION_PROOF_SIZE` replaces
`MAX_SIGNED_EXECUTION_PROOF_ENVELOPE_SIZE`.

## The gossip domain: gossipsub

### Topics and messages

#### Global topics

##### Modified `execution_proof`

This topic is used to propagate `SignedExecutionProof` messages.

```python
def validate_execution_proof_gossip(
    seen: Seen,
    store: Store,
    # [Modified in EIP9998]
    signed_proof: SignedExecutionProof,
    proof_engine: ProofEngine,
) -> None:
    """
    Validate a SignedExecutionProof for gossip propagation.
    Raises GossipIgnore or GossipReject on validation failure.
    """
    proof = signed_proof.message

    # [REJECT] The proof data is non-empty
    if len(proof.proof_data) == 0:
        raise GossipReject("execution proof is empty")

    # [REJECT] The proof type is supported
    if proof.proof_type not in get_supported_proof_types():
        raise GossipReject("unexpected execution proof type")

    # [Modified in EIP9998]
    head_block_root = proof.head_block_root

    # [IGNORE] The proof's beacon block has been seen
    if head_block_root not in store.blocks:
        raise GossipIgnore("execution proof's beacon block has not been seen")

    # [IGNORE] No valid proof is known for this beacon block and proof type
    if proof.proof_type in store.execution_proofs.get(head_block_root, {}):
        raise GossipIgnore("verified proof already known for this beacon block and proof type")

    proof_root = hash_tree_root(proof)

    # [IGNORE] The proof has not already been processed
    if proof_root in seen.execution_proof_roots.get(head_block_root, set()):
        raise GossipIgnore("execution proof has already been processed")

    # [IGNORE] This is the prover's first valid or invalid proof for this key
    validator_index = signed_proof.validator_index
    prover_key = (head_block_root, proof.proof_type, validator_index)
    if prover_key in seen.execution_proof_provers:
        raise GossipIgnore(
            "proof already seen from this prover for this beacon block and proof type"
        )

    # [New in EIP9998]
    # [IGNORE] The proof's beacon block has been validated
    if head_block_root not in store.block_states:
        raise GossipIgnore("execution proof's beacon block has not been validated")

    state = store.block_states[head_block_root]

    # [REJECT] The signed execution proof passes validation
    try:
        # [Modified in EIP9998]
        verify_signed_execution_proof(state, signed_proof)
    except AssertionError:
        raise GossipReject("signed execution proof is invalid") from None

    # Mark the authenticated proof and prover attempt as seen
    if head_block_root not in seen.execution_proof_roots:
        seen.execution_proof_roots[head_block_root] = set()
    seen.execution_proof_roots[head_block_root].add(proof_root)
    seen.execution_proof_provers.add(prover_key)

    # [REJECT] The execution proof is valid
    if not proof_engine.verify_execution_proof(proof):
        raise GossipReject("execution proof is invalid")
```
