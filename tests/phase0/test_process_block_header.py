from copy import deepcopy
import pytest


from build.phase0.spec import (
    get_beacon_proposer_index,
    process_block_header,
)
from tests.phase0.helpers import (
    build_empty_block_for_next_slot,
)

# mark entire file as 'sanity' and 'header'
pytestmark = [pytest.mark.sanity, pytest.mark.header]


def test_proposer_slashed(state):
    pre_state = deepcopy(state)

    block = build_empty_block_for_next_slot(pre_state)
    proposer_index = get_beacon_proposer_index(pre_state, block.slot)
    pre_state.validator_registry[proposer_index].slashed = True
    with pytest.raises(AssertionError):
        process_block_header(pre_state, block)

    return state, [block], None
