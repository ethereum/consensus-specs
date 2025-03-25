# Merkle proof formats

## Table of contents

<!-- TOC -->
<!-- START doctoc generated TOC please keep comment here to allow auto update -->
<!-- DON'T EDIT THIS SECTION, INSTEAD RE-RUN doctoc TO UPDATE -->

- [Helper functions](#helper-functions)
- [Generalized Merkle tree index](#generalized-merkle-tree-index)
- [SSZ object to index](#ssz-object-to-index)
  - [Helpers for generalized indices](#helpers-for-generalized-indices)
    - [`concat_generalized_indices`](#concat_generalized_indices)
    - [`get_generalized_index_length`](#get_generalized_index_length)
    - [`get_generalized_index_bit`](#get_generalized_index_bit)
    - [`generalized_index_sibling`](#generalized_index_sibling)
    - [`generalized_index_child`](#generalized_index_child)
    - [`generalized_index_parent`](#generalized_index_parent)
- [Merkle multiproofs](#merkle-multiproofs)

<!-- END doctoc generated TOC please keep comment here to allow auto update -->
<!-- /TOC -->

## Helper functions

```python
def get_power_of_two_ceil(x: int) -> int:
    """
    Get the power of 2 for given input, or the closest higher power of 2 if the input is not a power of 2.
    Commonly used for "how many nodes do I need for a bottom tree layer fitting x elements?"
    Example: 0->1, 1->1, 2->2, 3->4, 4->4, 5->8, 6->8, 7->8, 8->8, 9->16.
    """
    if x <= 1:
        return 1
    elif x == 2:
        return 2
    else:
        return 2 * get_power_of_two_ceil((x + 1) // 2)
```

```python
def get_power_of_two_floor(x: int) -> int:
    """
    Get the power of 2 for given input, or the closest lower power of 2 if the input is not a power of 2.
    The zero case is a placeholder and not used for math with generalized indices.
    Commonly used for "what power of two makes up the root bit of the generalized index?"
    Example: 0->1, 1->1, 2->2, 3->2, 4->4, 5->4, 6->4, 7->4, 8->8, 9->8
    """
    if x <= 1:
        return 1
    if x == 2:
        return x
    else:
        return 2 * get_power_of_two_floor(x // 2)
```

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
def merkle_tree(leaves: Sequence[Bytes32]) -> Sequence[Bytes32]:
    """
    Return an array representing the tree nodes by generalized index:
    [0, 1, 2, 3, 4, 5, 6, 7], where each layer is a power of 2. The 0 index is ignored. The 1 index is the root.
    The result will be twice the size as the padded bottom layer for the input leaves.
    """
    bottom_length = get_power_of_two_ceil(len(leaves))
    o = (
        [Bytes32()] * bottom_length
        + list(leaves)
        + [Bytes32()] * (bottom_length - len(leaves))
    )
    for i in range(bottom_length - 1, 0, -1):
        o[i] = hash(o[i * 2] + o[i * 2 + 1])
    return o
```

We define a custom type `GeneralizedIndex` as a Python integer type in this document. It can be represented as a Bitvector/Bitlist object as well.

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

We can now define a concept of a "path", a way of describing a function that takes as input an SSZ object and outputs some specific (possibly deeply nested) member. For example, `foo -> foo.x` is a path, as are `foo -> len(foo.y)` and `foo -> foo.y[5].w`. We'll describe paths as lists, which can have two representations. In "human-readable form", they are `["x"]`, `["y", "__len__"]` and `["y", 5, "w"]` respectively. In "encoded form", they are lists of `uint64` values, in these cases (assuming the fields of `foo` in order are `x` then `y`, and `w` is the first field of `y[i]`) `[0]`, `[1, 2**64-1]`, `[1, 5, 0]`. We define `SSZVariableName` as the member variable name string, i.e., a path is presented as a sequence of integers and `SSZVariableName`.

```python
def item_length(typ: SSZType) -> int:
    """
    Return the number of bytes in a basic type, or 32 (a full hash) for compound types.
    """
    if issubclass(typ, BasicValue):
        return typ.byte_len
    else:
        return 32
```

```python
def get_elem_type(
    typ: Union[BaseBytes, BaseList, Container],
    index_or_variable_name: Union[int, SSZVariableName],
) -> SSZType:
    """
    Return the type of the element of an object of the given type with the given index
    or member variable name (eg. `7` for `x[7]`, `"foo"` for `x.foo`)
    """
    return (
        typ.get_fields()[index_or_variable_name]
        if issubclass(typ, Container)
        else typ.elem_type
    )
```

```python
def chunk_count(typ: SSZType) -> int:
    """
    Return the number of hashes needed to represent the top-level elements in the given type
    (eg. `x.foo` or `x[7]` but not `x[7].bar` or `x.foo.baz`). In all cases except lists/vectors
    of basic types, this is simply the number of top-level elements, as each element gets one
    hash. For lists/vectors of basic types, it is often fewer because multiple basic elements
    can be packed into one 32-byte chunk.
    """
    # typ.length describes the limit for list types, or the length for vector types.
    if issubclass(typ, BasicValue):
        return 1
    elif issubclass(typ, Bits):
        return (typ.length + 255) // 256
    elif issubclass(typ, Elements):
        return (typ.length * item_length(typ.elem_type) + 31) // 32
    elif issubclass(typ, Container):
        return len(typ.get_fields())
    else:
        raise Exception(f"Type not supported: {typ}")
```

```python
def get_item_position(
    typ: SSZType, index_or_variable_name: Union[int, SSZVariableName]
) -> Tuple[int, int, int]:
    """
    Return three variables:
        (i) the index of the chunk in which the given element of the item is represented;
        (ii) the starting byte position within the chunk;
        (iii) the ending byte position within the chunk.
    For example: for a 6-item list of uint64 values, index=2 will return (0, 16, 24), index=5 will return (1, 8, 16)
    """
    if issubclass(typ, Elements):
        index = int(index_or_variable_name)
        start = index * item_length(typ.elem_type)
        return start // 32, start % 32, start % 32 + item_length(typ.elem_type)
    elif issubclass(typ, Container):
        variable_name = index_or_variable_name
        return (
            typ.get_field_names().index(variable_name),
            0,
            item_length(get_elem_type(typ, variable_name)),
        )
    else:
        raise Exception("Only lists/vectors/containers supported")
```

```python
def get_generalized_index(
    typ: SSZType, *path: PyUnion[int, SSZVariableName]
) -> GeneralizedIndex:
    """
    Converts a path (eg. `[7, "foo", 3]` for `x[7].foo[3]`, `[12, "bar", "__len__"]` for
    `len(x[12].bar)`) into the generalized index representing its position in the Merkle tree.
    """
    root = GeneralizedIndex(1)
    for p in path:
        assert not issubclass(
            typ, BasicValue
        )  # If we descend to a basic type, the path cannot continue further
        if p == "__len__":
            assert issubclass(typ, (List, ByteList))
            typ = uint64
            root = GeneralizedIndex(root * 2 + 1)
        else:
            pos, _, _ = get_item_position(typ, p)
            base_index = (
                GeneralizedIndex(2)
                if issubclass(typ, (List, ByteList))
                else GeneralizedIndex(1)
            )
            root = GeneralizedIndex(
                root * base_index * get_power_of_two_ceil(chunk_count(typ)) + pos
            )
            typ = get_elem_type(typ, p)
    return root
```

### Helpers for generalized indices

_Usage note: functions outside this section should manipulate generalized indices using only functions inside this section. This is to make it easier for developers to implement generalized indices with underlying representations other than bigints._

#### `concat_generalized_indices`

```python
def concat_generalized_indices(*indices: GeneralizedIndex) -> GeneralizedIndex:
    """
    Given generalized indices i1 for A -> B, i2 for B -> C .... i_n for Y -> Z, returns
    the generalized index for A -> Z.
    """
    o = GeneralizedIndex(1)
    for i in indices:
        o = GeneralizedIndex(
            o * get_power_of_two_floor(i) + (i - get_power_of_two_floor(i))
        )
    return o
```

#### `get_generalized_index_length`

```python
def get_generalized_index_length(index: GeneralizedIndex) -> int:
    """
    Return the length of a path represented by a generalized index.
    """
    return int(log2(index))
```

#### `get_generalized_index_bit`

```python
def get_generalized_index_bit(index: GeneralizedIndex, position: int) -> bool:
    """
    Return the given bit of a generalized index.
    """
    return (index & (1 << position)) > 0
```

#### `generalized_index_sibling`

```python
def generalized_index_sibling(index: GeneralizedIndex) -> GeneralizedIndex:
    return GeneralizedIndex(index ^ 1)
```

#### `generalized_index_child`

```python
def generalized_index_child(
    index: GeneralizedIndex, right_side: bool
) -> GeneralizedIndex:
    return GeneralizedIndex(index * 2 + right_side)
```

#### `generalized_index_parent`

```python
def generalized_index_parent(index: GeneralizedIndex) -> GeneralizedIndex:
    return GeneralizedIndex(index // 2)
```

## Merkle multiproofs

We define a Merkle multiproof as a minimal subset of nodes in a Merkle tree needed to fully authenticate that a set of nodes actually are part of a Merkle tree with some specified root, at a particular set of generalized indices. For example, here is the Merkle multiproof for positions 0, 1, 6 in an 8-node Merkle tree (i.e. generalized indices 8, 9, 14):

```
       .
   .       .
 .   *   *   .
x x . . . . x *
```

. are unused nodes, * are used nodes, x are the values we are trying to prove. Notice how despite being a multiproof for 3 values, it requires only 3 auxiliary nodes, the same amount required to prove a single value. Normally the efficiency gains are not quite that extreme, but the savings relative to individual Merkle proofs are still significant. As a rule of thumb, a multiproof for k nodes at the same level of an n-node tree has size `k * (n/k + log(n/k))`.

First, we provide a method for computing the generalized indices of the auxiliary tree nodes that a proof of a given set of generalized indices will require:

```python
def get_branch_indices(tree_index: GeneralizedIndex) -> Sequence[GeneralizedIndex]:
    """
    Get the generalized indices of the sister chunks along the path from the chunk with the
    given tree index to the root.
    """
    o = [generalized_index_sibling(tree_index)]
    while o[-1] > 1:
        o.append(generalized_index_sibling(generalized_index_parent(o[-1])))
    return o[:-1]
```

```python
def get_path_indices(tree_index: GeneralizedIndex) -> Sequence[GeneralizedIndex]:
    """
    Get the generalized indices of the chunks along the path from the chunk with the
    given tree index to the root.
    """
    o = [tree_index]
    while o[-1] > 1:
        o.append(generalized_index_parent(o[-1]))
    return o[:-1]
```

```python
def get_helper_indices(
    indices: Sequence[GeneralizedIndex],
) -> Sequence[GeneralizedIndex]:
    """
    Get the generalized indices of all "extra" chunks in the tree needed to prove the chunks with the given
    generalized indices. Note that the decreasing order is chosen deliberately to ensure equivalence to the
    order of hashes in a regular single-item Merkle proof in the single-item case.
    """
    all_helper_indices: Set[GeneralizedIndex] = set()
    all_path_indices: Set[GeneralizedIndex] = set()
    for index in indices:
        all_helper_indices = all_helper_indices.union(set(get_branch_indices(index)))
        all_path_indices = all_path_indices.union(set(get_path_indices(index)))

    return sorted(all_helper_indices.difference(all_path_indices), reverse=True)
```

Now we provide the Merkle proof verification functions. First, for single item proofs:

```python
def calculate_merkle_root(
    leaf: Bytes32, proof: Sequence[Bytes32], index: GeneralizedIndex
) -> Root:
    assert len(proof) == get_generalized_index_length(index)
    for i, h in enumerate(proof):
        if get_generalized_index_bit(index, i):
            leaf = hash(h + leaf)
        else:
            leaf = hash(leaf + h)
    return leaf
```

```python
def verify_merkle_proof(
    leaf: Bytes32, proof: Sequence[Bytes32], index: GeneralizedIndex, root: Root
) -> bool:
    return calculate_merkle_root(leaf, proof, index) == root
```

Now for multi-item proofs:

```python
def calculate_multi_merkle_root(
    leaves: Sequence[Bytes32],
    proof: Sequence[Bytes32],
    indices: Sequence[GeneralizedIndex],
) -> Root:
    assert len(leaves) == len(indices)
    helper_indices = get_helper_indices(indices)
    assert len(proof) == len(helper_indices)
    objects = {
        **{index: node for index, node in zip(indices, leaves)},
        **{index: node for index, node in zip(helper_indices, proof)},
    }
    keys = sorted(objects.keys(), reverse=True)
    pos = 0
    while pos < len(keys):
        k = keys[pos]
        if k in objects and k ^ 1 in objects and k // 2 not in objects:
            objects[GeneralizedIndex(k // 2)] = hash(
                objects[GeneralizedIndex((k | 1) ^ 1)]
                + objects[GeneralizedIndex(k | 1)]
            )
            keys.append(GeneralizedIndex(k // 2))
        pos += 1
    return objects[GeneralizedIndex(1)]
```

```python
def verify_merkle_multiproof(
    leaves: Sequence[Bytes32],
    proof: Sequence[Bytes32],
    indices: Sequence[GeneralizedIndex],
    root: Root,
) -> bool:
    return calculate_multi_merkle_root(leaves, proof, indices) == root
```

Note that the single-item proof is a special case of a multi-item proof; a valid single-item proof verifies correctly when put into the multi-item verification function (making the natural trivial changes to input arguments, `index -> [index]` and `leaf -> [leaf]`). Note also that `calculate_merkle_root` and `calculate_multi_merkle_root` can be used independently to compute the new Merkle root of a proof with leaves updated.
