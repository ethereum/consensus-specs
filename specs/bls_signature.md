# BLS signatures

## Table of contents
<!-- TOC -->

- [BLS signatures](#bls-signatures)
    - [Table of contents](#table-of-contents)
    - [Standards drafts](#standards-drafts)
    - [Point representations](#point-representations)
        - [G1 points](#g1-points)
        - [G2 points](#g2-points)
    - [Ciphersuite](#ciphersuite)
    - [Helpers](#helpers)
        - [`hash_to_G2`](#hash_to_g2)
    - [Aggregation operations](#aggregation-operations)
        - [`bls_aggregate_pubkeys`](#bls_aggregate_pubkeys)
        - [`bls_aggregate_signatures`](#bls_aggregate_signatures)
    - [Signature verification](#signature-verification)
        - [`bls_verify`](#bls_verify)
        - [`bls_verify_multiple`](#bls_verify_multiple)

<!-- /TOC -->

## Standards drafts

This specification follows three Internet Research Task Force (IRTF) Crypto Forum Research Group (CFRG) drafts:

* [`pairing-friendly-curves-00`](https://tools.ietf.org/html/draft-irtf-cfrg-pairing-friendly-curves-00) (published November 1, 2019)
* [`hash-to-curve-05`](https://tools.ietf.org/html/draft-irtf-cfrg-hash-to-curve-05) (published November 2, 2019)
* [`bls-signature-00`](https://tools.ietf.org/html/draft-irtf-cfrg-bls-signature-00) (published August 8, 2019)

Note that the above standards drafts are not ratified as Internet Engineering Task Force (IEFT) standards. Despite the lack of  IEFT standardization various blockchain projects are using the above drafts as the "de facto BLS standard for blockchains" to facilitate interoperability.

## Point representations

We represent points in the G1 and G2 groups following [zkcrypto/pairing](https://github.com/zkcrypto/pairing/tree/master/src/bls12_381). We denote by `q` the field modulus and by `i` the imaginary unit.

### G1 points

A G1 point is represented as a 384-bit integer `z` decomposed as a 381-bit integer `x` and three 1-bit flags in the top bits:

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

## Ciphersuite

We use the `BLS_SIG_BLS12381G2-SHA256-SSWU-RO-_POP_` ciphersuite where:

* `BLS_SIG_` refers to BLS signatures
* `BLS12381G2-SHA256-SSWU-RO-` is the hash to curve ciphersuite (see [hash-to-curve-05#section-8.9.2](https://tools.ietf.org/html/draft-irtf-cfrg-hash-to-curve-05#section-8.9.2)):
    * `BLS12381G2-` refers to the use of the BLS12-381 curve with signatures on G2
    * `SHA256-` refers to the use of SHA256 as the internal `hash_to_base` function
    * `SSWU-` refers to use of the simplified SWU mapping finite field elements to elliptic curve points
    * `RO-` refers to the hash to curve outputs being indifferentiable from a random oracle
* `_POP_` refers to the use proofs of possession to prevent rogue key attacks (see [bls-signature-00#section-4.2.3](https://tools.ietf.org/html/draft-irtf-cfrg-bls-signature-00#section-4.2.3))

## Helpers

### `hash_to_G2`

`hash_to_G2` is equivalent to `hash_to_curve` found in [hash-to-curve-05#section-3](https://tools.ietf.org/html/draft-irtf-cfrg-hash-to-curve-05#section-3). It is defined as

```python
def hash_to_G2(alpha: Bytes) -> Tuple[uint384, uint384]:
   u0 = hash_to_base(alpha, 0)
   u1 = hash_to_base(alpha, 1)
   Q0 = map_to_curve(u0)
   Q1 = map_to_curve(u1)
   R = Q0 + Q1 # point addition
   P = clear_cofactor(R)
   return P
 ```

* `hash_to_base` converts a message from bytes to a field point (see [hash-to-curve-05#section-5.3](https://tools.ietf.org/html/draft-irtf-cfrg-hash-to-curve-05#section-5.3)). The parameters are:
    * domain separation tag—`DST = BLS_SIG_BLS12381G2-SHA256-SSWU-RO-_POP_`
    * hash function—`H = SHA256`
    * field degree—`m = 2`
    * length of HKDF—`L = 64`
* `map_to_curve` converts a field point to a G2 point in two steps:
    1) it applies a simplified SWU map (see [hash-to-curve-05#section-6.6.3](https://tools.ietf.org/html/draft-irtf-cfrg-hash-to-curve-05#section-6.6.3)) to the 3-isogeny curve  `E'` (see [hash-to-curve-05#section-8.9.2](https://tools.ietf.org/html/draft-irtf-cfrg-hash-to-curve-05#section-8.9.2))
    2) it maps the point on `E'` to a G2 point using `iso_map` (see [hash-to-curve-05#appendix-C.3](https://tools.ietf.org/html/draft-irtf-cfrg-hash-to-curve-05#appendix-C.3))
* `clear_cofactor` ensures the point is in the correct subfield by multiplying by the curve coefficient `h_eff` (see [hash-to-curve-05#section-8.9.2](https://tools.ietf.org/html/draft-irtf-cfrg-hash-to-curve-05#section-8.9.2)).

An implementation of `hash_to_curve` can be found [here](https://github.com/kwantam/bls_sigs_ref/blob/93b58f3e9f9ef55085f9ad78c708fa5ad9b894df/python-impl/opt_swu_g2.py#L131).

## Aggregation operations

### `bls_aggregate_pubkeys`

Let `bls_aggregate_pubkeys(pubkeys: List[Bytes48]) -> Bytes48` return `pubkeys[0] + .... + pubkeys[len(pubkeys) - 1]`, where `+` is the elliptic curve addition operation over the G1 curve. (When `len(pubkeys) == 0` the empty sum is the G1 point at infinity.)

### `bls_aggregate_signatures`

Let `bls_aggregate_signatures(signatures: List[Bytes96]) -> Bytes96` return `signatures[0] + .... + signatures[len(signatures) - 1]`, where `+` is the elliptic curve addition operation over the G2 curve. (When `len(signatures) == 0` the empty sum is the G2 point at infinity.)

## Signature verification

In the following, `e` is the pairing function and `g` is the G1 generator with the following coordinates (see `x` and `y` in [pairing-friendly-curves-00#section-4.2.2](https://tools.ietf.org/html/draft-irtf-cfrg-pairing-friendly-curves-00#section-4.2.2)):

```python
g_x = 0x17f1d3a73197d7942695638c4fa9ac0fc3688c4f9774b905a14e3a3f171bac586c55e83ff97a1aeffb3af00adb22c6bb
g_y = 0x08b3f481e3aaa0f1a09e30ed741d8ae4fcf5e095d5d00af600db18cb2c04b3edd03cc744a2888ae40caa232946c5e7e1
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
* Verify that `e(pubkeys[0], hash_to_G2(message_hashes[0], domain)) * ... * e(pubkeys[L - 1], hash_to_G2(message_hashes[L - 1], domain)) == e(g, signature)`.
