from eth_consensus_specs.test.context import spec_state_test, with_eip8450_and_later
from eth_consensus_specs.test.gloas.networking.test_gossip_beacon_block import (
    _assert_beacon_block_gossip,
)
from eth_consensus_specs.test.helpers.gossip import make_progressive_list


@with_eip8450_and_later
@spec_state_test
def test_gossip_beacon_block__reject_too_many_pq_key_registrations(spec, state):
    """A block with more PQ key registrations than the limit is rejected."""

    def mutate(spec, block):
        block.body.pq_key_registrations = make_progressive_list(
            spec.PQKeyRegistrations, spec.MAX_PQ_KEY_REGISTRATIONS + 1
        )

    yield from _assert_beacon_block_gossip(
        spec, state, mutate, "reject", "too many pq key registrations"
    )
