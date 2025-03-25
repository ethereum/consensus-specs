from copy import deepcopy
from typing import Optional

from eth2spec.test.helpers.pow_block import (
    prepare_random_pow_chain,
)
from eth2spec.test.helpers.constants import (
    BELLATRIX,
)
from eth2spec.test.context import (
    spec_state_test,
    with_phases,
)


# For test_get_pow_block_at_terminal_total_difficulty
IS_HEAD_BLOCK = "is_head_block"
IS_HEAD_PARENT_BLOCK = "is_head_parent_block"

# NOTE: The following parameter names are in the view of the head block (the second block)
# 'block_reached_ttd', 'block_parent_hash_is_empty', 'parent_reached_ttd', 'return_block'
expected_results = [
    (False, False, False, None),
    (False, False, True, IS_HEAD_PARENT_BLOCK),
    (False, True, False, None),
    (False, True, True, IS_HEAD_PARENT_BLOCK),
    (True, False, False, IS_HEAD_BLOCK),
    (True, False, True, IS_HEAD_PARENT_BLOCK),
    (True, True, False, IS_HEAD_BLOCK),
    (True, True, True, IS_HEAD_PARENT_BLOCK),
]
# NOTE: since the first block's `parent_hash` is set to `Hash32()` in test, if `parent_reached_ttd is True`,
# it would return the first block (IS_HEAD_PARENT_BLOCK).


@with_phases([BELLATRIX])
@spec_state_test
def test_get_pow_block_at_terminal_total_difficulty(spec, state):
    for result in expected_results:
        (
            block_reached_ttd,
            block_parent_hash_is_empty,
            parent_reached_ttd,
            return_block,
        ) = result
        pow_chain = prepare_random_pow_chain(spec, 2)
        pow_chain.head(-1).parent_hash = spec.Hash32()

        if block_reached_ttd:
            pow_chain.head().total_difficulty = spec.config.TERMINAL_TOTAL_DIFFICULTY
        else:
            pow_chain.head().total_difficulty = spec.config.TERMINAL_TOTAL_DIFFICULTY - 1

        if parent_reached_ttd:
            pow_chain.head(-1).total_difficulty = spec.config.TERMINAL_TOTAL_DIFFICULTY
        else:
            pow_chain.head(-1).total_difficulty = spec.config.TERMINAL_TOTAL_DIFFICULTY - 1

        if block_parent_hash_is_empty:
            pow_chain.head().parent_hash = spec.Hash32()

        pow_block = spec.get_pow_block_at_terminal_total_difficulty(pow_chain.to_dict())
        if return_block == IS_HEAD_BLOCK:
            assert pow_block == pow_chain.head()
        elif return_block == IS_HEAD_PARENT_BLOCK:
            assert pow_block == pow_chain.head(-1)
        elif return_block is None:
            assert pow_block is None
        else:
            raise Exception("Something is wrong")


SAMPLE_PAYLOAD_ID = b"\x12" * 8
# ('is_merge_complete', 'is_terminal_block_hash_set', 'is_activation_epoch_reached',
# 'terminal_pow_block_is_none', 'result_payload_id')
prepare_execution_payload_expected_results = [
    (False, False, False, False, SAMPLE_PAYLOAD_ID),
    (False, False, False, True, None),
    (False, False, True, False, SAMPLE_PAYLOAD_ID),
    (False, False, True, True, None),
    (False, True, False, False, None),
    (False, True, False, True, None),
    (False, True, True, False, SAMPLE_PAYLOAD_ID),
    (False, True, True, True, None),
    (True, False, False, False, SAMPLE_PAYLOAD_ID),
    (True, False, False, True, SAMPLE_PAYLOAD_ID),
    (True, False, True, False, SAMPLE_PAYLOAD_ID),
    (True, False, True, True, SAMPLE_PAYLOAD_ID),
    (True, True, False, False, SAMPLE_PAYLOAD_ID),
    (True, True, False, True, SAMPLE_PAYLOAD_ID),
    (True, True, True, False, SAMPLE_PAYLOAD_ID),
    (True, True, True, True, SAMPLE_PAYLOAD_ID),
]


@with_phases([BELLATRIX])
@spec_state_test
def test_prepare_execution_payload(spec, state):
    for result in prepare_execution_payload_expected_results:
        (
            is_merge_complete,
            is_terminal_block_hash_set,
            is_activation_epoch_reached,
            terminal_pow_block_is_none,
            result_payload_id,
        ) = result

        # 1. Handle `is_merge_complete`
        if is_merge_complete:
            state.latest_execution_payload_header = spec.ExecutionPayloadHeader(
                prev_randao=b"\x12" * 32
            )
        else:
            state.latest_execution_payload_header = spec.ExecutionPayloadHeader()

        # 2. `is_terminal_block_hash_set` and `is_activation_epoch_reached` require mocking configs in runtime
        config_overrides = {}
        _mock_terminal_block_hash = b"\x34" * 32
        if is_terminal_block_hash_set:
            config_overrides["TERMINAL_BLOCK_HASH"] = _mock_terminal_block_hash
        else:
            config_overrides["TERMINAL_BLOCK_HASH"] = spec.Hash32()

        # Default `TERMINAL_BLOCK_HASH_ACTIVATION_EPOCH` is too big and too close to overflow
        _mock_terminal_block_hash_activation_epoch = 3
        config_overrides["TERMINAL_BLOCK_HASH_ACTIVATION_EPOCH"] = (
            _mock_terminal_block_hash_activation_epoch
        )
        if is_activation_epoch_reached:
            state.slot = _mock_terminal_block_hash_activation_epoch * spec.SLOTS_PER_EPOCH
        else:
            state.slot = (_mock_terminal_block_hash_activation_epoch - 1) * spec.SLOTS_PER_EPOCH

        # Logic from `with_config_overrides`
        old_config = spec.config
        tmp_config = deepcopy(old_config._asdict())
        tmp_config.update(config_overrides)
        config_types = spec.Configuration.__annotations__
        test_config = {k: config_types[k](v) for k, v in tmp_config.items()}
        spec.config = spec.Configuration(**test_config)

        # 3. Handle `terminal_pow_block_is_none`
        pow_chain = prepare_random_pow_chain(spec, 2)
        if terminal_pow_block_is_none:
            pow_chain.head().total_difficulty = spec.config.TERMINAL_TOTAL_DIFFICULTY - 1
        else:
            if is_terminal_block_hash_set:
                pow_chain.head().block_hash = _mock_terminal_block_hash
            pow_chain.head().total_difficulty = spec.config.TERMINAL_TOTAL_DIFFICULTY

        # Dummy arguments
        finalized_block_hash = b"\x56" * 32
        safe_block_hash = b"\x58" * 32
        suggested_fee_recipient = b"\x78" * 20

        # Mock execution_engine
        class TestEngine(spec.NoopExecutionEngine):
            def notify_forkchoice_updated(
                self,
                head_block_hash,
                safe_block_hash,
                finalized_block_hash,
                payload_attributes,
            ) -> Optional[spec.PayloadId]:
                return SAMPLE_PAYLOAD_ID

        payload_id = spec.prepare_execution_payload(
            state=state,
            safe_block_hash=safe_block_hash,
            finalized_block_hash=finalized_block_hash,
            suggested_fee_recipient=suggested_fee_recipient,
            execution_engine=TestEngine(),
            pow_chain=pow_chain.to_dict(),
        )
        assert payload_id == result_payload_id

        # Restore config
        spec.config = old_config
