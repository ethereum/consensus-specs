from eth2spec.test.context import (
    spec_test,
    single_phase,
    with_fulu_and_later,
    with_phases,
)
from eth2spec.test.helpers.constants import (
    MAINNET,
)


@with_fulu_and_later
@spec_test
@single_phase
@with_phases([MAINNET])
def test_sampling_config(spec):
    probability_of_unavailable = 2 ** (-int(spec.SAMPLES_PER_SLOT))
    # TODO: What is the security requirement?
    security_requirement = 0.01
    assert probability_of_unavailable <= security_requirement

    column_size_in_bytes = (
        spec.FIELD_ELEMENTS_PER_CELL
        * spec.BYTES_PER_FIELD_ELEMENT
        * max(entry["MAX_BLOBS_PER_BLOCK"] for entry in spec.config.BLOB_SCHEDULE)
    )
    bytes_per_slot = column_size_in_bytes * spec.SAMPLES_PER_SLOT
    # TODO: What is the bandwidth requirement?
    bandwidth_requirement = 10000  # bytes/s
    assert bytes_per_slot // spec.config.SECONDS_PER_SLOT < bandwidth_requirement
