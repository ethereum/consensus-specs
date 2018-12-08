### BLS Verification

**Warning: This document is pending academic review and should not yet be considered secure.**

See https://z.cash/blog/new-snark-curve/ for BLS-12-381 parameters. `q` is the field modulus.

We represent coordinates as defined in https://github.com/zkcrypto/pairing/tree/master/src/bls12_381/.

Specifically, a point in G1 as a 384-bit integer `z`, which we decompose into:

* `x = z % 2**381` (must be `< q`)
* `highflag = z // 2**382`
* `lowflag = (z % 2**382) // 2**381`

If `highflag == 3`, the point is the point at infinity and we require `lowflag = x = 0`. Otherwise, we require `highflag == 2`, in which case the point is `(x, y)` where `y` is the valid coordinate such that `(y * 2) // q == lowflag`.

We represent a point in G2 as a pair of 384-bit integers `(z1, z2)` that are each decomposed into `x1`, `highflag1`, `lowflag1`, `x2`, `highflag2`, `lowflag2` as above, where `x1` and `x2` must both be `< q`. We require `lowflag2 == highflag2 == 0`. If `highflag1 == 3`, the point is the point at infinity and we require `lowflag1 == x1 == x2 == 0`. Otherwise, we require `highflag == 2`, in which case the point is `(x1 * i + x2, y)` where `y` is the valid coordinate such that the imaginary part of `y` satisfies `(y_im * 2) // q == lowflag1`.

`BLSVerify(pubkey: uint384, msg: bytes32, sig: [uint384], domain: uint64)` is done as follows:

* Verify that `pubkey` is a valid G1 point and `sig` is a valid G2 point.
* Convert `msg` to a G2 point using `hash_to_G2` defined below.
* Do the pairing check: verify `e(pubkey, hash_to_G2(msg, domain)) == e(G1, sig)` (where `e` is the BLS pairing function)

Here is the `hash_to_G2` definition:

```python
G2_cofactor = 305502333931268344200999753193121504214466019254188142667664032982267604182971884026507427359259977847832272839041616661285803823378372096355777062779109
field_modulus = 4002409555221667393417789825735904156556882819939007885332058136124031650490837864442687629129015664037894272559787

def hash_to_G2(m, domain):
    x1 = hash(bytes8(domain) + b'\x01' + m)
    x2 = hash(bytes8(domain) + b'\x02' + m)
    x_coord = FQ2([x1, x2]) # x1 + x2 * i
    while 1:
        x_cubed_plus_b2 = x_coord ** 3 + FQ2([4,4])
        y_coord = mod_sqrt(x_cubed_plus_b2)
        if y_coord is not None:
            break
        x_coord += FQ2([1, 0]) # Add one until we get a quadratic residue
    assert is_on_curve((x_coord, y_coord))
    return multiply((x_coord, y_coord), G2_cofactor)
```

Here is a sample implementation of `mod_sqrt`:

```python
qmod = field_modulus ** 2 - 1
eighth_roots_of_unity = [FQ2([1,1]) ** ((qmod * k) // 8) for k in range(8)]

def mod_sqrt(val):
    candidate_sqrt = val ** ((qmod + 8) // 16)
    check = candidate_sqrt ** 2 / val
    if check in eighth_roots_of_unity[::2]:
        return candidate_sqrt / eighth_roots_of_unity[eighth_roots_of_unity.index(check) // 2]
    return None
```

`BLSMultiVerify(pubkeys: [uint384], msgs: [bytes32], sig: [uint384], domain: uint64)` is done as follows:

* Verify that each element of `pubkeys` is a valid G1 point and `sig` is a valid G2 point.
* Convert each element of `msg` to a G2 point using `hash_to_G2` defined above, using the specified `domain`.
* Check that the length of `pubkeys` and `msgs` is the same, call the length `L`
* Do the pairing check: verify `e(pubkeys[0], hash_to_G2(msgs[0], domain)) * ... * e(pubkeys[L-1], hash_to_G2(msgs[L-1], domain)) == e(G1, sig)`
