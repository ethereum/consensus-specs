# EIP-8025 -- Proof Engine

*Note*: This document is a work-in-progress for researchers and implementers.

## Table of contents

<!-- mdformat-toc start --slug=github --no-anchors --maxlevel=6 --minlevel=2 -->

- [Table of contents](#table-of-contents)
- [Introduction](#introduction)
- [Proof engine](#proof-engine)
  - [New `verify_execution_proof`](#new-verify_execution_proof)

<!-- mdformat-toc end -->

## Introduction

This document contains the Proof Engine specification. The Proof Engine enables
stateless validation of execution payloads through execution proofs.

## Proof engine

The implementation-dependent `ProofEngine` protocol encapsulates proof
verification through `self.verify_execution_proof`.

### New `verify_execution_proof`

```python
def verify_execution_proof(
    self: ProofEngine,
    execution_proof: ExecutionProof,
) -> bool:
    """
    Verify an execution proof.

    Use ``hash_tree_root(execution_proof.public_input)`` as the proof-system
    public input.

    Return ``True`` if ``execution_proof`` is valid.
    """
```
