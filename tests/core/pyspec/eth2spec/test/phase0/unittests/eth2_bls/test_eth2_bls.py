from eth2spec.test.context import with_all_phases, spec_state_test, always_bls
from eth2spec.phase0.spec import G1_INFINITY_POINT, G2_INFINITY_POINT


infinity_pubkey = G1_INFINITY_POINT
infinity_signature = G2_INFINITY_POINT
message = b'\x12' * 32


@with_all_phases
@spec_state_test
@always_bls
def test_eth2_verify(spec, state):

    # Valid in IETF BLS v3
    # TODO: will be invalid when we update it to v4
    assert spec.bls._Verify(infinity_pubkey, message, infinity_signature)
    # Valid in Eth2 spec
    assert spec.Eth2Verify(infinity_pubkey, message, infinity_signature)


@with_all_phases
@spec_state_test
@always_bls
def test_eth2_aggregate_verify(spec, state):
    pubkeys = [infinity_pubkey]
    signatures = [infinity_signature]
    for privkey in range(1, 3):
        pubkeys.append(spec.bls.SkToPk(privkey))
        signatures.append(spec.bls.Sign(privkey, message))
    signature = spec.bls.Aggregate(signatures)
    messages = [message] * 3

    # Valid in IETF BLS v3
    # TODO: will be invalid when we update it to v4
    assert spec.bls._AggregateVerify(pubkeys, messages, signature)
    # Valid in Eth2 spec
    assert spec.Eth2AggregateVerify(pubkeys, messages, signature)


@with_all_phases
@spec_state_test
@always_bls
def test_eth2_fast_aggregate_verify(spec, state):
    pubkeys = [infinity_pubkey]
    signatures = [infinity_signature]
    for privkey in range(1, 3):
        pubkeys.append(spec.bls.SkToPk(privkey))
        signatures.append(spec.bls.Sign(privkey, message))
    signature = spec.bls.Aggregate(signatures)

    # Valid in IETF BLS v3
    # TODO: check if it should be invalid in v4
    assert spec.bls._FastAggregateVerify(pubkeys, message, signature)
    # Valid in Eth2 spec
    assert spec.Eth2FastAggregateVerify(pubkeys, message, signature)
