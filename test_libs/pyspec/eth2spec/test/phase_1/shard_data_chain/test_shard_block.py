from eth2spec.test.helpers.phase1.shard_block import (
    build_empty_shard_block,
)
from eth2spec.test.context import (
    with_all_phases_except,
    spec_state_test,
    always_bls,
)


@with_all_phases_except(['phase0'])
@always_bls
@spec_state_test
def test_is_valid_shard_block(spec, state):
    block = build_empty_shard_block(
        spec,
        state,
        slot=spec.Slot(spec.PERSISTENT_COMMITTEE_PERIOD * 100),
        shard=spec.Shard(1),
        parent_root=spec.Hash(),
        signed=True,
    )

    # TODO: test `is_valid_shard_block`

    yield 'blocks', (block,)
