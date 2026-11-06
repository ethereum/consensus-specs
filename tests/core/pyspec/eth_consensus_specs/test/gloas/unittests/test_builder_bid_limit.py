from eth_consensus_specs.test.context import (
    spec_state_test,
    with_gloas_and_later,
)


def _get_bid_limit_for_balance(spec, state, balance):
    builder_index = spec.BuilderIndex(0)
    state.builders[builder_index].balance = spec.Gwei(balance)
    return spec.get_builder_bid_limit(state, builder_index)


@with_gloas_and_later
@spec_state_test
def test_get_builder_bid_limit__one_bid_per_eth(spec, state):
    """A builder may submit one bid per ETH of balance."""
    for eth in [1, 2, 31]:
        assert _get_bid_limit_for_balance(spec, state, eth * spec.ETH_TO_GWEI) == eth


@with_gloas_and_later
@spec_state_test
def test_get_builder_bid_limit__rounds_down(spec, state):
    """A partial ETH of balance does not grant an extra bid."""
    assert _get_bid_limit_for_balance(spec, state, 0) == 0
    assert _get_bid_limit_for_balance(spec, state, spec.ETH_TO_GWEI - 1) == 0
    assert _get_bid_limit_for_balance(spec, state, 2 * spec.ETH_TO_GWEI - 1) == 1


@with_gloas_and_later
@spec_state_test
def test_get_builder_bid_limit__capped(spec, state):
    """The bid limit never exceeds ``MAX_BIDS_PER_BUILDER_PER_SLOT``."""
    max_bids = spec.config.MAX_BIDS_PER_BUILDER_PER_SLOT
    for eth in [max_bids, max_bids + 1, 2048]:
        assert _get_bid_limit_for_balance(spec, state, eth * spec.ETH_TO_GWEI) == max_bids
