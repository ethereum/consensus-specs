from py_ecc.bls import G2ProofOfPossession as bls

# Enough keys for 256 validators per slot in worst-case epoch length
privkeys = [i + 1 for i in range(32 * 256)]
pubkeys = [bls.SkToPk(privkey) for privkey in privkeys]
pubkey_to_privkey = {pubkey: privkey for privkey, pubkey in zip(privkeys, pubkeys)}

MAX_KEYS = 32 * 256
whisk_ks_initial = [i for i in range(MAX_KEYS)]
# Must be unique among the set `whisk_ks_initial + whisk_ks_final`
whisk_ks_final = [MAX_KEYS + i for i in range(MAX_KEYS)]

known_whisk_trackers = {}

def register_known_whisk_tracker(k_r_G: bytes, index: int):
    known_whisk_trackers[k_r_G] = index
