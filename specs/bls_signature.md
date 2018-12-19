# BLS signature verification

**Warning: This document is pending academic review and should not yet be considered secure.**

## Table of contents
<!-- TOC -->

- [BLS signature verification](#bls-signature-verification)
    - [Table of contents](#table-of-contents)
    - [Curve parameters](#curve-parameters)
    - [Point representations](#point-representations)
        - [G1 points](#g1-points)
        - [G2 points](#g2-points)
    - [Helpers](#helpers)
        - [`hash_to_G2`](#hash_to_g2)
        - [`modular_squareroot`](#modular_squareroot)
    - [Aggregation operations](#aggregation-operations)
        - [`bls_aggregate_pubkeys`](#bls_aggregate_pubkeys)
        - [`bls_aggregate_signatures`](#bls_aggregate_signatures)
    - [Signature verification](#signature-verification)
        - [`bls_verify`](#bls_verify)
        - [`bls_verify_multiple`](#bls_verify_multiple)

<!-- /TOC -->

## Curve parameters

The BLS12-381 curve parameters are defined [here](https://z.cash/blog/new-snark-curve).

## Point representations

We represent points in the groups G1 and G2 following [zkcrypto/pairing](https://github.com/zkcrypto/pairing/tree/master/src/bls12_381). We denote by `q` the field modulus and by `i` the imaginary unit.

### G1 points

A point in G1 is represented as a 384-bit integer `z` decomposed as a 381-bit integer `x` and three 1-bit flags in the top bits:

* `x = z % 2**381`
* `a_flag = (z % 2**382) // 2**381`
* `b_flag = (z % 2**383) // 2**382`
* `c_flag = (z % 2**384) // 2**383`

Respecting bit ordering, `z` is decomposed as `(c_flag, b_flag, a_flag, x)`.

We require:

* `x < q`
* `c_flag == 1`
* if `b_flag == 1` then `a_flag == x == 0` and `z` represents the point at infinity
* if `b_flag == 0` then `z` represents the point `(x, y)` where `y` is the valid coordinate such that `(y * 2) // q == a_flag`

### G2 points

A point in G2 is represented as a pair of 384-bit integers `(z1, z2)`. We decompose `z1` as above into `x1`, `a_flag1`, `b_flag1`, `c_flag1` and `z2` into `x2`, `a_flag2`, `b_flag2`, `c_flag2`.

We require:

* `x1 < q` and `x2 < q`
* `a_flag2 == b_flag2 == c_flag2 == 0`
* `c_flag1 == 1`
* if `b_flag1 == 1` then `a_flag1 == x1 == x2 == 0` and `(z1, z2)` represents the point at infinity
* if `b_flag1 == 0` then `(z1, z2)` represents the point `(x1 * i + x2, y)` where `y` is the valid coordinate such that the imaginary part `y_im` of `y` satisfies `(y_im * 2) // q == a_flag1`

## Helpers

### `hash_to_G2`

```python
G2_cofactor = 305502333931268344200999753193121504214466019254188142667664032982267604182971884026507427359259977847832272839041616661285803823378372096355777062779109
q = 4002409555221667393417789825735904156556882819939007885332058136124031650490837864442687629129015664037894272559787

def hash_to_G2(message: bytes32, domain: uint64) -> [uint384]:
    # Initial candidate x coordinate
    x_re = int.from_bytes(hash(bytes8(domain) + b'\x01' + message), 'big')
    x_im = int.from_bytes(hash(bytes8(domain) + b'\x02' + message), 'big')
    x_coordinate = Fq2([x_re, x_im])  # x = x_re + i * x_im
    
    # Test candidate y coordinates until a one is found
    while 1:
        y_coordinate_squared = x_coordinate ** 3 + Fq2([4, 4])  # The curve is y^2 = x^3 + 4(i + 1)
        y_coordinate = modular_squareroot(y_coordinate_squared)
        if y_coordinate is not None:  # Check if quadratic residue found
            return multiply_in_G2((x_coordinate, y_coordinate), G2_cofactor)
        x_coordinate += Fq2([1, 0])  # Add 1 and try again
```

### `modular_squareroot`

`modular_squareroot(x)` returns a solution `y` to `y**2 % q == x`, and `None` if none exists. If there are two solutions the one with higher imaginary component is favored; if both solutions have equal imaginary component the one with higher real component is favored.

```python
Fq2_order = q ** 2 - 1
eighth_roots_of_unity = [Fq2([1,1]) ** ((Fq2_order * k) // 8) for k in range(8)]

def modular_squareroot(value: int) -> int:
    candidate_squareroot = value ** ((Fq2_order + 8) // 16)
    check = candidate_squareroot ** 2 / value
    if check in eighth_roots_of_unity[::2]:
        x1 = candidate_squareroot / eighth_roots_of_unity[eighth_roots_of_unity.index(check) // 2]
        x2 = -x1
        return x1 if (x1.coeffs[1].n, x1.coeffs[0].n) > (x2.coeffs[1].n, x2.coeffs[0].n) else x2
    return None
```

## Aggregation operations

### `bls_aggregate_pubkeys`

Let `bls_aggregate_pubkeys(pubkeys: [uint384]) -> uint384` return `pubkeys[0] + .... + pubkeys[len(pubkeys)-1]`, where `+` is the elliptic curve addition operation over the G1 curve.

### `bls_aggregate_signatures`

Let `bls_aggregate_signatures(signatures: [[uint384]]) -> [uint384]` return `signatures[0] + .... + signatures[len(signatures)-1]`, where `+` is the elliptic curve addition operation over the G2 curve.

## Signature verification

In the following `e` is the pairing function and `g` is the G1 generator with the following coordinates (see [here](https://github.com/zkcrypto/pairing/tree/master/src/bls12_381#g1)):

```python
g_x = 3685416753713387016781088315183077757961620795782546409894578378688607592378376318836054947676345821548104185464507
g_y = 1339506544944476473020471379941921221584933875938349620426543736416511423956333506472724655353366534992391756441569
g = Fq2(g_x, g_y)
```

### `bls_verify`

Let `bls_verify(pubkey: uint384, message: bytes32, signature: [uint384], domain: uint64) -> bool`:

* Verify that `pubkey` is a valid G1 point.
* Verify that `signature` is a valid G2 point.
* Verify that `e(pubkey, hash_to_G2(message, domain)) == e(g, signature)`.

### `bls_verify_multiple`

Let `bls_verify_multiple(pubkeys: [uint384], messages: [bytes32], signature: [uint384], domain: uint64) -> bool`:

* Verify that each `pubkey` in `pubkeys` is a valid G1 point.
* Verify that `signature` is a valid G2 point.
* Verify that `len(pubkeys)` equals `len(messages)` and denote the length `L`.
* Verify that `e(pubkeys[0], hash_to_G2(messages[0], domain)) * ... * e(pubkeys[L-1], hash_to_G2(messages[L-1], domain)) == e(g, signature)`.
