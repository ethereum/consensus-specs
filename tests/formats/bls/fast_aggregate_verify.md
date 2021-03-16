# Test format: BLS sign message

Verify the signature against the given pubkeys and one message.

## Test case format

### `meta.yaml`

```yaml
release_version: string  -- required, the pyspec release version.
```

### `data.yaml`

```yaml
input:
  pubkeys: List[bytes48] -- the pubkey
  message: bytes32 -- the message
  signature: bytes96 -- the signature to verify against pubkeys and message
output: bool  -- VALID or INVALID
```

All byte(s) fields are encoded as strings, hexadecimal encoding, prefixed with `0x`.
