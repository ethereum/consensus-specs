from typing import Tuple

from eth2spec.debug.encode import encode
from eth2spec.phase0 import spec
from eth2spec.phase0.state_transition import (
    state_transition_to,
    process_block
)
from eth2spec.utils.merkle_minimal import get_merkle_root
from eth_utils import (
    to_dict, to_tuple
)
from gen_base import gen_suite, gen_typing
from preset_loader import loader
from tests import helpers

import genesis
import keys
import eth2spec.utils.bls_stub as bls


def create_genesis_state(initial_validator_count: int) -> spec.BeaconState:
    genesis_deposits = genesis.create_deposits(
        keys.pubkeys[:initial_validator_count],
        keys.withdrawal_creds[:initial_validator_count]
    )
    state = genesis.create_genesis_state(genesis_deposits)
    deposit_data_leaves = [dep.data.hash_tree_root() for dep in genesis_deposits]
    state.latest_eth1_data.deposit_root = get_merkle_root(tuple(deposit_data_leaves))
    state.latest_eth1_data.deposit_count = len(deposit_data_leaves)

    return state


def build_simple_state_and_attestation(validators_number: int) -> Tuple[spec.Attestation, spec.BeaconState]:
    state = create_genesis_state(validators_number)
    attestation_slot = spec.Slot(state.slot + 1)
    slot = spec.Slot(state.slot + spec.MIN_ATTESTATION_INCLUSION_DELAY + 1)
    state_transition_to(state, slot)
    attestation = get_valid_attestation(state, keys.privkeys, attestation_slot)
    return attestation, state


def build_justified_state(validators_number: int, slots: int) -> spec.BeaconState:
    state = create_genesis_state(validators_number)
    return update_justified_state_with_slots(state, slots)


def update_justified_state_with_slots(state: spec.BeaconState, slots: int) -> spec.BeaconState:
    for i in range(slots):
        block = helpers.build_empty_block_for_next_slot(state)
        state_transition_to(state, block.slot)
        process_block(state, block, False)
        if i > spec.MIN_ATTESTATION_INCLUSION_DELAY:
            new_attestation = get_valid_attestation(state, keys.privkeys,
                                                    state.slot - spec.MIN_ATTESTATION_INCLUSION_DELAY)
            spec.process_attestation(state, new_attestation)

    return state


def update_signature(attestation: spec.Attestation, state: spec.BeaconState, private_keys) -> spec.Attestation:
    """
    Signature is not updated as it's not verified, BLS is mocked
    """
    pass


def get_valid_attestation(state, private_keys, slot=None):
    if slot is None:
        slot = state.slot

    crosslink_committee, shard = spec.get_crosslink_committees_at_slot(state, slot)[0]
    attestation_data = helpers.build_attestation_data(state, slot, shard)

    committee_size = len(crosslink_committee)
    assert committee_size > 0
    bitfield_length = (committee_size + 7) // 8
    aggregation_bitfield = bytearray(bitfield_length)
    for index_into_committee in range(len(crosslink_committee)):
        aggregation_bitfield[index_into_committee // 8] |= 2 ** (index_into_committee % 8)
    custody_bitfield = b'\x00' * bitfield_length
    attestation = spec.Attestation(
        aggregation_bitfield=bytes(aggregation_bitfield),
        data=attestation_data,
        custody_bitfield=custody_bitfield,
    )
    participants = spec.get_attesting_indices(
        state,
        attestation.data,
        attestation.aggregation_bitfield,
    )

    signatures = []
    for validator_index in participants:
        privkey = private_keys[validator_index]
        signatures.append(
            helpers.get_attestation_signature(
                state,
                attestation.data,
                privkey
            )
        )

    attestation.signature = bls.bls_aggregate_signatures(signatures)
    return attestation


@to_dict
def valid_attestation():
    new_attestation, state = build_simple_state_and_attestation(spec.SLOTS_PER_EPOCH)
    yield 'description', 'valid attestation for current epoch'
    yield 'pre', encode(state, spec.BeaconState)
    yield 'attestation', encode(new_attestation, spec.Attestation)
    assert len(state.current_epoch_attestations) == 0
    spec.process_attestation(state, new_attestation)
    assert len(state.current_epoch_attestations) == 1
    yield 'post', encode(state, spec.BeaconState)


@to_dict
def valid_attestation_previous_epoch():
    state = build_justified_state(spec.SLOTS_PER_EPOCH, spec.SLOTS_PER_EPOCH * 3)
    # skip one epoch so we could have empty attestations list
    state_transition_to(state, spec.Slot(state.slot + spec.SLOTS_PER_EPOCH))
    attest_slot = state.slot
    state_transition_to(state, spec.Slot(attest_slot + spec.SLOTS_PER_EPOCH))
    yield 'description', 'valid attestation for previous epoch'
    yield 'pre', encode(state, spec.BeaconState)
    attestation = get_valid_attestation(state, keys.privkeys, attest_slot)
    yield 'attestation', encode(attestation, spec.Attestation)
    assert len(state.previous_epoch_attestations) == 0
    spec.process_attestation(state, attestation)
    assert len(state.previous_epoch_attestations) == 1
    yield 'post', encode(state, spec.BeaconState)


@to_dict
def invalid_attestation_wrong_source_root():
    state = build_justified_state(spec.SLOTS_PER_EPOCH, spec.SLOTS_PER_EPOCH * 3)
    attest_slot = spec.Slot(state.slot - spec.MIN_ATTESTATION_INCLUSION_DELAY)
    attestation = get_valid_attestation(state, keys.privkeys, attest_slot)
    # Make attestation source root invalid
    attestation.data.source_root = attestation.data.target_root
    update_signature(attestation, state, keys.privkeys)

    yield 'description', 'invalid attestation source root, same as target'
    yield 'pre', encode(state, spec.BeaconState)
    yield 'attestation', encode(attestation, spec.Attestation)
    try:
        spec.process_attestation(state, attestation)
    except AssertionError:
        # expected
        yield 'post', None
        return
    raise Exception('invalid_attestation_wrong_source_root has unexpectedly allowed attestation')


@to_dict
def invalid_attestation_current_epoch_source_root():
    state = build_justified_state(spec.SLOTS_PER_EPOCH, spec.SLOTS_PER_EPOCH * 3)
    attest_slot = spec.Slot(state.slot - spec.MIN_ATTESTATION_INCLUSION_DELAY)
    attestation = get_valid_attestation(state, keys.privkeys, attest_slot)
    # Make attestation source root invalid, should be previous
    assert state.current_justified_root != state.previous_justified_root
    assert attestation.data.source_root == state.previous_justified_root
    attestation.data.source_root = state.current_justified_root
    update_signature(attestation, state, keys.privkeys)

    yield 'description', 'invalid attestation source root, should be previous justified, not current one'
    yield 'pre', encode(state, spec.BeaconState)
    yield 'attestation', encode(attestation, spec.Attestation)
    try:
        spec.process_attestation(state, attestation)
    except AssertionError:
        # expected
        yield 'post', None
        return
    raise Exception('invalid_attestation_current_epoch_source_root has unexpectedly allowed attestation')


@to_dict
def invalid_attestation_new_source_epoch():
    state = build_justified_state(spec.SLOTS_PER_EPOCH, spec.SLOTS_PER_EPOCH * 3)
    attest_slot = spec.Slot(state.slot - spec.MIN_ATTESTATION_INCLUSION_DELAY)
    attestation = get_valid_attestation(state, keys.privkeys, attest_slot)
    # Make attestation source epoch invalid, next one
    assert attestation.data.source_epoch == 0
    attestation.data.source_epoch = 1
    update_signature(attestation, state, keys.privkeys)

    yield 'description', 'invalid attestation source epoch, should be from previous justified, not the next'
    yield 'pre', encode(state, spec.BeaconState)
    yield 'attestation', encode(attestation, spec.Attestation)
    try:
        spec.process_attestation(state, attestation)
    except AssertionError:
        # expected
        yield 'post', None
        return
    raise Exception('invalid_attestation_new_source_epoch has unexpectedly allowed attestation')


@to_dict
def invalid_attestation_old_source_epoch():
    state = build_justified_state(spec.SLOTS_PER_EPOCH, spec.SLOTS_PER_EPOCH * 4)
    attest_slot = spec.Slot(state.slot - spec.MIN_ATTESTATION_INCLUSION_DELAY)
    attestation = get_valid_attestation(state, keys.privkeys, attest_slot)
    # Make attestation source epoch invalid, one before
    assert attestation.data.source_epoch == 2
    attestation.data.source_epoch = 1
    update_signature(attestation, state, keys.privkeys)

    yield 'description', 'invalid attestation source epoch, should be from second epoch already'
    yield 'pre', encode(state, spec.BeaconState)
    yield 'attestation', encode(attestation, spec.Attestation)
    try:
        spec.process_attestation(state, attestation)
    except AssertionError:
        # expected
        yield 'post', None
        return
    raise Exception('invalid_attestation_old_source_epoch has unexpectedly allowed attestation')


@to_dict
def invalid_attestation_bad_crosslink_root():
    state = build_justified_state(spec.SLOTS_PER_EPOCH, spec.SLOTS_PER_EPOCH)
    # cache crosslink roots
    previous_crosslink_roots = set()
    for i in range(spec.SHARD_COUNT):
        old_attest_slot = spec.Slot(state.slot - spec.MIN_ATTESTATION_INCLUSION_DELAY)
        old_attestation = get_valid_attestation(state, keys.privkeys, old_attest_slot)
        previous_crosslink_roots.add(old_attestation.data.previous_crosslink_root)
        state = update_justified_state_with_slots(state, 1)
    assert len(previous_crosslink_roots) > 1
    new_attest_slot = spec.Slot(state.slot - spec.MIN_ATTESTATION_INCLUSION_DELAY)
    new_attestation = get_valid_attestation(state, keys.privkeys, new_attest_slot)
    new_attestation.data.previous_crosslink_root = \
        [x for x in previous_crosslink_roots if x != new_attestation.data.previous_crosslink_root][0]
    update_signature(new_attestation, state, keys.privkeys)

    yield 'description', 'invalid attestation previous_crosslink_root, from old set'
    yield 'pre', encode(state, spec.BeaconState)
    yield 'attestation', encode(new_attestation, spec.Attestation)
    try:
        spec.process_attestation(state, new_attestation)
    except AssertionError:
        # expected
        yield 'post', None
        return
    raise Exception('invalid_attestation_bad_crosslink_root has unexpectedly allowed attestation')


@to_dict
def invalid_attestation_non_zero_crosslink():
    new_attestation, state = build_simple_state_and_attestation(spec.SLOTS_PER_EPOCH)
    # Make attestation crosslink data root invalid (not zero)
    new_attestation.data.crosslink_data_root = spec.int_to_bytes32(1)
    update_signature(new_attestation, state, keys.privkeys)

    yield 'description', 'invalid attestation crosslink data root (should be zero)'
    yield 'pre', encode(state, spec.BeaconState)
    yield 'attestation', encode(new_attestation, spec.Attestation)
    try:
        spec.process_attestation(state, new_attestation)
    except AssertionError:
        # expected
        yield 'post', None
        return
    raise Exception('invalid_attestation_non_zero_crosslink has unexpectedly allowed attestation')


@to_dict
def invalid_attestation_mismatch_custody():
    new_attestation, state = build_simple_state_and_attestation(spec.SLOTS_PER_EPOCH)
    # Make attestation custody bits invalid by reverting last byte
    new_attestation.custody_bitfield = new_attestation.custody_bitfield[:-1] + bytes(
        [~new_attestation.custody_bitfield[-1] & 0xFF])
    update_signature(new_attestation, state, keys.privkeys)

    yield 'description', 'invalid attestation custody bits'
    yield 'pre', encode(state, spec.BeaconState)
    yield 'attestation', encode(new_attestation, spec.Attestation)
    try:
        spec.process_attestation(state, new_attestation)
    except AssertionError:
        # expected
        yield 'post', None
        return
    raise Exception('invalid_attestation_mismatch_custody has unexpectedly allowed attestation')


@to_dict
def invalid_attestation_wrong_slot(delta_slot: int):
    new_attestation, state = build_simple_state_and_attestation(spec.SLOTS_PER_EPOCH)
    # Make attestation invalid by changing slot. Before we have genesis,
    # after - MIN_ATTESTATION_INCLUSION_DELAY will be not respected
    new_attestation.data.slot = new_attestation.data.slot + delta_slot
    update_signature(new_attestation, state, keys.privkeys)

    yield 'description', 'invalid attestation slot'
    yield 'pre', encode(state, spec.BeaconState)
    yield 'attestation', encode(new_attestation, spec.Attestation)
    try:
        spec.process_attestation(state, new_attestation)
    except (IndexError, AssertionError):
        # expected
        yield 'post', None
        return
    raise Exception('invalid_attestation_wrong_slot has unexpectedly allowed attestation')


@to_tuple
def attestation_cases():
    yield valid_attestation()
    yield valid_attestation_previous_epoch()
    yield invalid_attestation_wrong_source_root()
    yield invalid_attestation_current_epoch_source_root()
    yield invalid_attestation_new_source_epoch()
    yield invalid_attestation_old_source_epoch()
    yield invalid_attestation_bad_crosslink_root()
    yield invalid_attestation_non_zero_crosslink()
    yield invalid_attestation_mismatch_custody()
    yield invalid_attestation_wrong_slot(-1)
    yield invalid_attestation_wrong_slot(1)


@to_tuple
def attestation_cases_lite_with_peppercorn():
    """
    Lite cases only with one heavy case included
    """
    yield valid_attestation()
    yield invalid_attestation_new_source_epoch()
    yield invalid_attestation_non_zero_crosslink()
    yield invalid_attestation_mismatch_custody()
    yield invalid_attestation_wrong_slot(-1)
    yield invalid_attestation_wrong_slot(1)


def mini_attestations_suite(configs_path: str) -> gen_typing.TestSuiteOutput:
    presets = loader.load_presets(configs_path, 'minimal')
    spec.apply_constants_preset(presets)

    return ("attestation_minimal", "attestations", gen_suite.render_suite(
        title="attestation operation",
        summary="Test suite for attestation type operation processing",
        forks_timeline="testing",
        forks=["phase0"],
        config="minimal",
        runner="operations",
        handler="attestations",
        test_cases=attestation_cases()))


def full_attestations_suite(configs_path: str) -> gen_typing.TestSuiteOutput:
    presets = loader.load_presets(configs_path, 'mainnet')
    spec.apply_constants_preset(presets)

    return ("attestation_full", "attestations", gen_suite.render_suite(
        title="attestation operation",
        summary="Test suite for attestation type operation processing",
        forks_timeline="mainnet",
        forks=["phase0"],
        config="mainnet",
        runner="operations",
        handler="attestations",
        test_cases=attestation_cases_lite_with_peppercorn()))
