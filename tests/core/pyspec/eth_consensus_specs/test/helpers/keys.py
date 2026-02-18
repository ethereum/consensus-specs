from py_ecc.bls import G2ProofOfPossession as bls

# Enough keys for 256 builders
builder_privkeys = [2**15 + i + 1 for i in range(256)]
builder_pubkeys = [bls.SkToPk(privkey) for privkey in builder_privkeys]
builder_pubkey_to_privkey = {
    pubkey: privkey for privkey, pubkey in zip(builder_privkeys, builder_pubkeys)
}

# Enough keys for 256 validators per slot in worst-case epoch length
privkeys = [i + 1 for i in range(32 * 256)]
pubkeys = [bls.SkToPk(privkey) for privkey in privkeys]
pubkey_to_privkey = {pubkey: privkey for privkey, pubkey in zip(privkeys, pubkeys)}

known_whisk_trackers = {}


def register_known_whisk_tracker(k_r_G: bytes, index: int):
    known_whisk_trackers[k_r_G] = index


def whisk_ks_initial(i: int):
    return i


# Must be unique among the set `whisk_ks_initial + whisk_ks_final`
def whisk_ks_final(i: int):
    return i + 10000000
