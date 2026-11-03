from eth_consensus_specs.test.helpers.forks import is_post_pq
from eth_consensus_specs.utils import bls, xmss

# Enough keys for 256 builders
builder_privkeys = [2**15 + i + 1 for i in range(256)]
builder_pubkeys = [bls.SkToPk(privkey) for privkey in builder_privkeys]
builder_pubkey_to_privkey = {
    pubkey: privkey for privkey, pubkey in zip(builder_privkeys, builder_pubkeys, strict=False)
}

# Enough keys for 256 validators per slot in worst-case epoch length
privkeys = [i + 1 for i in range(32 * 256 + 1)]
pubkeys = [bls.SkToPk(privkey) for privkey in privkeys]
pubkey_to_privkey = {pubkey: privkey for privkey, pubkey in zip(privkeys, pubkeys, strict=False)}

# XMSS key generation takes minutes, so the XMSS keys are placeholders
xmss_builder_pubkeys = [xmss.StubPk(privkey) for privkey in builder_privkeys]
builder_pubkey_to_privkey.update(zip(xmss_builder_pubkeys, builder_privkeys, strict=True))
xmss_pubkeys = [xmss.StubPk(privkey) for privkey in privkeys]
pubkey_to_privkey.update(zip(xmss_pubkeys, privkeys, strict=True))


def get_pubkeys(spec):
    """
    The validator public keys of ``spec``'s signature scheme.
    """
    return xmss_pubkeys if is_post_pq(spec) else pubkeys


def get_builder_pubkeys(spec):
    """
    The builder public keys of ``spec``'s signature scheme.
    """
    return xmss_builder_pubkeys if is_post_pq(spec) else builder_pubkeys


def get_filled_pubkey(spec, byte):
    """
    The public key of ``spec``'s signature scheme with every byte set to ``byte``.
    """
    if is_post_pq(spec):
        return spec.XMSSPubkey(byte * spec.XMSSPubkey.LENGTH)
    return spec.BLSPubkey(byte * spec.BLSPubkey.LENGTH)
