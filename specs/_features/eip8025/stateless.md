# EIP-8025 -- Stateless Payload Validation

*Note*: This document is a work-in-progress for researchers and implementers.

> **EIP-8025 feature:** `stateless` (`eip8025-experimental`). This feature is
> optional and has no effect unless its handler is explicitly used.

## Introduction

This document defines an experimental policy for using independently verified
execution proofs to update local payload-validation bookkeeping. It does not
modify fork-choice weights, head selection, beacon-chain consensus processing,
or Gloas payload status.

## Constants

| Name                                               | Value       |
| -------------------------------------------------- | ----------- |
| `MIN_PROOF_TYPES_FOR_STATELESS_PAYLOAD_VALIDATION` | `Uint64(2)` |

## Helpers

### New `get_ancestor_path`

```python
def get_ancestor_path(
    store: Store, head_root: Root, ancestor_root: Root
) -> Optional[Sequence[Root]]:
    """
    Return roots from ``head_root`` through ``ancestor_root``, inclusive.
    Return ``None`` when local history cannot establish the ancestry.
    """
    path = []
    root = head_root
    while root in store.blocks:
        path.append(root)
        if root == ancestor_root:
            return path
        parent_root = store.blocks[root].parent_root
        if parent_root == Root():
            return None
        root = parent_root
    return None
```

### New `get_latest_valid_ancestor`

```python
def get_latest_valid_ancestor(
    store: Store,
    block_payload_statuses: Dict[Root, PayloadValidationStatus],
    head_root: Root,
) -> Optional[Root]:
    """
    Return the latest ancestor explicitly recorded as payload-valid.
    Return ``None`` when local history cannot establish one.
    """
    root = head_root
    while root in store.blocks:
        if block_payload_statuses.get(root) == PAYLOAD_STATUS_VALID:
            return root
        parent_root = store.blocks[root].parent_root
        if parent_root == Root():
            return None
        root = parent_root
    return None
```

### New `is_execution_proof_compatible_with_ancestor`

```python
def is_execution_proof_compatible_with_ancestor(
    store: Store,
    proof: ExecutionProof,
    head_root: Root,
    valid_ancestor_root: Root,
) -> bool:
    origin = proof.claim.origin
    head = proof.claim.head
    if head.beacon_block_root != head_root:
        return False

    origin_path = get_ancestor_path(store, head_root, origin.beacon_block_root)
    if origin_path is None:
        return False
    if store.blocks[origin.beacon_block_root].slot != origin.slot:
        return False

    valid_ancestor = store.blocks[valid_ancestor_root]
    return origin.slot <= valid_ancestor.slot
```

### New `has_sufficient_execution_proofs`

```python
def has_sufficient_execution_proofs(
    store: Store,
    block_payload_statuses: Dict[Root, PayloadValidationStatus],
    head_root: Root,
) -> bool:
    proofs = store.execution_proofs.get(head_root, {})
    valid_ancestor_root = get_latest_valid_ancestor(store, block_payload_statuses, head_root)

    qualifying_proof_types: Set[ProofType] = set()
    for proof_type, proof in proofs.items():
        if proof_type not in SUPPORTED_PROOF_TYPES:
            continue

        if valid_ancestor_root is None:
            if proof.claim.origin != proof.claim.head:
                continue
            if proof.claim.head.beacon_block_root != head_root:
                continue
        elif not is_execution_proof_compatible_with_ancestor(
            store, proof, head_root, valid_ancestor_root
        ):
            continue

        qualifying_proof_types.add(proof_type)

    return len(qualifying_proof_types) >= MIN_PROOF_TYPES_FOR_STATELESS_PAYLOAD_VALIDATION
```

### New `promote_payload_validation_status`

```python
def promote_payload_validation_status(
    store: Store,
    opt_store: OptimisticStore,
    block_payload_statuses: Dict[Root, PayloadValidationStatus],
    head_root: Root,
) -> bool:
    """
    Promote the proven lineage in local payload-validation bookkeeping.
    Return ``True`` if ``head_root`` is payload-valid after this call.
    """
    if block_payload_statuses.get(head_root) == PAYLOAD_STATUS_VALID:
        return True
    if block_payload_statuses.get(head_root) == PAYLOAD_STATUS_INVALIDATED:
        return False
    if not has_sufficient_execution_proofs(store, block_payload_statuses, head_root):
        return False

    valid_ancestor_root = get_latest_valid_ancestor(store, block_payload_statuses, head_root)
    roots_to_promote: Sequence[Root]
    if valid_ancestor_root is None:
        roots_to_promote = [head_root]
    else:
        ancestor_path = get_ancestor_path(store, head_root, valid_ancestor_root)
        if ancestor_path is None:
            return False
        roots_to_promote = ancestor_path[:-1]

    for root in roots_to_promote:
        if block_payload_statuses.get(root) == PAYLOAD_STATUS_INVALIDATED:
            return False

    for root in roots_to_promote:
        block_payload_statuses[root] = PAYLOAD_STATUS_VALID
        opt_store.optimistic_roots.discard(root)
    return True
```

## Handlers

### New `on_execution_proof_stateless`

This handler is an opt-in extension of `on_execution_proof`. Invalid proofs are
rejected by the baseline handler and MUST NOT invalidate the corresponding
beacon block. Peer scoring for invalid gossip remains implementation-dependent.

```python
def on_execution_proof_stateless(
    store: Store,
    opt_store: OptimisticStore,
    block_payload_statuses: Dict[Root, PayloadValidationStatus],
    signed_execution_proof: SignedExecutionProof,
    proof_verifier: ProofVerifier,
) -> bool:
    on_execution_proof(store, signed_execution_proof, proof_verifier)
    head_root = signed_execution_proof.message.claim.head.beacon_block_root
    return promote_payload_validation_status(store, opt_store, block_payload_statuses, head_root)
```
