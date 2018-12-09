# BLS signature verification

**Warning: This document is pending academic review and should not yet be considered secure.**

## Table of contents
<!-- TOC -->

- [BLS signature verification](#bls-signature-verification)
    - [Table of contents](#table-of-contents)
    - [Point representations](#point-representations)
        - [G1 points](#g1-points)
        - [G2 points](#g2-points)
    - [Helpers](#helpers)
        - [`hash_to_G2`](#hash_to_g2)
        - [`modular_squareroot`](#modular_squareroot)
    - [Signature verification](#signature-verification)
        - [`bls_verify`](#bls_verify)
        - [`bls_verify_multiple`](#bls_verify_multiple)

<!-- /TOC -->

## Curve 

The BLS12-381 curve parameters are defined [here](https://z.cash/blog/new-snark-curve).

## Point representations

We represent points in the groups G1 and G2 following [zkcrypto/pairing](https://github.com/zkcrypto/pairing/tree/master/src/bls12_381). We denote by `q` the field modulus and by `i` the imaginary unit.

### G1 points

A point in G1 is represented as a 384-bit integer `z` decomposed as a 381-bit integer and three 1-bit flags:

* `x = z % 2**381`
* `a_flag = (z % 2**382) // 2**381`
* `b_flag = (z % 2**383) // 2**382`
* `c_flag = (z % 2**384) // 2**383`

We require:

* `x < q`
* `c_flag == 1`
* if `b_flag == 1` then `a_flag == x == 0` and `z` is the point at infinity
* if `b_flag == 0` then `z` is the point `(x, y)` where `y` is the valid coordinate such that `(y * 2) // q == a_flag`

### G2 points

A point in G2 is represented as a pair of 384-bit integers `(z1, z2)`. We decompose `z1` and `z2` as above into `x1`, `a_flag1`, `b_flag1`, `c_flag1` and `x2`, `a_flag2`, `b_flag2`, `c_flag2`.

We require:

* `x1 < q` and `x2 < q`
* `a_flag2 == b_flag2 == c_flag2 == 0`
* `c_flag1 == 1`
* if `b_flag1 == 1` then `a_flag1 == x1 == x2 == 0` and `(z1, z2)` is the point at infinity
* if `b_flag1 == 0` then `(z1, z2)` is the point `(x1 * i + x2, y)` where `y` is the valid coordinate such that the imaginary part `y_im` of `y` satisfies `(y_im * 2) // q == a_flag1`.

## Helpers

### `hash_to_G2`

```python
G2_cofactor = 305502333931268344200999753193121504214466019254188142667664032982267604182971884026507427359259977847832272839041616661285803823378372096355777062779109
q = 4002409555221667393417789825735904156556882819939007885332058136124031650490837864442687629129015664037894272559787

def hash_to_G2(message, domain):
    x1 = hash(bytes8(domain) + b'\x01' + message)
    x2 = hash(bytes8(domain) + b'\x02' + message)
    x_coordinate = FQ2([x1, x2]) # x1 + x2 * i
    while 1:
        x_cubed_plus_b2 = x_coordinate ** 3 + FQ2([4, 4])
        y_coordinate = modular_squareroot(x_cubed_plus_b2)
        if y_coordinate is not None:
            break
        x_coordinate += FQ2([1, 0]) # Add one until we get a quadratic residue
    assert is_on_curve((x_coordinate, y_coordinate))
    return multiply((x_coordinate, y_coordinate), G2_cofactor)
```

### `modular_squareroot`

```python
qmod = q ** 2 - 1
eighth_roots_of_unity = [FQ2([1,1]) ** ((qmod * k) // 8) for k in range(8)]

def modular_squareroot(value):
    candidate_squareroot = value ** ((qmod + 8) // 16)
    check = candidate_squareroot ** 2 / value
    if check in eighth_roots_of_unity[::2]:
        return candidate_squareroot / eighth_roots_of_unity[eighth_roots_of_unity.index(check) // 2]
    return None
```

## Signature verification

In the following `e` is the pairing function and `g` is the generator in G1.

### `bls_verify`

Let `bls_verify(pubkey: uint384, message: bytes32, signature: [uint384], domain: uint64) -> bool`:

* Verify that `pubkey` is a valid G1 point.
* Verify that `signature` is a valid G2 point.
* Verify that `e(pubkey, hash_to_G2(message, domain)) == e(g, signature)`.

### `bls_verify_multiple`

Let `BLSMultiVerify(pubkeys: [uint384], messages: [bytes32], signature: [uint384], domain: uint64) -> bool`:

* Verify that each `pubkey` in `pubkeys` is a valid G1 point.
* Verify that `signature` is a valid G2 point.
* Verify that `len(pubkeys)` equals `len(messages)` and denote the length `L`.
* Verify that `e(pubkeys[0], hash_to_G2(messages[0], domain)) * ... * e(pubkeys[L-1], hash_to_G2(messages[L-1], domain)) == e(g, signature)`.
