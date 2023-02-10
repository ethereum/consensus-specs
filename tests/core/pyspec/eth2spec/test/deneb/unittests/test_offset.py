
from eth2spec.test.helpers.constants import (
    DENEB,
    MINIMAL,
)
from eth2spec.test.helpers.sharding import (
    get_sample_opaque_tx,
)
from eth2spec.test.context import (
    with_phases,
    spec_state_test,
    with_presets,
)


@with_phases([DENEB])
@spec_state_test
@with_presets([MINIMAL])
def test_tx_peek_blob_versioned_hashes(spec, state):
    otx, blobs, commitments = get_sample_opaque_tx(spec)
    data_hashes = spec.tx_peek_blob_versioned_hashes(otx)
    expected = [spec.kzg_commitment_to_versioned_hash(blob_commitment) for blob_commitment in commitments]
    assert expected == data_hashes
