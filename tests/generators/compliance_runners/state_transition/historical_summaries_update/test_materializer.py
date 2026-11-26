from random import Random
from types import SimpleNamespace

from eth_consensus_specs.gloas import minimal as spec
from eth_consensus_specs.test.helpers.block import build_empty_block
from eth_consensus_specs.test.helpers.epoch_processing import run_epoch_processing_to
from eth_consensus_specs.test.helpers.genesis import create_genesis_state

from .materializer import MATERIALIZER


def test_final_block_matches_skipped_slot_replay():
    materializer = MATERIALIZER(spec)
    materializer.rng = Random(0)
    genesis = create_genesis_state(
        spec, [spec.MAX_EFFECTIVE_BALANCE] * 64, spec.MAX_EFFECTIVE_BALANCE
    )
    slot = 2 * spec.SLOTS_PER_EPOCH - 1
    # Reuse one generator in reverse slot order, including a historical-ring wrap.
    for count, final_slot in [("GT_1", slot + spec.SLOTS_PER_HISTORICAL_ROOT), ("EQ", slot)]:
        solution = SimpleNamespace(update_remainder="INTERIOR", summaries_nonempty=count)
        _, parts = materializer.materialize_solution(solution)
        pre = spec.BeaconState.decode_bytes(next(data for name, _, data in parts if name == "pre"))

        replay = genesis.copy()
        spec.process_slots(replay, final_slot)
        block = build_empty_block(spec, replay)
        assert pre.latest_block_header.proposer_index == block.proposer_index
        spec.process_block(replay, block)
        run_epoch_processing_to(spec, replay, "process_historical_summaries_update")
        assert pre == replay
