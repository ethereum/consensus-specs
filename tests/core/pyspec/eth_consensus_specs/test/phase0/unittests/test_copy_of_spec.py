from eth_consensus_specs.test.context import (
    get_copy_of_spec,
    single_phase,
    spec_test,
    with_all_phases,
)


@with_all_phases
@spec_test
@single_phase
def test_copy_of_spec_cached_functions_use_copy(spec):
    index_count = spec.Uint64(16)
    seed = spec.Bytes32(b"\x01" * 32)
    shuffled_original = spec.compute_shuffled_permutation(index_count, seed)
    assert list(shuffled_original) != list(range(index_count))

    spec_copy = get_copy_of_spec(spec)
    spec_copy.SHUFFLE_ROUND_COUNT = 0
    shuffled_modified = spec_copy.compute_shuffled_permutation(index_count, seed)
    assert list(shuffled_modified) == list(range(index_count))
    assert spec.compute_shuffled_permutation(index_count, seed) == shuffled_original
