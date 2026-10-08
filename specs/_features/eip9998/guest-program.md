# EIP-9998 -- Recursive Guest Program

*Note*: This document is a work-in-progress for researchers and implementers.

## Table of contents

<!-- mdformat-toc start --slug=github --no-anchors --maxlevel=6 --minlevel=2 -->

- [Table of contents](#table-of-contents)
- [Introduction](#introduction)
- [Guest inputs](#guest-inputs)
  - [New `PrivateInput`](#new-privateinput)
- [Guest processing](#guest-processing)
  - [New `verify_execution_transition`](#new-verify_execution_transition)
- [Execution engine](#execution-engine)
- [Separation of consensus and execution](#separation-of-consensus-and-execution)

<!-- mdformat-toc end -->

## Introduction

This document defines the private input and the processing logic of the
recursive guest program. Each run proves one *full* execution payload. It
extends the parent proof, whose head is the block of the last full payload
before the target block, or it starts a new recursion at the target block.
Blocks between the two are *empty* or missed, and the guest does not see them.

The guest verifies the parent proof with the proof engine, as consensus clients
verify proofs. It binds the payload to its beacon block with
`verify_execution_payload_envelope`, the handler consensus clients run on a
received payload envelope, which validates the payload through the execution
engine. The public input it commits to is the `PublicInput` defined in
[beacon-chain.md](./beacon-chain.md).

## Guest inputs

The guest inputs are implementation-level dataclasses, not consensus SSZ
containers.

### New `PrivateInput`

```python
@dataclass
class PrivateInput:
    previous_proof: ExecutionProof | None
    previous_state: BeaconState | None
    state: BeaconState
    signed_envelope: SignedExecutionPayloadEnvelope
    execution_witness: Any
```

- `previous_proof` is the parent proof, or `None` to start a recursion at the
  target block.
- `previous_state` is the post-state of the parent proof's head block. It is
  `None` exactly when `previous_proof` is `None`.
- `state` is the post-state of the target block, and `signed_envelope` is the
  target block's payload envelope.
- `execution_witness` has the execution-specs type `ExecutionWitness`. The
  execution engine running in the guest is bound to it.

Together, `previous_state` and `state` form the step's beacon state witness.
Both states are post-block states, not advanced by `process_slots`, so their
`latest_block_header.state_root` is still empty. Implementations SHOULD supply
each state as a partial SSZ tree whose root is the full state root and in which
only the fields read by the guest are expanded. Reading a field that is not
expanded MUST fail the proof.

## Guest processing

### New `verify_execution_transition`

```python
def verify_execution_transition(
    proof_engine: ProofEngine,
    execution_engine: ExecutionEngine,
    private_input: PrivateInput,
) -> PublicInput:
    state = private_input.state
    signed_envelope = private_input.signed_envelope
    envelope = signed_envelope.message

    previous_proof = private_input.previous_proof
    if previous_proof is None:
        assert private_input.previous_state is None
        # A new recursion starts at the target block
        origin_block_root = envelope.beacon_block_root
    else:
        assert proof_engine.verify_execution_proof(previous_proof)
        origin_block_root = previous_proof.origin_block_root

        # Authenticate the post-state of the parent proof's head block
        previous_state = private_input.previous_state
        assert previous_state is not None
        previous_header = previous_state.latest_block_header.copy()
        previous_header.state_root = hash_tree_root(previous_state)
        assert hash_tree_root(previous_header) == previous_proof.head_block_root

        # The payload proven by the parent is the last payload applied before
        # the target block, so every block between them was empty or missed
        previous_bid = previous_state.latest_execution_payload_bid
        assert state.latest_block_hash == previous_bid.block_hash

    # Gloas enforces these limits only in payload envelope gossip. The gossip
    # helper raises ``GossipReject``, which fails the proof like an assertion.
    verify_execution_requests_limits(envelope.execution_requests)
    assert len(envelope.payload.withdrawals) <= MAX_WITHDRAWALS_PER_PAYLOAD

    # Authenticate the target post-state against the envelope's block root, bind
    # the payload to the block, and validate it statelessly
    verify_execution_payload_envelope(state, signed_envelope, execution_engine)

    return PublicInput(
        origin_block_root=origin_block_root,
        head_block_root=envelope.beacon_block_root,
        chain_id=DEPOSIT_CHAIN_ID,
        schema_id=STATELESS_INPUT_SCHEMA_ID,
    )
```

Any failed assertion or raised exception fails the proof.

A guest program MUST fail the proof unless the parent proof's `proof_type` is
the program's own proof type or one of a fixed set of predecessor proof types
that the program accepts. The set is part of the program and changes only with a
new program and proof type.

## Execution engine

Inside the guest, the execution engine has no execution state. Its
`verify_and_notify_new_payload` validates the payload statelessly against the
execution witness, with the guarantees the `ExecutionEngine` specification
requires of that function. It MUST validate the payload under the chain ID
`DEPOSIT_CHAIN_ID` and the fork rules the guest implements, and MUST reject a
payload whose timestamp falls outside that fork. The guest MUST NOT take the
chain ID or the fork schedule from its private input.

Validation MUST be equivalent to the execution-specs
`verify_stateless_new_payload` applied to a `StatelessInput` built from the
request, the execution witness and `DEPOSIT_CHAIN_ID`.

## Separation of consensus and execution

An execution chain proof covers only the execution state transition: each
payload's execution and its binding to the beacon block that committed to it.
The consensus client executes the beacon state transition natively, including
for the blocks between the parent proof's head and the target. In particular,
`latest_block_hash` changes only when a block applies a full parent payload, and
every bid must build on it.

The guest checks that the parent proof's head payload is the target payload's
execution parent. It does not check that the parent proof's head block is a
beacon ancestor of the target block. The two differ only if another block
committed to the identical payload, whose execution is the same.

The guest does not prove data availability.
