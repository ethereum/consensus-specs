# Gossip validation tests

The aim of the gossip validation tests is to provide test coverage of the
validation rules for messages received via gossip topics.

<!-- mdformat-toc start --slug=github --no-anchors --maxlevel=6 --minlevel=2 -->

- [Test case format](#test-case-format)
  - [Directory structure](#directory-structure)
  - [`meta.yaml`](#metayaml)
  - [`state.ssz_snappy`](#statessz_snappy)
  - [Message files](#message-files)
- [Condition](#condition)
- [Expected results](#expected-results)

<!-- mdformat-toc end -->

## Test case format

### Directory structure

```
tests/gossip/<topic>/<test_name>/
├── meta.yaml
├── state.ssz_snappy
├── block_<32-byte-root>.ssz_snappy           # block file(s)
├── attestation_<32-byte-root>.ssz_snappy     # attestation file(s) (attestation topics)
└── aggregate_<32-byte-root>.ssz_snappy       # aggregate file(s) (aggregate topic)
```

### `meta.yaml`

```yaml
topic: string                -- The gossip topic name (e.g., "beacon_block", "beacon_attestation").
blocks: [{                   -- Optional. Blocks to import before validation (oldest to newest).
    block: string,           -- The block file (without extension).
    failed: bool,            -- Optional. If true, block failed validation (for testing descendant rejection).
}]
finalized_checkpoint:        -- Optional. Custom finalized checkpoint.
  epoch: int                 -- The epoch of the finalized checkpoint.
  root: string               -- Hex-encoded root (use this OR block, not both).
  block: string              -- Block file whose root to use (use this OR root, not both).
current_time_ms: int         -- The base time in milliseconds since genesis.
messages: [{                 -- List of messages to validate in sequence.
    offset_ms: int,          -- Time offset from current_time_ms when message is received.
    subnet_id: int,          -- Optional. The subnet ID.
    message: string,         -- The name of the message file (without extension).
    expected: string,        -- Expected result: "valid", "ignore", or "reject".
    reason: string,          -- Optional. The expected reason for ignore/reject.
}]
```

### `state.ssz_snappy`

An SSZ-snappy encoded `BeaconState`. This state provides:

- `genesis_time`: Used for time calculations.
- `finalized_checkpoint`: Used for finalization checks (unless overridden).
- Validator public keys: Used for signature verification.

### Message files

Message files are named with a prefix indicating their type and the 32-byte hash
tree root:

| Topic                        | File prefix          | SSZ type                  |
| ---------------------------- | -------------------- | ------------------------- |
| `beacon_block`               | `block_`             | `SignedBeaconBlock`       |
| `beacon_attestation`         | `attestation_`       | `Attestation`             |
| `beacon_aggregate_and_proof` | `aggregate_`         | `SignedAggregateAndProof` |
| `proposer_slashing`          | `proposer_slashing_` | `ProposerSlashing`        |
| `attester_slashing`          | `attester_slashing_` | `AttesterSlashing`        |
| `voluntary_exit`             | `voluntary_exit_`    | `SignedVoluntaryExit`     |

Block files (`block_<root>.ssz_snappy`) serve multiple purposes:

1. **Store blocks**: Referenced in the `blocks` list in `meta.yaml`.
2. **Messages**: Referenced by `message` in the messages list (for
   `beacon_block` topic).

## Condition

1. Deserialize `state.ssz_snappy` to get the beacon state.
2. Initialize a minimal store with:
   - `genesis_time` from the state.
   - `finalized_checkpoint` from the state (or `meta.finalized_checkpoint` if
     specified).
   - Import each entry in `blocks` into the store. If `failed: true`, track the
     block as having failed validation (for testing descendant rejection).
3. Iterate sequentially through `messages`:
   - Set `current_time_ms` to `meta.current_time_ms + message.offset_ms`.
   - Deserialize the message file based on the topic type.
   - Execute the appropriate validation function (e.g.,
     `validate_beacon_block_gossip` for the `beacon_block` topic).
   - Verify the result matches `expected`.
   - If the result is `valid`, update the store as the validation function would
     (e.g., add to `seen_proposer_slots`, track seen attestations).

## Expected results

| Result   | Description                            |
| -------- | -------------------------------------- |
| `valid`  | Message passes all validation checks.  |
| `ignore` | Message fails an `[IGNORE]` condition. |
| `reject` | Message fails a `[REJECT]` condition.  |
