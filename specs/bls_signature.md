# BLS signature verification

**Notice**: This document is a placeholder to facilitate the emergence of cross-client testnets. Substantive changes are postponed until [BLS standardisation](https://github.com/pairingwg/bls_standard) is finalized.

## Table of contents
<!-- TOC -->

- [BLS signature verification](#bls-signature-verification)
    - [Table of contents](#table-of-contents)
    - [Curve parameters](#curve-parameters)
    - [Ciphersuite](#ciphersuite)
    - [Point representations](#point-representations)
        - [G1 points](#g1-points)
        - [G2 points](#g2-points)
    - [Helpers](#helpers)
        - [`hash_to_G2`](#hash_to_G2)
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

## Ciphersuite

We use the following Ciphersuite `BLS_SIG_BLS12381G2-SHA256-SSWU-RO_POP_`.

Where:
* `POP` refers to proof of possession.
* `G2` refers to signatures on G2.
* `SHA256` is the hash function used.
* `SSWU` refers to the Simplified SWU Map from a finite field element to an elliptic curve point.
* `RO` refers to `hash-to-curve` function rather than `encode-to-curve`.
*  `BLS12381G2-SHA256-SSWU-RO` refers to the [hash to curve version 5](https://tools.ietf.org/html/draft-irtf-cfrg-hash-to-curve-05#section-8.9.2) ciphersuite.

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

`hash_to_g2` is equivaent `hash_to_curve` found in the [BLS standard](https://tools.ietf.org/html/draft-irtf-cfrg-hash-to-curve-05#section-3) with this interpretation reflecting draft version 5. We use the hash to curve ciphersuite `BLS12381G2-SHA256-SSWU-RO` found in section 8.9.2. It consists of three parts:

* `hash_to_base` - Converting a message from bytes to a field point found in [section 5.3](https://tools.ietf.org/html/draft-irtf-cfrg-hash-to-curve-05#section-5.3). The required constant parameters are:
  * Field Degree: `m = 2`
  * Length of HKDF: `L = 64`,
  * Hash Function: `H = SHA256`,
  * Domain Separation Tag: `DST = BLS_SIG_BLS12381G2-SHA256-SSWU-RO_POP_`.
* `map_to_curve` - Converting a field point to a point on the elliptic curve (G2 Point) in two steps:
  * First apply a [Simplified SWU Map](https://tools.ietf.org/html/draft-irtf-cfrg-hash-to-curve-05#section-6.6.3) to the [3-Isogney curve](https://tools.ietf.org/html/draft-irtf-cfrg-hash-to-curve-05#section-8.9.2) `E'`.
  * Second map the `E'` point to G2 using the `iso_map` detailed [here](https://tools.ietf.org/html/draft-irtf-cfrg-hash-to-curve-05#appendix-C.3).
* `clear_cofactor` - Ensure the point is in the correct subfield by multiplying by the curve co-efficient `h_eff` as found [here](https://tools.ietf.org/html/draft-irtf-cfrg-hash-to-curve-05#section-8.9.2).

Details of the `hash_to_curve` function are shown below.

```python
def hash_to_G2(alpha: Bytes) -> Tuple[uint384, uint384]:
   u0 = hash_to_base(alpha, 0)
   u1 = hash_to_base(alpha, 1)
   Q0 = map_to_curve(u0)
   Q1 = map_to_curve(u1)
   R = Q0 + Q1 # Point Addition
   P = clear_cofactor(R)
   return P
 ```

 An implementation of `hash_to_curve` can be found [here](https://github.com/kwantam/bls_sigs_ref/blob/93b58f3e9f9ef55085f9ad78c708fa5ad9b894df/python-impl/opt_swu_g2.py#L131).

## Aggregation operations

### `bls_aggregate_pubkeys`

Let `bls_aggregate_pubkeys(pubkeys: List[Bytes48]) -> Bytes48` return `pubkeys[0] + .... + pubkeys[len(pubkeys)-1]`, where `+` is the elliptic curve addition operation over the G1 curve. (When `len(pubkeys) == 0` the empty sum is the G1 point at infinity.)

### `bls_aggregate_signatures`

Let `bls_aggregate_signatures(signatures: List[Bytes96]) -> Bytes96` return `signatures[0] + .... + signatures[len(signatures)-1]`, where `+` is the elliptic curve addition operation over the G2 curve. (When `len(signatures) == 0` the empty sum is the G2 point at infinity.)

## Signature verification

In the following, `e` is the pairing function and `g` is the G1 generator with the following coordinates (see [here](https://github.com/zkcrypto/pairing/tree/master/src/bls12_381#g1)):

```python
g_x = 3685416753713387016781088315183077757961620795782546409894578378688607592378376318836054947676345821548104185464507
g_y = 1339506544944476473020471379941921221584933875938349620426543736416511423956333506472724655353366534992391756441569
g = Fq2([g_x, g_y])
```

### `bls_verify`

Let `bls_verify(pubkey: Bytes48, message_hash: Bytes32, signature: Bytes96, domain: Bytes8) -> bool`:

* Verify that `pubkey` is a valid G1 point.
* Verify that `signature` is a valid G2 point.
* Verify that `e(pubkey, hash_to_G2(message_hash, domain)) == e(g, signature)`.

### `bls_verify_multiple`

Let `bls_verify_multiple(pubkeys: List[Bytes48], message_hashes: List[Bytes32], signature: Bytes96, domain: Bytes8) -> bool`:

* Verify that each `pubkey` in `pubkeys` is a valid G1 point.
* Verify that `signature` is a valid G2 point.
* Verify that `len(pubkeys)` equals `len(message_hashes)` and denote the length `L`.
* Verify that `e(pubkeys[0], hash_to_G2(message_hashes[0], domain)) * ... * e(pubkeys[L-1], hash_to_G2(message_hashes[L-1], domain)) == e(g, signature)`.
