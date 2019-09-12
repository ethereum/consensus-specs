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

Every key generated via the key derivation process derives a child key via a set of intermediate Lamport keys. The idea behind the Lamport keys is to provide a quantum secure backup incase BLS12-381 is no longer deemed secure. At a high level, the key derivation process works by using the parent node's privkey as an entropy source for the Lamport privkeys which are then hashed together into a compressed Lamport public key, this public key is then hashed into BLS12-381's private key group.

### Helper functions

```python
def flip_bits(input: int) -> int:
    return input ^ (2**256 - 1)
```

```python
def seed_to_lamport_keys(seed: int, index: int) -> List[bytes]:
    combined_bytes = hkdf(master=seed.to_bytes(32, byteorder='big'),
                          salt=index.to_bytes(32, byteorder='big'), key_len=8160, hashmod=sha256)
    return [combined_bytes[i: i + 32] for i in range(255)]
```

```python
def parent_privkey_to_lamport_root(parent_key: int, index: int) -> bytes:
    lamport_0 = seed_to_lamport_keys(parent_key, index)
    lamport_1 = seed_to_lamport_keys(flip_bits(parent_key), index)
    lamport_privkeys = lamport_0 + lamport_1
    lamport_pubkeys = [sha256(sk) for sk in lamport_privkeys]
    return sha256(b''.join(lamport_pubkeys))
```

`hkdf_mod_r` is used to hash 32 random bytes into the field of the BLS12-381 private keys. It operates in the same way as the `KeyGen` function described in the [draft IETF BLS standard](https://github.com/cfrg/draft-irtf-cfrg-bls-signature/blob/master/draft-irtf-cfrg-bls-signature-00.txt) and therefore the private key obtained from `KeyGen` is equal to that obtained from `hkdf_mod_r` for the same seed bytes.

```python
def hkdf_mod_r(ikm: bytes) -> int:
    okm = hkdf(master=ikm, salt=b'BLS-SIG-KEYGEN-SALT-', key_len=48, hashmod=sha256)
    return int.from_bytes(okm, byteorder='big') % curve_order
```

### Master Key Derivation

The master key is the root of the key-tree and is derived from a 256-bit seed. While this seed can be any arbitrary 256 bits, it is intended to be the output of the seed derivation process described in the [mnemonic generation specification](./mnemonic.md).

```python
def derive_master_privkey(seed: bytes) -> int:
    seed = seed[:32]
    return derive_child_privkey(int.from_bytes(seed, byteorder='big'), 0)
```

### Child Key Derivation

The child key derivation function takes in the parent's private key and the index of the child and returns the child private key.

```python
def derive_child_privkey(parent_privkey: int, i: int) -> int:
    lamport_root = parent_privkey_to_lamport_root(parent_privkey, i)
    return hkdf_mod_r(lamport_root)
```
