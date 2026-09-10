from eth_consensus_specs.test.context import (
    single_phase,
    spec_test,
    with_fulu_and_later,
    with_presets,
)
from eth_consensus_specs.test.helpers.constants import (
    MAINNET,
)
from eth_consensus_specs.test.helpers.fork_choice import get_slot_start_time_ms


@with_fulu_and_later
@spec_test
@single_phase
@with_presets([MAINNET])
def test_sampling_config(spec):
    probability_of_unavailable = 2 ** (-int(spec.config.SAMPLES_PER_SLOT))
    # TODO: What is the security requirement?
    security_requirement = 0.01
    assert probability_of_unavailable <= security_requirement

    column_size_in_bytes = (
        spec.FIELD_ELEMENTS_PER_CELL
        * spec.BYTES_PER_FIELD_ELEMENT
        * spec.config.MAX_BLOBS_PER_BLOCK
    )
    bytes_per_slot = column_size_in_bytes * spec.config.SAMPLES_PER_SLOT
    # TODO: What is the bandwidth requirement?
    bandwidth_requirement = 10000  # bytes/s
    slot_duration_ms = get_slot_start_time_ms(spec, 0, spec.GENESIS_SLOT + 1)
    assert bytes_per_slot * 1000 // slot_duration_ms < bandwidth_requirement
