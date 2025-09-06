# TODO(jtraglia): for all tests in this file, consider adding support for Gloas later

from random import Random

from eth2spec.test.context import (
    spec_state_test,
    with_all_phases_from_to,
)
from eth2spec.test.helpers.blob import get_block_with_blob_and_sidecars
from eth2spec.test.helpers.constants import (
    FULU,
    GLOAS,
)
from eth2spec.test.helpers.fork_choice import (
    BlobData,
    get_genesis_forkchoice_store_and_block,
    on_tick_and_append_step,
    tick_and_add_block_with_data,
)
from tests.infra.spec_cache import spec_cache_peerdas


def flip_one_bit_in_bytes(data: bytes, index: int = 0) -> bytes:
    """
    Flip one bit in a bytes object at the given index.
    """
    constr = data.__class__
    byte_index = index // 8
    bit_index = 7 - (index % 8)
    byte = data[byte_index]
    flipped_byte = byte ^ (1 << bit_index)

    return constr(bytes(data[:byte_index]) + bytes([flipped_byte]) + bytes(data[byte_index + 1 :]))


def get_alt_sidecars(spec, state):
    """
    Get alternative sidecars for negative test cases.
    """
    rng = Random(4321)
    state_copy = state.copy()
    _, _, _, _, alt_sidecars = get_block_with_blob_and_sidecars(
        spec, state_copy, rng=rng, blob_count=2
    )
    return alt_sidecars


@with_all_phases_from_to(FULU, GLOAS)
@spec_state_test
@spec_cache_peerdas
def test_on_block_peerdas__ok(spec, state):
    """
    Similar to test_simple_blob_data, but in PeerDAS version that is from Fulu onwards.
    It covers code related to the blob sidecars because on_block calls `is_data_available`
    and we are calling `get_data_column_sidecars_from_block` in the test itself.
    """
    rng = Random(1234)

    test_steps = []
    # Initialization
    store, anchor_block = get_genesis_forkchoice_store_and_block(spec, state)
    yield "anchor_state", state
    yield "anchor_block", anchor_block
    current_time = state.slot * spec.config.SECONDS_PER_SLOT + store.genesis_time
    on_tick_and_append_step(spec, store, current_time, test_steps)
    assert store.time == current_time

    # On receiving a block of `GENESIS_SLOT + 1` slot
    _, _, _, signed_block, sidecars = get_block_with_blob_and_sidecars(
        spec, state, rng=rng, blob_count=2
    )
    blob_data = BlobData(sidecars=sidecars)

    yield from tick_and_add_block_with_data(spec, store, signed_block, test_steps, blob_data)

    assert spec.get_head(store) == signed_block.message.hash_tree_root()

    # On receiving a block of next epoch
    _, _, _, signed_block, sidecars = get_block_with_blob_and_sidecars(
        spec, state, rng=rng, blob_count=2
    )
    blob_data = BlobData(sidecars=sidecars)

    yield from tick_and_add_block_with_data(spec, store, signed_block, test_steps, blob_data)

    assert spec.get_head(store) == signed_block.message.hash_tree_root()

    yield "steps", test_steps


def run_on_block_peerdas_invalid_test(spec, state, fn):
    """
    Run a invalid PeerDAS on_block test with a sidecars mutation function.
    """
    rng = Random(1234)

    test_steps = []

    # Initialization
    store, anchor_block = get_genesis_forkchoice_store_and_block(spec, state)
    yield "anchor_state", state
    yield "anchor_block", anchor_block
    current_time = state.slot * spec.config.SECONDS_PER_SLOT + store.genesis_time
    on_tick_and_append_step(spec, store, current_time, test_steps)
    assert store.time == current_time

    _, _, _, signed_block, sidecars = get_block_with_blob_and_sidecars(
        spec, state, rng=rng, blob_count=2
    )
    sidecars = fn(sidecars)
    blob_data = BlobData(sidecars=sidecars)

    yield from tick_and_add_block_with_data(
        spec, store, signed_block, test_steps, blob_data, valid=False
    )
    assert spec.get_head(store) != signed_block.message.hash_tree_root()

    yield "steps", test_steps


@with_all_phases_from_to(FULU, GLOAS)
@spec_state_test
@spec_cache_peerdas
def test_on_block_peerdas__not_available(spec, state):
    """
    Test is_data_available throws an exception when not enough columns are sampled.
    """
    yield from run_on_block_peerdas_invalid_test(
        spec,
        state,
        # Empty sidecars will trigger the simulation of not enough columns being sampled
        lambda _: [],
    )


@with_all_phases_from_to(FULU, GLOAS)
@spec_state_test
@spec_cache_peerdas
def test_on_block_peerdas__invalid_zero_blobs(spec, state):
    """
    Test is_data_available returns false when there are no blobs in the sidecars.
    """

    def invalid_zero_blobs(sidecars):
        sidecars[0].column = []
        sidecars[0].kzg_commitments = []
        sidecars[0].kzg_proofs = []
        return sidecars

    yield from run_on_block_peerdas_invalid_test(spec, state, invalid_zero_blobs)


@with_all_phases_from_to(FULU, GLOAS)
@spec_state_test
@spec_cache_peerdas
def test_on_block_peerdas__invalid_index_1(spec, state):
    """
    Test invalid index in sidecars for negative PeerDAS on_block test.
    """

    def invalid_index(sidecars):
        sidecars[0].index = 128  # Invalid index
        return sidecars

    yield from run_on_block_peerdas_invalid_test(spec, state, invalid_index)


@with_all_phases_from_to(FULU, GLOAS)
@spec_state_test
@spec_cache_peerdas
def test_on_block_peerdas__invalid_index_2(spec, state):
    """
    Test invalid index in sidecars for negative PeerDAS on_block test.
    """

    def invalid_index(sidecars):
        sidecars[0].index = 256  # Invalid index
        return sidecars

    yield from run_on_block_peerdas_invalid_test(spec, state, invalid_index)


@with_all_phases_from_to(FULU, GLOAS)
@spec_state_test
@spec_cache_peerdas
def test_on_block_peerdas__invalid_mismatch_len_column_1(spec, state):
    """
    Test mismatch length in column for negative PeerDAS on_block test.
    """

    def invalid_mismatch_len_column(sidecars):
        sidecars[0].column = sidecars[0].column[1:]
        return sidecars

    yield from run_on_block_peerdas_invalid_test(spec, state, invalid_mismatch_len_column)


@with_all_phases_from_to(FULU, GLOAS)
@spec_state_test
@spec_cache_peerdas
def test_on_block_peerdas__invalid_mismatch_len_column_2(spec, state):
    """
    Test mismatch length in column for negative PeerDAS on_block test.
    """

    def invalid_mismatch_len_column(sidecars):
        sidecars[1].column = sidecars[1].column[1:]
        return sidecars

    yield from run_on_block_peerdas_invalid_test(spec, state, invalid_mismatch_len_column)


@with_all_phases_from_to(FULU, GLOAS)
@spec_state_test
@spec_cache_peerdas
def test_on_block_peerdas__invalid_mismatch_len_kzg_commitments_1(spec, state):
    """
    Test mismatch length in kzg_commitments for negative PeerDAS on_block test.
    """

    def invalid_mismatch_len_kzg_commitments(sidecars):
        sidecars[0].kzg_commitments = sidecars[0].kzg_commitments[1:]
        return sidecars

    yield from run_on_block_peerdas_invalid_test(spec, state, invalid_mismatch_len_kzg_commitments)


@with_all_phases_from_to(FULU, GLOAS)
@spec_state_test
@spec_cache_peerdas
def test_on_block_peerdas__invalid_mismatch_len_kzg_commitments_2(spec, state):
    """
    Test mismatch length in kzg_commitments for negative PeerDAS on_block test.
    """

    def invalid_mismatch_len_kzg_commitments(sidecars):
        sidecars[1].kzg_commitments = sidecars[1].kzg_commitments[1:]
        return sidecars

    yield from run_on_block_peerdas_invalid_test(spec, state, invalid_mismatch_len_kzg_commitments)


@with_all_phases_from_to(FULU, GLOAS)
@spec_state_test
@spec_cache_peerdas
def test_on_block_peerdas__invalid_mismatch_len_kzg_proofs_1(spec, state):
    """
    Test mismatch length in kzg_proofs for negative PeerDAS on_block test.
    """

    def invalid_mismatch_len_kzg_proofs(sidecars):
        sidecars[0].kzg_proofs = sidecars[0].kzg_proofs[1:]
        return sidecars

    yield from run_on_block_peerdas_invalid_test(spec, state, invalid_mismatch_len_kzg_proofs)


@with_all_phases_from_to(FULU, GLOAS)
@spec_state_test
@spec_cache_peerdas
def test_on_block_peerdas__invalid_mismatch_len_kzg_proofs_2(spec, state):
    """
    Test mismatch length in kzg_proofs for negative PeerDAS on_block test.
    """

    def invalid_mismatch_len_kzg_proofs(sidecars):
        sidecars[1].kzg_proofs = sidecars[1].kzg_proofs[1:]
        return sidecars

    yield from run_on_block_peerdas_invalid_test(spec, state, invalid_mismatch_len_kzg_proofs)


@with_all_phases_from_to(FULU, GLOAS)
@spec_state_test
@spec_cache_peerdas
def test_on_block_peerdas__invalid_wrong_column_1(spec, state):
    """
    Test wrong column for negative PeerDAS on_block test.
    """

    def invalid_wrong_column(sidecars):
        sidecars[0].column[0] = flip_one_bit_in_bytes(sidecars[0].column[0], 80)
        return sidecars

    yield from run_on_block_peerdas_invalid_test(spec, state, invalid_wrong_column)


@with_all_phases_from_to(FULU, GLOAS)
@spec_state_test
@spec_cache_peerdas
def test_on_block_peerdas__invalid_wrong_column_2(spec, state):
    """
    Test wrong column for negative PeerDAS on_block test.
    """

    def invalid_wrong_column(sidecars):
        sidecars[1].column[1] = flip_one_bit_in_bytes(sidecars[1].column[1], 20)
        return sidecars

    yield from run_on_block_peerdas_invalid_test(spec, state, invalid_wrong_column)


@with_all_phases_from_to(FULU, GLOAS)
@spec_state_test
@spec_cache_peerdas
def test_on_block_peerdas__invalid_wrong_commitment_1(spec, state):
    """
    Test wrong commitment for negative PeerDAS on_block test.
    """
    alt_sidecars = get_alt_sidecars(spec, state)

    def invalid_wrong_commitment(sidecars, alt_sidecars=alt_sidecars):
        sidecars[0].kzg_commitments[0] = alt_sidecars[0].kzg_commitments[0]
        return sidecars

    yield from run_on_block_peerdas_invalid_test(spec, state, invalid_wrong_commitment)


@with_all_phases_from_to(FULU, GLOAS)
@spec_state_test
@spec_cache_peerdas
def test_on_block_peerdas__invalid_wrong_commitment_2(spec, state):
    """
    Test wrong commitment for negative PeerDAS on_block test.
    """
    alt_sidecars = get_alt_sidecars(spec, state)

    def invalid_wrong_commitment(sidecars, alt_sidecars=alt_sidecars):
        sidecars[1].kzg_commitments[1] = alt_sidecars[1].kzg_commitments[1]
        return sidecars

    yield from run_on_block_peerdas_invalid_test(spec, state, invalid_wrong_commitment)


@with_all_phases_from_to(FULU, GLOAS)
@spec_state_test
@spec_cache_peerdas
def test_on_block_peerdas__invalid_wrong_proof_1(spec, state):
    """
    Test wrong proof for negative PeerDAS on_block test.
    """
    alt_sidecars = get_alt_sidecars(spec, state)

    def invalid_wrong_proof(sidecars, alt_sidecars=alt_sidecars):
        sidecars[0].kzg_proofs[0] = alt_sidecars[0].kzg_proofs[0]
        return sidecars

    yield from run_on_block_peerdas_invalid_test(spec, state, invalid_wrong_proof)


@with_all_phases_from_to(FULU, GLOAS)
@spec_state_test
@spec_cache_peerdas
def test_on_block_peerdas__invalid_wrong_proof_2(spec, state):
    """
    Test wrong proof for negative PeerDAS on_block test.
    """
    alt_sidecars = get_alt_sidecars(spec, state)

    def invalid_wrong_proof(sidecars, alt_sidecars=alt_sidecars):
        sidecars[1].kzg_proofs[1] = alt_sidecars[1].kzg_proofs[1]
        return sidecars

    yield from run_on_block_peerdas_invalid_test(spec, state, invalid_wrong_proof)
