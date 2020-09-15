from eth2spec.test.context import with_all_phases, spec_state_test


@with_all_phases
@spec_state_test
def test_eth2_verify(spec, state):
    PK = spec.G1_INFINATY_POINT
    signature = spec.G2_INFINATY_POINT
    message = b'hello'

    # Valid in IETF BLS v3
    # TODO: will be invalid when we update it to v4
    assert spec.bls._Verify(PK, message, signature)
    # Valid in Eth2 spec
    assert spec.Eth2Verify(PK, message, signature)
