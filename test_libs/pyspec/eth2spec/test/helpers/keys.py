from py_ecc import bls
from eth2spec.phase0 import spec

privkeys = [i + 1 for i in range(spec.SHARD_COUNT * 8)]
pubkeys = [bls.privtopub(privkey) for privkey in privkeys]
pubkey_to_privkey = {pubkey: privkey for privkey, pubkey in zip(privkeys, pubkeys)}
