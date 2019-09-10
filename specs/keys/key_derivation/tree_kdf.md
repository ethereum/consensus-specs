# Tree Key Derivation Function

The tree KDF describes how to take a parent key and a child-leaf index and arrive at a child key. This is very useful as one can start with a single source of entropy and from there build out a practically unlimited number of keys. The specification can be broken into two sub-components: generating the master key, and constructing a child key from its parent. The master key is used as the root of the tree and then the tree is built in layers on top of this root.

## The Tree Structure

The key tree is defined purely through the relationship between a child-node and its ancestors. Starting with the root of the tree, the *master key*, a child node can be derived by knowing the parent's private key and the index of the child. The tree is broken up into depths which are indicated by `/` and the master node is described as `m`. The first child of the master node is therefore described as `m / 0`.

```text
      [m / 0] - [m / 0 / 0]
     /        \
    /           [m / 0 / 1]
[m] - [m / 1]
    \
     ...
      [m / i]
```

## Specification

### Helper functions

`hkdf_mod_r` is the core of this tree KDF specification. It operates in the same way as the `KeyGen` function described in the [draft IETF BLS standard](https://github.com/cfrg/draft-irtf-cfrg-bls-signature/blob/master/draft-irtf-cfrg-bls-signature-00.txt) and therefore the private key obtained from `KeyGen` is equal to that obtained from `hkdf_mod_r` for the same seed bytes.

```python
def hkdf_mod_r(ikm: bytes) -> int:
    okm = hkdf(master=ikm, salt="BLS-SIG-KEYGEN-SALT-", key_len=48, hashmod=sha256)
    return int.from_bytes(okm, byteorder='big') % curve_order
```

```python
def flip_bits(input: int) -> bytes:
    return = input ^ (2**256 - 1)
```

```python
def seed_to_lamport_keys(seed: int, index: int) -> List[bytes]:
    combined_bytes = hkdf(master=seed.to_bytes(32, byteorder='big'),
                          salt=index.to_bytes(32, byteorder='big'), key_len=8160, hashmod=sha256)
    return [combined_bytes[i: i + 32] for i in range(31)]
```

```python
def parent_privkey_to_lamport_root(parent_key: int, index: int) -> bytes:
    lamport_0 = seed_to_lamport_keys(parent_key, index)
    lamport_1 = seed_to_lamport_keys(flip_bits(parent_key), index)
    merkle_leaves = lamport_0 + [b'x\00' * 32] + lamport_1 + [b'x\00' * 32]
    return merkle_root(merkle_leaves)
```

### Master Key Derivation

The master key is the root of the key-tree and is derived from a 256-bit seed. While this seed can be any arbitrary 256 bits, it is intended to be the output of the seed derivation process described in the [mnemonic generation specification](./mnemonic.md).

```python
def derive_master_privkey(seed: bytes) -> int:
    return derive_child_privkey(int.from_bytes(seed, byteorder='big'), 0)
```

### Child Key Derivation

The child key derivation function takes in the parent's private key and the index of the child and returns the child private key.

```python
def derive_child_privkey(parent_privkey: int, i: int) -> int:
    lamport_root = parent_privkey_to_lamport_root(parent_privkey, i)
    return hkdf_mod_r(lamport_root)
```
