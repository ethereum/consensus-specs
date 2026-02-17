import milagro_bls_binding as milagro_bls
import pytest
from eth_utils import encode_hex

from eth_consensus_specs.test.context import only_generator, single_phase, spec_test, with_phases
from eth_consensus_specs.test.helpers.constants import ALTAIR
from eth_consensus_specs.utils import bls
from tests.infra.manifest import manifest
from tests.infra.template_test import template_test

from .constants import G1_POINT_AT_INFINITY, PRIVKEYS, ZERO_PUBKEY


def _run_eth_aggregate_pubkeys_valid(spec, pubkeys):
    aggregate_pubkey = spec.eth_aggregate_pubkeys(pubkeys)

    assert aggregate_pubkey == milagro_bls._AggregatePKs(pubkeys)

    yield (
        "data",
        "data",
        {
            "input": [encode_hex(pubkey) for pubkey in pubkeys],
            "output": (encode_hex(aggregate_pubkey)),
        },
    )


def _run_eth_aggregate_pubkeys_invalid(spec, pubkeys):
    with pytest.raises(Exception):
        spec.eth_aggregate_pubkeys(pubkeys)

    with pytest.raises(Exception):
        milagro_bls._AggregatePKs(pubkeys)

    yield (
        "data",
        "data",
        {
            "input": [encode_hex(pubkey) for pubkey in pubkeys],
            "output": (None),
        },
    )


@template_test
def _template_eth_aggregate_pubkeys_valid(privkey_index: int):
    privkey = PRIVKEYS[privkey_index]

    @manifest(preset_name="general", suite_name="bls")
    @only_generator("too slow")
    @with_phases([ALTAIR])
    @spec_test
    @single_phase
    def the_test(spec):
        yield from _run_eth_aggregate_pubkeys_valid(spec, [bls.SkToPk(privkey)])

    return (the_test, f"test_eth_aggregate_pubkeys_valid_{privkey_index}")


for privkey_index in range(len(PRIVKEYS)):
    _template_eth_aggregate_pubkeys_valid(privkey_index)


@manifest(preset_name="general", suite_name="bls")
@only_generator("too slow")
@with_phases([ALTAIR])
@spec_test
@single_phase
def test_eth_aggregate_pubkeys_valid_pubkeys(spec):
    pubkeys = [bls.SkToPk(privkey) for privkey in PRIVKEYS]
    yield from _run_eth_aggregate_pubkeys_valid(spec, pubkeys)


@manifest(preset_name="general", suite_name="bls")
@only_generator("too slow")
@with_phases([ALTAIR])
@spec_test
@single_phase
def test_eth_aggregate_pubkeys_empty_list(spec):
    yield from _run_eth_aggregate_pubkeys_invalid(spec, [])


@manifest(preset_name="general", suite_name="bls")
@only_generator("too slow")
@with_phases([ALTAIR])
@spec_test
@single_phase
def test_eth_aggregate_pubkeys_zero_pubkey(spec):
    yield from _run_eth_aggregate_pubkeys_invalid(spec, [ZERO_PUBKEY])


@manifest(preset_name="general", suite_name="bls")
@only_generator("too slow")
@with_phases([ALTAIR])
@spec_test
@single_phase
def test_eth_aggregate_pubkeys_infinity_pubkey(spec):
    yield from _run_eth_aggregate_pubkeys_invalid(spec, [G1_POINT_AT_INFINITY])


@manifest(preset_name="general", suite_name="bls")
@only_generator("too slow")
@with_phases([ALTAIR])
@spec_test
@single_phase
def test_eth_aggregate_pubkeys_x40_pubkey(spec):
    yield from _run_eth_aggregate_pubkeys_invalid(spec, [b"\x40" + b"\x00" * 47])
