from eth_consensus_specs.test.context import (
    single_phase,
    spec_test,
    with_fulu_and_later,
    with_phases,
)
from eth_consensus_specs.test.helpers.constants import (
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
        * spec.config.MAX_BLOBS_PER_BLOCK
    )
    bytes_per_slot = column_size_in_bytes * spec.SAMPLES_PER_SLOT
    # TODO: What is the bandwidth requirement?
    bandwidth_requirement = 10000  # bytes/s
    assert bytes_per_slot * 1000 // spec.config.SLOT_DURATION_MS < bandwidth_requirement
