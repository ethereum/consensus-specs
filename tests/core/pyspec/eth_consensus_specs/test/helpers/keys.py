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
