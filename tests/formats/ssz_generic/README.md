# SSZ, generic tests

This set of test-suites provides general testing for SSZ: to decode any
container/list/vector/other type from binary data, encode it back, and compute
the hash-tree-root.

This test collection for general-purpose SSZ is experimental. The `ssz_static`
suite is the required minimal support for SSZ, and should be prioritized.

The `ssz_generic` tests are split up into different handler, each specialized
into a SSZ type:

- Vectors
  - [`basic_vector`](#basic_vector)
  - `complex_vector` *not supported yet*
- List
  - `basic_list` *not supported yet*
  - `complex_list` *not supported yet*
- ProgressiveList
  - [`basic_progressive_list`](#basic_progressive_list)
  - `complex_progressive_list` *not supported yet*
- Bitfields
  - [`bitvector`](#bitvector)
  - [`bitlist`](#bitlist)
- ProgressiveBitlist
  - [`progressive_bitlist`](#progressive_bitlist)
- Basic types
  - [`boolean`](#boolean)
  - [`uints`](#uints)
- Containers
  - [`containers`](#uints)
- ProgressiveContainer
  - [`progressive_containers`](#progressive_containers)
- CompatibleUnion
  - [`compatible_unions`](#compatible_uniosn)

## Format

For each type, a `valid` and an `invalid` suite is implemented. The cases have
the same format, but those in the `invalid` suite only declare a subset of the
data a test in the `valid` declares.

Each of the handlers encodes the SSZ type declaration in the file-name. See
[Type Declarations](#type-declarations).

### `valid`

Valid has 3 parts: `meta.yaml`, `serialized.ssz_snappy`, `value.yaml`

### `meta.yaml`

Valid ssz objects can have a hash-tree-root. The expected roots are encoded into
the metadata yaml:

```yaml
root: Bytes32             -- Hash-tree-root of the object
```

The `Bytes32` is encoded as a string, hexadecimal encoding, prefixed with `0x`.

### `serialized.ssz_snappy`

The serialized form of the object, as snappy-compressed SSZ bytes.

### `value.yaml`

The object, encoded as a YAML structure. Using the same familiar encoding as
YAML data in the other test suites.

### Conditions

The conditions are the same for each type:

- Encoding: After encoding the given `value` object, the output should match
  `serialized`.
- Decoding: After decoding the given `serialized` bytes, it should match the
  `value` object.
- Hash-tree-root: the root should match the root declared in the metadata.

## `invalid`

Test cases in the `invalid` suite only include the `serialized.ssz_snappy`

#### Condition

Unlike the `valid` suite, invalid encodings do not have any `value` or hash tree
root. The `serialized` data should simply not be decoded without raising an
error.

Note that for some type declarations in the invalid suite, the type itself may
technically be invalid. This is a valid way of detecting `invalid` data too.
E.g. a 0-length basic vector.

## Type declarations

Most types are not as static, and can reasonably be constructed during test
runtime from the test case name. Formats are listed below.

For each test case, an additional `_{extra...}` may be appended to the name,
where `{extra...}` contains a human readable indication of the test case
contents for debugging purposes.

### `basic_vector`

```
Template:

vec_{element type}_{length}

Data:

{element type}: bool, uint8, uint16, uint32, uint64, uint128, uint256

{length}: an unsigned integer
```

### `basic_progressive_list`

```
Template:

proglist_{element type}

Data:

{element type}: bool, uint8, uint16, uint32, uint64, uint128, uint256
```

### `bitlist`

```
Template:

bitlist_{limit}

Data:

{limit}: the list limit, in bits, of the bitlist. Does not include the length-delimiting bit in the serialized form.
```

### `bitvector`

```
Template:

bitvec_{length}

Data:

{length}: the length, in bits, of the bitvector.
```

### `progressive_bitlist`

```
Template:

progbitlist
```

### `boolean`

A boolean has no type variations. Instead, file names just plainly describe the
contents for debugging.

### `uints`

```
Template:

uint_{size}

Data:

{size}: the uint size: 8, 16, 32, 64, 128 or 256.
```

### `containers`

Containers are more complicated than the other types. Instead, a set of
pre-defined container structures is referenced.

```
Template:

{structure name}

Data:

{structure name}: Any of the structure names listed below (excluding the `(Container)` python super type)
```

```python
class SingleFieldTestStruct(Container):
    A: byte


class SmallTestStruct(Container):
    A: uint16
    B: uint16


class FixedTestStruct(Container):
    A: uint8
    B: uint64
    C: uint32


class VarTestStruct(Container):
    A: uint16
    B: List[uint16, 1024]
    C: uint8


class ComplexTestStruct(Container):
    A: uint16
    B: List[uint16, 128]
    C: uint8
    D: ByteList[256]
    E: VarTestStruct
    F: Vector[FixedTestStruct, 4]
    G: Vector[VarTestStruct, 2]


class ProgressiveTestStruct(Container):
    A: ProgressiveList[byte]
    B: ProgressiveList[uint64]
    C: ProgressiveList[SmallTestStruct]
    D: ProgressiveList[ProgressiveList[VarTestStruct]]


class BitsStruct(Container):
    A: Bitlist[5]
    B: Bitvector[2]
    C: Bitvector[1]
    D: Bitlist[6]
    E: Bitvector[8]


class ProgressiveBitsStruct(Container):
    A: Bitvector[256]
    B: Bitlist[256]
    C: ProgressiveBitlist
    D: Bitvector[257]
    E: Bitlist[257]
    F: ProgressiveBitlist
    G: Bitvector[1280]
    H: Bitlist[1280]
    I: ProgressiveBitlist
    J: Bitvector[1281]
    K: Bitlist[1281]
    L: ProgressiveBitlist
```

### `progressive_containers`

A set of pre-defined progressive container structures is referenced.
`SmallTestStruct` and `VarTestStruct` follow the definitions from the
[`containers`](#containers) section.

```
Template:

{structure name}

Data:

{structure name}: Any of the structure names listed below (excluding the `(ProgressiveContainer)` python super type)
```

```python
class ProgressiveSingleFieldContainerTestStruct(ProgressiveContainer(active_fields=[1])):
    A: byte


class ProgressiveSingleListContainerTestStruct(ProgressiveContainer(active_fields=[0, 0, 0, 0, 1])):
    C: ProgressiveBitlist


class ProgressiveVarTestStruct(ProgressiveContainer(active_fields=[1, 0, 1, 0, 1])):
    A: byte
    B: List[uint16, 123]
    C: ProgressiveBitlist


class ProgressiveComplexTestStruct(
    ProgressiveContainer(
        active_fields=[1, 0, 1, 0, 1, 0, 0, 0, 1, 0, 0, 0, 1, 1, 0, 0, 0, 0, 0, 0, 1, 1]
    )
):
    A: byte
    B: List[uint16, 123]
    C: ProgressiveBitlist
    D: ProgressiveList[uint64]
    E: ProgressiveList[SmallTestStruct]
    F: ProgressiveList[ProgressiveList[VarTestStruct]]
    G: List[ProgressiveSingleFieldContainerTestStruct, 10]
    H: ProgressiveList[ProgressiveVarTestStruct]
```

### `compatible_unions`

A set of pre-defined compatible union structures is referenced, combining
definitions from the other sections.

```
Template:

{structure name}

Data:

{structure name}: Any of the structure names listed below (excluding the `= CompatibleUnion` definition)
```

```python
CompatibleUnionA = CompatibleUnion({1: ProgressiveSingleFieldContainerTestStruct})

CompatibleUnionBC = CompatibleUnion(
    {2: ProgressiveSingleListContainerTestStruct, 3: ProgressiveVarTestStruct}
)

CompatibleUnionABCA = CompatibleUnion(
    {
        1: ProgressiveSingleFieldContainerTestStruct,
        2: ProgressiveSingleListContainerTestStruct,
        3: ProgressiveVarTestStruct,
        4: ProgressiveSingleFieldContainerTestStruct,
    }
)
```
