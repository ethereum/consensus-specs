from eth_consensus_specs.test.helpers.signatures import sign


def sign_block_header(spec, state, header, privkey):
    domain = spec.get_domain(
        state=state,
        domain_type=spec.DOMAIN_BEACON_PROPOSER,
    )
    signing_root = spec.compute_signing_root(header, domain)
    signature = sign(spec, privkey, signing_root, header.slot, "LEAF_OFFSET_BEACON_PROPOSER")
    return spec.SignedBeaconBlockHeader(message=header, signature=signature)
