# Sync tests

It reuses the [fork choice test format](../fork_choice/README.md) to apply the
test script.

## Gloas and later

The execution engine judges execution payloads, which arrive in
`on_execution_payload_envelope` steps. An `on_payload_info` step sets the
response for one `block_hash`, both to `engine_newPayload` for that payload and
to `engine_forkchoiceUpdated` with that `headBlockHash`. A later
`on_payload_info` step for the same `block_hash` replaces the response.

An envelope whose `engine_newPayload` response is `INVALID` is rejected, so its
step is `valid: false`. An envelope that builds on an `INVALIDATED` payload is
rejected whatever the execution engine responds. A block that extends a node
removed from fork choice is rejected.

The client sends `engine_forkchoiceUpdated` whenever its head node changes, even
if `headBlockHash` stays the same, and applies the response before the next
step. For a `full` head node the `headBlockHash` is the block's own payload. For
an `empty` head node it is the payload the block builds on. A `headBlockHash`
with no `on_payload_info` gets `SYNCING`.

### `execution_payload_statuses` check

```yaml
execution_payload_statuses: [{
    block_hash: string,       -- Encoded 32-byte block hash of an imported payload
    status: string,           -- "VALID" | "NOT_VALIDATED" | "INVALIDATED"
}]
```

The list holds every payload whose envelope fork choice imported, in any order.
`NOT_VALIDATED` means the payload is in `opt_store.optimistic_payloads`,
`INVALIDATED` that it transitioned from `NOT_VALIDATED` to `INVALIDATED`, and
`VALID` neither. A payload the client pruned with its removed nodes counts as
`INVALIDATED`. See
[Gloas optimistic sync](../../../specs/gloas/optimistic-sync.md).
