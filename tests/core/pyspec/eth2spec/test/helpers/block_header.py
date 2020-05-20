def sign_block_header(spec, state, header, privkey):
    # Either passing block or header would get the same signature
    signature = spec.get_block_signature(state, block=header, privkey=privkey)
    return spec.SignedBeaconBlockHeader(message=header, signature=signature)
