import random

from eth2spec.test.context import (
    expect_assertion_error,
    single_phase,
    spec_test,
    with_config_overrides,
    with_fulu_and_later,
)
from eth2spec.test.helpers.blob import (
    get_sample_blob,
)

from tests.core.pyspec.eth2spec.test.context import spec_state_test
from tests.core.pyspec.eth2spec.test.deneb.fork_choice.test_on_block import get_block_with_blob
from tests.core.pyspec.eth2spec.test.helpers.fork_choice import BlobData, with_blob_data
from tests.core.pyspec.eth2spec.test.helpers.state import state_transition_and_sign_block
from tests.core.pyspec.eth2spec.utils.ssz.ssz_impl import hash_tree_root


def chunks(lst, n):
    """Helper that splits a list into N sized chunks."""
    return [lst[i : i + n] for i in range(0, len(lst), n)]


@with_fulu_and_later
@spec_test
@single_phase
def test_compute_matrix(spec):
    rng = random.Random(5566)

    blob_count = 2
    input_blobs = [get_sample_blob(spec, rng=rng) for _ in range(blob_count)]
    matrix = spec.compute_matrix(input_blobs)
    assert len(matrix) == spec.CELLS_PER_EXT_BLOB * blob_count

    rows = chunks(matrix, spec.CELLS_PER_EXT_BLOB)
    assert len(rows) == blob_count
    for row in rows:
        assert len(row) == spec.CELLS_PER_EXT_BLOB

    for blob_index, row in enumerate(rows):
        extended_blob = []
        for entry in row:
            extended_blob.extend(spec.cell_to_coset_evals(entry.cell))
        blob_part = extended_blob[0 : len(extended_blob) // 2]
        blob = b"".join([spec.bls_field_to_bytes(x) for x in blob_part])
        assert blob == input_blobs[blob_index]


@with_fulu_and_later
@spec_test
@single_phase
def test_recover_matrix(spec):
    rng = random.Random(5566)

    # Number of samples we will be recovering from
    N_SAMPLES = spec.CELLS_PER_EXT_BLOB // 2

    # Compute an extended matrix with two blobs
    blob_count = 2
    blobs = [get_sample_blob(spec, rng=rng) for _ in range(blob_count)]
    matrix = spec.compute_matrix(blobs)

    # Construct a matrix with some entries missing
    partial_matrix = []
    for blob_entries in chunks(matrix, spec.CELLS_PER_EXT_BLOB):
        rng.shuffle(blob_entries)
        partial_matrix.extend(blob_entries[:N_SAMPLES])

    # Given the partial matrix, recover the missing entries
    recovered_matrix = spec.recover_matrix(partial_matrix, blob_count)

    # Ensure that the recovered matrix matches the original matrix
    assert recovered_matrix == matrix


@with_fulu_and_later
@spec_test
@single_phase
def test_get_extended_sample_count__1(spec):
    rng = random.Random(1111)
    allowed_failures = rng.randint(0, spec.config.NUMBER_OF_COLUMNS // 2)
    spec.get_extended_sample_count(allowed_failures)


@with_fulu_and_later
@spec_test
@single_phase
def test_get_extended_sample_count__2(spec):
    rng = random.Random(2222)
    allowed_failures = rng.randint(0, spec.config.NUMBER_OF_COLUMNS // 2)
    spec.get_extended_sample_count(allowed_failures)


@with_fulu_and_later
@spec_test
@single_phase
def test_get_extended_sample_count__3(spec):
    rng = random.Random(3333)
    allowed_failures = rng.randint(0, spec.config.NUMBER_OF_COLUMNS // 2)
    spec.get_extended_sample_count(allowed_failures)


@with_fulu_and_later
@spec_test
@single_phase
def test_get_extended_sample_count__lower_bound(spec):
    allowed_failures = 0
    spec.get_extended_sample_count(allowed_failures)


@with_fulu_and_later
@spec_test
@single_phase
def test_get_extended_sample_count__upper_bound(spec):
    allowed_failures = spec.config.NUMBER_OF_COLUMNS // 2
    spec.get_extended_sample_count(allowed_failures)


@with_fulu_and_later
@spec_test
@single_phase
def test_get_extended_sample_count__upper_bound_exceed(spec):
    allowed_failures = spec.config.NUMBER_OF_COLUMNS // 2 + 1
    expect_assertion_error(lambda: spec.get_extended_sample_count(allowed_failures))


@with_fulu_and_later
@spec_test
@with_config_overrides(
    {
        "NUMBER_OF_COLUMNS": 128,
        "SAMPLES_PER_SLOT": 16,
    }
)
@single_phase
def test_get_extended_sample_count__table_in_spec(spec):
    table = dict(
        # (allowed_failures, expected_extended_sample_count)
        {
            0: 16,
            1: 20,
            2: 24,
            3: 27,
            4: 29,
            5: 32,
            6: 35,
            7: 37,
            8: 40,
        }
    )
    for allowed_failures, expected_extended_sample_count in table.items():
        assert (
            spec.get_extended_sample_count(allowed_failures=allowed_failures)
            == expected_extended_sample_count
        )

@with_fulu_and_later
@spec_state_test
def test_is_data_available_peerdas(spec, state):
    rng = random.Random(1234)

    block, blobs, blob_kzg_proofs = get_block_with_blob(spec, state, rng=rng)
    # We need a signed block to call `get_data_column_sidecars_from_block`
    signed_block = state_transition_and_sign_block(spec, state, block)
    sidecars = spec.get_data_column_sidecars_from_block(signed_block, [spec.compute_cells_and_kzg_proofs(blob) for blob in blobs])
    blob_data = BlobData(blobs, blob_kzg_proofs, sidecars)

    def callback():
        yield spec.is_data_available(hash_tree_root(signed_block))

    result = next(with_blob_data(spec, blob_data, callback))

    assert result is True, "Data should be available for the block with blob data"

@with_fulu_and_later
@spec_state_test
def test_is_data_available_peerdas_not_avail(spec, state):
    rng = random.Random(1234)

    block, blobs, blob_kzg_proofs = get_block_with_blob(spec, state, rng=rng)

    # Empty sidecars will trigger the simulation of not enough columns being available
    blob_data = BlobData(blobs, blob_kzg_proofs, [])

    def callback():
        try:
            spec.is_data_available(hash_tree_root(block))
            yield False
        except ValueError:
            yield True

    result = next(with_blob_data(spec, blob_data, callback))

    assert result is True, "Should throw an exception when data is not available"
