# Test format: config_spec

The `config` runner with the `spec` handler validates the beacon API
`/eth/v1/config/spec` endpoint.

The endpoint returns the union of all configuration, preset, and constant
values for a given network. These test vectors provide the expected key-value
pairs for each `(preset, fork)` combination so that client implementations can
verify their responses are correct and complete.

## Test case format

### `data.yaml`

A flat mapping of every key-value pair that the endpoint must return:

```yaml
SLOTS_PER_EPOCH: '32'
PTC_SIZE: '512'
DOMAIN_BEACON_PROPOSER: '0x00000000'
...
```

All values are strings. Numeric values are decimal strings. Byte values are
`0x`-prefixed hex strings.

## Condition

A client's `/eth/v1/config/spec` response must contain **at least** every key
present in `data.yaml`, and each value must match exactly.

Clients may return additional keys (e.g. client-specific extensions), but
every key in the fixture must be present with the correct value.
