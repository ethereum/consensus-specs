from eth2spec.fuzzing.decoder import translate_typ, translate_value
from eth2spec.phase0 import spec
from eth2spec.utils.ssz import ssz_impl as spec_ssz_impl
from random import Random
from eth2spec.debug import random_value


def test_decoder():
    rng = Random(123)

    # check these types only, Block covers a lot of operation types already.
    for typ in [spec.AttestationDataAndCustodyBit, spec.BeaconState, spec.BeaconBlock]:
        # create a random pyspec value
        original = random_value.get_random_ssz_object(rng, typ, 100, 10,
                                                      mode=random_value.RandomizationMode.mode_random,
                                                      chaos=True)
        # serialize it, using pyspec
        pyspec_data = spec_ssz_impl.serialize(original)
        # get the py-ssz type for it
        block_sedes = translate_typ(typ)
        # try decoding using the py-ssz type
        raw_value = block_sedes.deserialize(pyspec_data)

        # serialize it using py-ssz
        pyssz_data = block_sedes.serialize(raw_value)
        # now check if the serialized form is equal. If so, we confirmed decoding and encoding to work.
        assert pyspec_data == pyssz_data

        # now translate the py-ssz value in a pyspec-value
        block = translate_value(raw_value, typ)

        # and see if the hash-tree-root of the original matches the hash-tree-root of the decoded & translated value.
        assert spec_ssz_impl.hash_tree_root(original) == spec_ssz_impl.hash_tree_root(block)
