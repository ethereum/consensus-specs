# Sync tests

It reuses the [fork choice test format](../fork_choice/README.md) to apply the
test script.

## Gloas and later

An `on_payload_info` step sets the execution engine's response for one
`block_hash`: to `engine_newPayload` for that payload and to
`engine_forkchoiceUpdated` with it as `headBlockHash`. A later step for the same
`block_hash` replaces it, and a `block_hash` without one gets `SYNCING`. An
envelope that gets `INVALID` is `valid: false`.

The client sends `engine_forkchoiceUpdated` on every head node change, even with
an unchanged `headBlockHash`, and applies the response before the next step. The
`headBlockHash` of a `full` head node is the block's payload, of an `empty` one
the payload the block builds on.

### `execution_payload_statuses` check

```yaml
execution_payload_statuses: [{
    block_hash: string,       -- Encoded 32-byte block hash of an imported payload
    status: string,           -- "VALID" | "NOT_VALIDATED" | "INVALIDATED"
}]
```

Every imported payload, in any order. `NOT_VALIDATED` means in
`opt_store.optimistic_payloads`, `INVALIDATED` moved from `NOT_VALIDATED` to
`INVALIDATED` or pruned with its removed nodes, and `VALID` neither. See
[Gloas optimistic sync](../../../specs/gloas/optimistic-sync.md).
