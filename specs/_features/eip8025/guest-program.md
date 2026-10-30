# EIP-8025 -- Guest Program

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

<!-- mdformat-toc end -->

## Introduction

This document defines the private input and the processing logic of the guest
program. Each run proves one execution payload and binds it to the beacon block
that committed to it.

The guest binds the payload to its beacon block with
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
    state: BeaconState
    envelope: ExecutionPayloadEnvelope
    execution_witness: Any
```

- `state` is the post-state of the target block, and `envelope` is the target
  block's payload envelope.
- `execution_witness` has the execution-specs type `ExecutionWitness`. The
  execution engine running in the guest is bound to it.

`state` is the step's beacon state witness. It is a post-block state, not
advanced by `process_slots`, so its `latest_block_header.state_root` is still
empty. Implementations SHOULD supply it as a partial SSZ tree whose root is the
full state root and in which only the fields read by the guest are expanded.
Reading a field that is not expanded MUST fail the proof.

## Guest processing

### New `verify_execution_transition`

```python
def verify_execution_transition(
    execution_engine: ExecutionEngine,
    private_input: PrivateInput,
) -> PublicInput:
    state = private_input.state
    envelope = private_input.envelope

    # Gloas enforces these limits only in payload envelope gossip. The gossip
    # helper raises ``GossipReject``, which fails the proof like an assertion.
    verify_execution_requests_limits(envelope.execution_requests)
    assert len(envelope.payload.withdrawals) <= MAX_WITHDRAWALS_PER_PAYLOAD

    # Authenticate the post-state against the envelope's block root, bind the
    # payload to the block, and validate it statelessly
    verify_execution_payload_envelope(state, envelope, execution_engine)

    return PublicInput(
        beacon_block_root=envelope.beacon_block_root,
        successful_validation=Boolean(True),
        chain_id=DEPOSIT_CHAIN_ID,
        schema_id=STATELESS_INPUT_SCHEMA_ID,
    )
```

Any failed assertion or raised exception fails the proof.

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
