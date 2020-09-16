from eth2spec.test.context import with_all_phases, spec_state_test, always_bls
from eth2spec.phase0.spec import G1_INFINITY_POINT, G2_INFINITY_POINT


infinity_pubkey = G1_INFINITY_POINT
infinity_signature = G2_INFINITY_POINT
message = b'\x12' * 32


@with_all_phases
@spec_state_test
@always_bls
def test_eth2_verify_point_at_infinity(spec, state):
    # Valid in IETF BLS v3
    # TODO: will be invalid when we update it to v4
    assert spec.ietf._Verify(infinity_pubkey, message, infinity_signature)
    # Valid in Eth2 spec
    assert spec.bls_verify(infinity_pubkey, message, infinity_signature)


@with_all_phases
@spec_state_test
@always_bls
def test_eth2_aggregate_verify_point_at_infinity(spec, state):
    pubkeys = [infinity_pubkey]
    signatures = [infinity_signature]
    for privkey in range(1, 3):
        pubkeys.append(spec.ietf.SkToPk(privkey))
        signatures.append(spec.ietf.Sign(privkey, message))
    signature = spec.ietf.Aggregate(signatures)
    messages = [message] * 3

    # Valid in IETF BLS v3
    # TODO: will be invalid when we update it to v4
    assert spec.ietf._AggregateVerify(pubkeys, messages, signature)
    # Valid in Eth2 spec
    assert spec.bls_aggregate_verify(pubkeys, messages, signature)


@with_all_phases
@spec_state_test
@always_bls
def test_eth2_aggregate_verify_no_signature(spec, state):
    # Invalid in IETF BLS v3
    assert not spec.ietf._AggregateVerify([], [], infinity_signature)
    # Valid in Eth2 spec
    assert spec.bls_aggregate_verify([], [], infinity_signature)


@with_all_phases
@spec_state_test
@always_bls
def test_eth2_fast_aggregate_verify_point_at_infinity(spec, state):
    pubkeys = [infinity_pubkey]
    signatures = [infinity_signature]
    for privkey in range(1, 3):
        pubkeys.append(spec.ietf.SkToPk(privkey))
        signatures.append(spec.ietf.Sign(privkey, message))
    signature = spec.ietf.Aggregate(signatures)

    # Valid in IETF BLS v3
    # TODO: check if it should be invalid in v4
    assert spec.ietf._FastAggregateVerify(pubkeys, message, signature)
    # Valid in Eth2 spec
    assert spec.bls_fast_aggregate_verify(pubkeys, message, signature)
