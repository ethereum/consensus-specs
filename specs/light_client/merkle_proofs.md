# Merkle proof formats

**Notice**: This document is a work-in-progress for researchers and implementers.

## Table of contents
<!-- TOC -->

- [Merkle proof formats](#merkle-proof-formats)
   - [Table of contents](#table-of-contents)
   - [Constants](#constants)
   - [Generalized Merkle tree index](#generalized-merkle-tree-index)
   - [SSZ object to index](#ssz-object-to-index)
   - [Merkle multiproofs](#merkle-multiproofs)
   - [MerklePartial](#merklepartial)
       - [`SSZMerklePartial`](#sszmerklepartial)
       - [Proofs for execution](#proofs-for-execution)

<!-- /TOC -->

## Constants

| Name | Value |
| - | - |
| `LENGTH_FLAG` | `2**64 - 1` | 

## Generalized Merkle tree index

In a binary Merkle tree, we define a "generalized index" of a node as `2**depth + index`. Visually, this looks as follows:

```
    1
 2     3
4 5   6 7
   ...
```

Note that the generalized index has the convenient property that the two children of node `k` are `2k` and `2k+1`, and also that it equals the position of a node in the linear representation of the Merkle tree that's computed by this function:

```python
def merkle_tree(leaves: List[Bytes32]) -> List[Bytes32]:
    o = [0] * len(leaves) + leaves
    for i in range(len(leaves) - 1, 0, -1):
        o[i] = hash(o[i * 2] + o[i * 2 + 1])
    return o
```

We will define Merkle proofs in terms of generalized indices.

## SSZ object to index

We can describe the hash tree of any SSZ object, rooted in `hash_tree_root(object)`, as a binary Merkle tree whose depth may vary. For example, an object `{x: bytes32, y: List[uint64]}` would look as follows:

```
     root
    /    \
   x    y_root
        /    \
y_data_root  len(y)
    / \
   /\ /\
  .......
```

We can now define a concept of a "path", a way of describing a function that takes as input an SSZ object and outputs some specific (possibly deeply nested) member. For example, `foo -> foo.x` is a path, as are `foo -> len(foo.y)` and `foo -> foo.y[5].w`. We'll describe paths as lists, which can have two representations. In "human-readable form", they are `["x"]`, `["y", "__len__"]` and `["y", 5, "w"]` respectively. In "encoded form", they are lists of `uint64` values, in these cases (assuming the fields of `foo` in order are `x` then `y`, and `w` is the first field of `y[i]`) `[0]`, `[1, 2**64-1]`, `[1, 5, 0]`.

```python
def item_length(typ: Type) -> int:
    """
    Returns the number of bytes in a basic type, or 32 (a full hash) for compound types.
    """
    if typ == bool:
        return 1
    elif issubclass(typ, uint):
        return typ.byte_len
    else:
        return 32
        
        
def get_elem_type(typ: Type, index: int) -> Type:
    """
    Returns the type of the element of an object of the given type with the given index
    or member variable name (eg. `7` for `x[7]`, `"foo"` for `x.foo`)
    """
    return typ.get_fields_dict()[index] if is_container_type(typ) else typ.elem_type
        
        
def get_chunk_count(typ: Type) -> int:
    """
    Returns the number of hashes needed to represent the top-level elements in the given type
    (eg. `x.foo` or `x[7]` but not `x[7].bar` or `x.foo.baz`). In all cases except lists/vectors
    of basic types, this is simply the number of top-level elements, as each element gets one
    hash. For lists/vectors of basic types, it is often fewer because multiple basic elements
    can be packed into one 32-byte chunk.
    """
    if is_basic_type(typ):
        return 1
    elif issubclass(typ, (List, Vector, Bytes, BytesN)):
        return (typ.length * item_length(typ.elem_type) + 31) // 32
    else:
        return len(typ.get_fields())


def get_item_position(typ: Type, index: Union[int, str]) -> Tuple[int, int, int]:
    """
    Returns three variables: (i) the index of the chunk in which the given element of the item is
    represented, (ii) the starting byte position, (iii) the ending byte position. For example for
    a 6-item list of uint64 values, index=2 will return (0, 16, 24), index=5 will return (1, 8, 16)
    """
    if issubclass(typ, (List, Vector, Bytes, BytesN)):
        start = index * item_length(typ.elem_type)
        return start // 32, start % 32, start % 32 + item_length(typ.elem_type)
    elif is_container_type(typ):
        return typ.get_field_names().index(index), 0, item_length(get_elem_type(typ, index))
    else:
        raise Exception("Only lists/vectors/containers supported")


def get_generalized_index(typ: Type, path: List[Union[int, str]]) -> GeneralizedIndex:
    """
    Converts a path (eg. `[7, "foo", 3]` for `x[7].foo[3]`, `[12, "bar", "__len__"]` for
    `len(x[12].bar)`) into the generalized index representing its position in the Merkle tree.
    """
    for p in path:
        assert not is_basic_type(typ)  # If we descend to a basic type, the path cannot continue further
        if p == '__len__':
            typ, root = uint256, root * 2 + 1 if issubclass(typ, (List, Bytes)) else None
        else:
            pos, _, _ = get_item_position(typ, p)
            root = root * (2 if issubclass(typ, (List, Bytes)) else 1) * next_power_of_two(get_chunk_count(typ)) + pos
            typ = get_elem_type(typ, p)
    return root
```

### Helpers for generalized indices

#### `concat_generalized_indices`

```python
def concat_generalized_indices(*indices: Sequence[GeneralizedIndex]) -> GeneralizedIndex:
    """
    Given generalized indices i1 for A -> B, i2 for B -> C .... i_n for Y -> Z, returns
    the generalized index for A -> Z.
    """
    o = GeneralizedIndex(1)
    for i in indices:
        o = o * get_previous_power_of_2(i) + i
    return o
```

#### `get_generalized_index_length`

```python
def get_generalized_index_length(index: GeneralizedIndex) -> int:
   """
   Returns the length of a path represented by a generalized index.
   """
   return log(index)
```

#### `get_generalized_index_bit`

```python
def get_generalized_index_bit(index: GeneralizedIndex, bit: int) -> bool:
   """
   Returns the i'th bit of a generalized index.
   """
   return (index & (1 << bit)) > 0
```

## Merkle multiproofs

We define a Merkle multiproof as a minimal subset of nodes in a Merkle tree needed to fully authenticate that a set of nodes actually are part of a Merkle tree with some specified root, at a particular set of generalized indices. For example, here is the Merkle multiproof for positions 0, 1, 6 in an 8-node Merkle tree (i.e. generalized indices 8, 9, 14):

```
       .
   .       .
 .   *   *   .
x x . . . . x *
```

. are unused nodes, * are used nodes, x are the values we are trying to prove. Notice how despite being a multiproof for 3 values, it requires only 3 auxiliary nodes, only one node more than would be required to prove a single value. Normally the efficiency gains are not quite that extreme, but the savings relative to individual Merkle proofs are still significant. As a rule of thumb, a multiproof for k nodes at the same level of an n-node tree has size `k * (n/k + log(n/k))`.

First, we provide a method for computing the generalized indices of the auxiliary tree nodes that a proof of a given set of generalized indices will require:

```
def get_branch_indices(tree_index: int) -> List[int]:
    """
    Get the generalized indices of the sister chunks along the path from the chunk with the
    given tree index to the root.
    """
    o = [tree_index ^ 1]
    while o[-1] > 1:
        o.append((o[-1] // 2) ^ 1)
    return o[:-1]

def get_expanded_indices(indices: List[int]) -> List[int]:
    """
    Get the generalized indices of all chunks in the tree needed to prove the chunks with the given
    generalized indices.
    """
    branches = set()
    for index in indices:
        branches = branches.union(set(get_branch_indices(index) + [index]))
    return sorted(list([x for x in branches if x*2 not in branches or x*2+1 not in branches]))[::-1]
```

Generating a proof that covers paths `p1 ... pn` is simply a matter of taking the chunks in the SSZ hash tree with generalized indices `get_expanded_indices([p1 ... pn])`.

We now provide the bulk of the proving machinery, a function that takes a `{generalized_index: chunk}` map and fills in chunks that can be inferred (inferring the parent by hashing its two children):

```python
def fill(objects: Dict[int, Bytes32]) -> Dict[int, Bytes32]:
    """
    Fills in chunks that can be inferred from other chunks. For a set of chunks that constitutes
    a valid proof, this includes the root (generalized index 1).
    """
    objects = {k: v for k, v in objects.items()}
    keys = sorted(objects.keys())[::-1]
    pos = 0
    while pos < len(keys):
        k = keys[pos]
        if k in objects and k ^ 1 in objects and k // 2 not in objects:
            objects[k // 2] = hash(objects[k & - 2] + objects[k | 1])
            keys.append(k // 2)
        pos += 1
    # Completeness and consistency check
    assert 1 in objects
    for k in objects:
        if k > 1:
            assert objects[k // 2] == hash(objects[k & -2] + objects[k | 1])
    return objects
```

## MerklePartial

We define a container that encodes an SSZ partial, and provide the methods for converting it into a `{generalized_index: chunk}` map, for which we provide a method to extract individual values. To determine the hash tree root of an object represented by an SSZ partial, simply check `decode_ssz_partial(partial)[1]`.

### `SSZMerklePartial`

```python
class SSZMerklePartial(Container):
    indices: List[uint64, 2**32]
    chunks: List[Bytes32, 2**32]
```

### `decode_ssz_partial`

```python
def decode_ssz_partial(encoded: SSZMerklePartial) -> Dict[int, Bytes32]:
    """
    Decodes an encoded SSZ partial into a generalized index -> chunk map, and verify hash consistency.
    """
    full_indices = get_expanded_indices(encoded.indices)
    return fill({k:v for k,v in zip(full_indices, encoded.chunks)})
```

### `extract_value_at_path`

```python
def extract_value_at_path(chunks: Dict[int, Bytes32], typ: Type, path: List[Union[int, str]]) -> Any:
    """
    Provides the value of the element in the object represented by the given encoded SSZ partial at
    the given path. Returns a KeyError if that path is not covered by this SSZ partial.
    """
    root = 1
    for p in path:
        if p == '__len__':
            return deserialize_basic(chunks[root * 2 + 1][:8], uint64)
        if iissubclass(typ, (List, Bytes)):
            assert 0 <= p < deserialize_basic(chunks[root * 2 + 1][:8], uint64)
        pos, start, end = get_item_position(typ, p)
        root = root * (2 if issubclass(typ, (List, Bytes)) else 1) * next_power_of_two(get_chunk_count(typ)) + pos
        typ = get_elem_type(typ, p)
    return deserialize_basic(chunks[root][start: end], typ)
```

Here [link TBD] is a python implementation of SSZ partials that represents them as a class that can be read and written to just like the underlying objects, so you can eg. perform state transitions on SSZ partials and compute the resulting root
