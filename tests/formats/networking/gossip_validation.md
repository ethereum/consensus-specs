# Gossip validation tests

The aim of the gossip validation tests is to provide test coverage of the
validation rules for messages received via gossip topics.

<!-- mdformat-toc start --slug=github --no-anchors --maxlevel=6 --minlevel=2 -->

- [Test case format](#test-case-format)
  - [`meta.yaml`](#metayaml)
  - [`state.ssz_snappy`](#statessz_snappy)
  - [Message files](#message-files)
- [Condition](#condition)
- [Expected results](#expected-results)

<!-- mdformat-toc end -->

## Test case format

### `meta.yaml`

```yaml
topic: string                -- The gossip topic name (e.g., "beacon_block", "blob_sidecar",
                             -- "data_column_sidecar", "partial_data_column_sidecar").
blocks: [{                   -- Optional. Blocks to import before validation (oldest to newest).
                             -- The first entry is the anchor block, consistent with
                             -- `state.ssz_snappy` (the anchor state); it initializes
                             -- the store and is not state-transitioned.
    block: string,           -- The block file (without extension).
    failed: bool,            -- Optional. If true, the block fails state transition.
                             -- Track it as seen but invalid, with no post-state
                             -- (for testing descendant rejection).
    pending: bool,           -- Optional. If true, the block has been seen but not
                             -- yet imported, e.g. it is queued for processing.
                             -- Track it as seen, with no post-state.
    payload_status: string,  -- Optional. Execution payload status for this block:
                             -- "VALID" | "INVALIDATED" | "NOT_VALIDATED".
                             -- Maps to the corresponding `PAYLOAD_STATUS_*` value
                             -- in the relevant specification.
    payload: string,         -- Optional. `SignedExecutionPayloadEnvelope` file for
                             -- this block. The envelope has been received and
                             -- verified, as recorded by `on_execution_payload_envelope`.
}]
finalized_checkpoint:        -- Optional. Custom finalized checkpoint. Use it wherever
                             -- validation consults finalization: the store's finalized
                             -- checkpoint and any state-based finalized checkpoint view
                             -- (e.g. builder activation).
  epoch: int                 -- The epoch of the finalized checkpoint.
  root: string               -- Hex-encoded root (use this OR block, not both).
  block: string              -- Block file whose root to use (use this OR root, not both).
seen_partial_data_column_headers: [{
                             -- Optional. Preload validated partial
                             -- data column headers into `seen`.
    block_root: string,      -- Hex-encoded partial message group root.
    header: string,          -- `PartialDataColumnHeader` file to cache.
}]
current_time_ms: int         -- The base time in milliseconds since genesis.
messages: [{                 -- List of messages to validate in sequence.
    offset_ms: int,          -- Time offset from current_time_ms when message is received.
    subnet_id: int,          -- Optional. The subnet ID for subnet-scoped topics.
    column_index: int,       -- Optional. The column index for
                             -- `partial_data_column_sidecar` vectors.
    group_id: string,        -- Optional. The `PartialDataColumnGroupID` file
                             -- (without extension) for
                             -- `partial_data_column_sidecar` vectors.
    message: string,         -- The name of the message file (without extension).
    expected: string,        -- Expected result: "valid", "ignore", or "reject".
    reason: string,          -- Optional. The expected reason for ignore/reject.
}]
```

### `state.ssz_snappy`

An SSZ-snappy encoded `BeaconState`: the anchor state on which the blocks in
`blocks` (if any) are replayed. It is consistent with the first block in
`blocks` (that block's `state_root` is this state's root). This state provides:

- The anchor for the fork choice store, from which per-block post-states are
  derived by importing the remaining blocks.
- `genesis_time`: Used for time calculations.
- `finalized_checkpoint`: Used for finalization checks (unless overridden).
- Validator public keys: Used for signature verification.

### Message files

Message files are named with a prefix indicating their type and the 32-byte hash
tree root:

| Topic                                   | File prefix                     | SSZ type                     |
| --------------------------------------- | ------------------------------- | ---------------------------- |
| `beacon_block`                          | `block_`                        | `SignedBeaconBlock`          |
| `beacon_attestation`                    | `attestation_`                  | `Attestation`                |
| `beacon_aggregate_and_proof`            | `aggregate_`                    | `SignedAggregateAndProof`    |
| `proposer_slashing`                     | `proposer_slashing_`            | `ProposerSlashing`           |
| `attester_slashing`                     | `attester_slashing_`            | `AttesterSlashing`           |
| `voluntary_exit`                        | `voluntary_exit_`               | `SignedVoluntaryExit`        |
| `sync_committee_contribution_and_proof` | `contribution_`                 | `SignedContributionAndProof` |
| `sync_committee`                        | `sync_committee_message_`       | `SyncCommitteeMessage`       |
| `bls_to_execution_change`               | `bls_to_execution_change_`      | `SignedBLSToExecutionChange` |
| `blob_sidecar`                          | `blob_sidecar_`                 | `BlobSidecar`                |
| `data_column_sidecar`                   | `data_column_sidecar_`          | `DataColumnSidecar`          |
| `partial_data_column_group_id`          | `partial_data_column_group_id_` | `PartialDataColumnGroupID`   |
| `partial_data_column_header`            | `partial_data_column_header_`   | `PartialDataColumnHeader`    |
| `partial_data_column_sidecar`           | `partial_data_column_sidecar_`  | `PartialDataColumnSidecar`   |

Block files (`block_<root>.ssz_snappy`) serve multiple purposes:

1. **Store blocks**: Referenced in the `blocks` list in `meta.yaml`.
2. **Messages**: Referenced by `message` in the messages list (for
   `beacon_block` topic).

## Condition

1. Deserialize `state.ssz_snappy` to get the anchor state.
2. Initialize the store from the anchor state and the first block in `blocks`
   (whose `state_root` matches the anchor state), as `get_forkchoice_store`
   would. Do not state-transition the anchor block. Then, for each subsequent
   entry in `blocks` (oldest to newest):
   - Import the block by applying the state transition to its parent's
     post-state, deriving the block's post-state.
     - If `failed: true`, the block fails state transition. Track it as seen but
       invalid: the block is known, but no post-state is available (for testing
       descendant rejection).
     - If `pending: true`, do not import the block. Track it as seen with no
       post-state available, as if it were queued for processing.
   - If `payload` is present, record the referenced envelope's message for that
     block as `on_execution_payload_envelope` would (e.g. add it to
     `store.payloads`).
   - If `payload_status` is present, track the execution payload status for that
     block.
     - `VALID`: the block's execution payload is known valid.
     - `INVALIDATED`: the block's execution payload is known invalid.
     - `NOT_VALIDATED`: the block's execution payload has not yet been
       validated.
     - For `beacon_block` gossip validation, `NOT_VALIDATED` represents the
       optimistic case where no valid/invalid payload result is yet available
       for the parent block.
3. If `meta.finalized_checkpoint` is specified, use it as the finalized
   checkpoint wherever validation consults finalization (in place of both the
   store's finalized checkpoint and any state-based finalized checkpoint view).
4. If `seen_partial_data_column_headers` is present, preload each referenced
   `PartialDataColumnHeader` into `seen.partial_data_column_headers` using its
   `block_root`.
5. Iterate sequentially through `messages`:
   - Set `current_time_ms` to `meta.current_time_ms + message.offset_ms`.
     `offset_ms` values are independent and need not be monotonic.
   - Deserialize the message file based on the topic type.
   - Execute the appropriate validation function, using the store built above
     and the head state derived from the imported blocks (advanced with empty
     slots to the current slot where required).
     - For subnet-scoped topics such as `beacon_attestation`, `blob_sidecar`,
       and `data_column_sidecar`, pass `message.subnet_id`.
     - For `partial_data_column_sidecar`, pass the `PartialDataColumnGroupID`
       referenced by `message.group_id` and `message.column_index`.
   - Verify the result matches `expected`.
   - If the result is `valid`, update the store as the validation function would
     (e.g., add to `seen_proposer_slots`, track seen attestations).

## Expected results

| Result   | Description                            |
| -------- | -------------------------------------- |
| `valid`  | Message passes all validation checks.  |
| `ignore` | Message fails an `[IGNORE]` condition. |
| `reject` | Message fails a `[REJECT]` condition.  |

Test cases are constructed so that every failing validation condition yields the
same expected result: clients may evaluate independent conditions in any order
without changing the outcome. Some conditions can only be evaluated after
another condition has passed (e.g. a check that reads a builder record requires
the builder index bounds check, and checks that use the parent block's state
require the parent to be known) -- such dependencies are always respected by the
vectors. The `reason` string reflects the specification's check order and is
informational.
