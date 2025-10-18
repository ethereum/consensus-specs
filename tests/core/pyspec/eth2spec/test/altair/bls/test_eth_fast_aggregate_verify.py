from eth_utils import encode_hex

from eth2spec.test.context import only_generator, single_phase, spec_test, with_phases
from eth2spec.test.helpers.constants import ALTAIR
from eth2spec.utils import bls
from tests.infra.manifest import manifest
from tests.infra.template_test import template_test

from .constants import (
    G1_POINT_AT_INFINITY,
    G2_POINT_AT_INFINITY,
    MESSAGES,
    PRIVKEYS,
    SAMPLE_MESSAGE,
    ZERO_SIGNATURE,
)


def _run_eth_fast_aggregate_verify(spec, pubkeys, message, aggregate_signature, expected_result):
    result = spec.eth_fast_aggregate_verify(pubkeys, message, aggregate_signature)

    assert result == expected_result

    yield (
        "data",
        "data",
        {
            "input": {
                "pubkeys": [encode_hex(pubkey) for pubkey in pubkeys],
                "message": encode_hex(message),
                "signature": encode_hex(aggregate_signature),
            },
            "output": result,
        },
    )


@template_test
def _template_eth_fast_aggregate_verify_valid(message_index: int):
    message = MESSAGES[message_index]
    privkeys = PRIVKEYS[: message_index + 1]

    @manifest(preset_name="general", suite_name="bls")
    @only_generator("too slow")
    @with_phases([ALTAIR])
    @spec_test
    @single_phase
    def the_test(spec):
        sigs = [bls.Sign(privkey, message) for privkey in privkeys]
        aggregate_signature = bls.Aggregate(sigs)
        pubkeys = [bls.SkToPk(privkey) for privkey in privkeys]
        yield from _run_eth_fast_aggregate_verify(
            spec, pubkeys, message, aggregate_signature, expected_result=True
        )

    return (the_test, f"test_eth_fast_aggregate_verify_valid_{message_index}")


for message_index in range(len(MESSAGES)):
    _template_eth_fast_aggregate_verify_valid(message_index)


@template_test
def _template_eth_fast_aggregate_verify_extra_pubkey(message_index: int):
    message = MESSAGES[message_index]
    privkeys = PRIVKEYS[: message_index + 1]

    @manifest(preset_name="general", suite_name="bls")
    @only_generator("too slow")
    @with_phases([ALTAIR])
    @spec_test
    @single_phase
    def the_test(spec):
        sigs = [bls.Sign(privkey, message) for privkey in privkeys]
        aggregate_signature = bls.Aggregate(sigs)
        # Add an extra pubkey to the end
        pubkeys = [bls.SkToPk(privkey) for privkey in privkeys] + [bls.SkToPk(PRIVKEYS[-1])]
        yield from _run_eth_fast_aggregate_verify(
            spec, pubkeys, message, aggregate_signature, expected_result=False
        )

    return (the_test, f"test_eth_fast_aggregate_verify_extra_pubkey_{message_index}")


for message_index in range(len(MESSAGES)):
    _template_eth_fast_aggregate_verify_extra_pubkey(message_index)


@template_test
def _template_eth_fast_aggregate_verify_tampered_signature(message_index: int):
    message = MESSAGES[message_index]
    privkeys = PRIVKEYS[: message_index + 1]

    @manifest(preset_name="general", suite_name="bls")
    @only_generator("too slow")
    @with_phases([ALTAIR])
    @spec_test
    @single_phase
    def the_test(spec):
        sigs = [bls.Sign(privkey, message) for privkey in privkeys]
        aggregate_signature = bls.Aggregate(sigs)
        pubkeys = [bls.SkToPk(privkey) for privkey in privkeys]
        # Tamper with the signature
        tampered_signature = aggregate_signature[:-4] + b"\xff\xff\xff\xff"
        yield from _run_eth_fast_aggregate_verify(
            spec, pubkeys, message, tampered_signature, expected_result=False
        )

    return (the_test, f"test_eth_fast_aggregate_verify_tampered_signature_{message_index}")


for message_index in range(len(MESSAGES)):
    _template_eth_fast_aggregate_verify_tampered_signature(message_index)


@manifest(preset_name="general", suite_name="bls")
@only_generator("too slow")
@with_phases([ALTAIR])
@spec_test
@single_phase
def test_eth_fast_aggregate_verify_na_pubkeys_and_infinity_signature(spec):
    # NOTE: Unlike `FastAggregateVerify`, len(pubkeys) == 0 and signature == G2_POINT_AT_INFINITY is VALID
    yield from _run_eth_fast_aggregate_verify(
        spec, [], MESSAGES[-1], G2_POINT_AT_INFINITY, expected_result=True
    )


@manifest(preset_name="general", suite_name="bls")
@only_generator("too slow")
@with_phases([ALTAIR])
@spec_test
@single_phase
def test_eth_fast_aggregate_verify_na_pubkeys_and_zero_signature(spec):
    yield from _run_eth_fast_aggregate_verify(
        spec, [], MESSAGES[-1], ZERO_SIGNATURE, expected_result=False
    )


@manifest(preset_name="general", suite_name="bls")
@only_generator("too slow")
@with_phases([ALTAIR])
@spec_test
@single_phase
def test_eth_fast_aggregate_verify_infinity_pubkey(spec):
    pubkeys = [bls.SkToPk(privkey) for privkey in PRIVKEYS]
    pubkeys_with_infinity = pubkeys + [G1_POINT_AT_INFINITY]
    signatures = [bls.Sign(privkey, SAMPLE_MESSAGE) for privkey in PRIVKEYS]
    aggregate_signature = bls.Aggregate(signatures)
    yield from _run_eth_fast_aggregate_verify(
        spec, pubkeys_with_infinity, SAMPLE_MESSAGE, aggregate_signature, expected_result=False
    )
