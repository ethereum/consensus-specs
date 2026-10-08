# EIP-9998 -- Proof Engine

*Note*: This document is a work-in-progress for researchers and implementers.

## Table of contents

<!-- mdformat-toc start --slug=github --no-anchors --maxlevel=6 --minlevel=2 -->

- [Table of contents](#table-of-contents)
- [Introduction](#introduction)
- [Proof engine](#proof-engine)
  - [Modified `verify_execution_proof`](#modified-verify_execution_proof)

<!-- mdformat-toc end -->

## Introduction

This document follows the change to `ExecutionProof`, which carries the roots of
its public input rather than the public input itself.

*Note*: This specification is built upon [EIP-8025](../eip8025/proof-engine.md).

## Proof engine

### Modified `verify_execution_proof`

```python
def verify_execution_proof(
    self: ProofEngine,
    execution_proof: ExecutionProof,
) -> bool:
    """
    Verify an execution proof.

    Use ``hash_tree_root(public_input)`` as the proof-system public input, where
    ``public_input`` is the ``PublicInput`` with ``origin_block_root`` and
    ``head_block_root`` from ``execution_proof``, ``chain_id`` equal to
    ``DEPOSIT_CHAIN_ID``, and ``schema_id`` equal to
    ``STATELESS_INPUT_SCHEMA_ID``.

    Return ``True`` if ``execution_proof`` is valid.
    """
```
