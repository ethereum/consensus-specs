# Test format: SSZ static types

The goal of this type is to provide clients with a solid reference for how the
known SSZ objects should be encoded. Each object described in the Phase 0 spec
is covered. This is important, as many of the clients aiming to
serialize/deserialize objects directly into structs/classes do not support (or
have alternatives for) generic SSZ encoding/decoding.

This test-format ensures these direct serializations are covered.

Note that this test suite does not cover the invalid-encoding case: SSZ
implementations should be hardened against invalid inputs with the other SSZ
tests as guide, along with fuzzing.

## Test case format

Each SSZ type is a `handler`, since the format is semantically different: the
type of the data is different.

One can iterate over the handlers, and select the type based on the handler
name. Suites are then the same format, but each specialized in one randomization
mode. Some randomization modes may only produce a single test case (e.g. the
all-zeroes case).

The output parts are: `roots.yaml`, `serialized.ssz_snappy`, `value.yaml`

### `roots.yaml`

```yaml
root: bytes32         -- string, hash-tree-root of the value, hex encoded, with prefix 0x
```

### `serialized.ssz_snappy`

The SSZ-snappy encoded bytes.

### `value.yaml`

The same value as `serialized.ssz_snappy`, represented as YAML.

## Condition

A test-runner can implement the following assertions:

- If YAML decoding of SSZ objects is supported by the implementation:
  - Serialization: After parsing the `value`, SSZ-serialize it: the output
    should match `serialized`
  - Deserialization: SSZ-deserialize the `serialized` value, and see if it
    matches the parsed `value`
- If YAML decoding of SSZ objects is not supported by the implementation:
  - Serialization in 2 steps: deserialize `serialized`, then serialize the
    result, and verify if the bytes match the original `serialized`.
- Hash-tree-root: After parsing the `value` (or deserializing `serialized`),
  Hash-tree-root it: the output should match `root`

## References

**`serialized`**—[SSZ serialization](../../../ssz/simple-serialize.md#serialization)
**`root`**—[hash_tree_root](../../../ssz/simple-serialize.md#merkleization)
function
