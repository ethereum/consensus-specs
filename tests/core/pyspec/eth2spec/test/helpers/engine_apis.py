from enum import Enum
from eth_utils import encode_hex

from eth2spec.test.exceptions import BlockNotFoundException
from eth2spec.test.helpers.execution_payload import (
    build_execution_payload,
)
from eth2spec.test.helpers.fork_choice import (
    get_pow_block_file_name,
)


class StatusCode(Enum):
    VALID = "VALID"
    INVALID = "INVALID"
    SYNCING = "SYNCING"


def to_json_rpc_request(method, params):
    return {
        'method': method,
        'params': params,
    }


def to_json_rpc_response(result, error=False):
    return {
        'error': error,
        'result': result,
    }


def execution_payload_to_json(execution_payload):
    return {
        "parentHash": encode_hex(execution_payload.parent_hash),
        "coinbase": encode_hex(execution_payload.coinbase),
        "stateRoot": encode_hex(execution_payload.state_root),
        "receiptRoot": encode_hex(execution_payload.receipt_root),
        "logsBloom": encode_hex(execution_payload.logs_bloom),
        "random": encode_hex(execution_payload.random),
        "blockNumber": int(execution_payload.block_number),
        "gasLimit": int(execution_payload.gas_limit),
        "gasUsed": int(execution_payload.gas_used),
        "timestamp": int(execution_payload.timestamp),
        "extraData": encode_hex(execution_payload.extra_data),
        "baseFeePerGas": int.from_bytes(execution_payload.base_fee_per_gas, byteorder='little'),
        "blockHash": encode_hex(execution_payload.block_hash),
        "transactions": [encode_hex(tx) for tx in execution_payload.transactions],
    }


def run_prepare_execution_payload_with_mock_engine_prepare_payload(
        spec,
        state,
        pow_chain,
        parent_hash,
        timestamp,
        random,
        fee_recipient,
        payload_id,
        test_steps,
        dump_rpc=False):
    class TestEngine(spec.NoopExecutionEngine):
        def prepare_payload(self,
                            parent_hash,
                            timestamp,
                            random,
                            fee_recipient):
            if dump_rpc:
                req = to_json_rpc_request(
                    method='engine_preparePayload',
                    params={
                        "parentHash": encode_hex(parent_hash),
                        "timestamp": int(timestamp),
                        "random": encode_hex(random),
                        "feeRecipient": encode_hex(fee_recipient),
                    }
                )
                resp = to_json_rpc_response(
                    result={
                        "payloadId": int(payload_id)
                    },
                )
                test_steps.append({
                    '_block_production': {
                        'prepare_execution_payload': {
                            'engine_api': {
                                'request': req,
                                'response': resp
                            }
                        }
                    }
                })
            return payload_id

    return spec.prepare_execution_payload(
        state=state,
        pow_chain=pow_chain,
        fee_recipient=fee_recipient,
        execution_engine=TestEngine(),
    )


def run_get_execution_payload_with_mock_engine_get_payload(
        spec,
        state,
        payload_id,
        parent_hash,
        fee_recipient,
        test_steps,
        dump_rpc=False):
    timestamp = spec.compute_timestamp_at_slot(state, state.slot + 1)
    random = spec.get_randao_mix(state, spec.get_current_epoch(state))

    class TestEngine(spec.NoopExecutionEngine):
        def get_payload(self, payload_id):
            execution_payload = build_execution_payload(
                spec,
                state,
                parent_hash=parent_hash,
                timestamp=timestamp,
                random=random,
                coinbase=fee_recipient,
            )
            if dump_rpc:
                req = to_json_rpc_request(
                    method='engine_getPayload',
                    params={
                        "payloadId": int(payload_id)
                    },
                )
                resp = to_json_rpc_response(
                    result={
                        "executionPayload": execution_payload_to_json(execution_payload),
                    },
                )
                test_steps.append({
                    '_block_production': {
                        'get_execution_payload': {
                            'engine_api': {
                                'request': req,
                                'response': resp
                            }
                        }
                    }
                })
            return execution_payload

    return spec.get_execution_payload(payload_id, TestEngine())


def with_pow_blocks_and_execute_payload(
    spec,
    pow_chain,
    status,
    func,
    test_steps
):
    def get_pow_block(block_hash):
        for block in pow_chain:  # type: ignore
            if block.block_hash == block_hash:
                test_steps.append({
                    '_to_next_on_block': {
                        'get_pow_block': {
                            'input': {
                                'pow_chain': [get_pow_block_file_name(pow_block) for pow_block in pow_chain]
                            },
                            'output': {
                                'result': get_pow_block_file_name(block),
                            },
                        }
                    }
                })
                return block
        raise BlockNotFoundException()

    class TestEngine(spec.NoopExecutionEngine):
        def execute_payload(self, execution_payload):
            req = to_json_rpc_request(
                method='engine_executePayload',
                params=execution_payload_to_json(execution_payload),
            )
            resp = to_json_rpc_response(
                result={
                    "status": status.value
                },
            )
            test_steps.append({
                '_to_next_on_block': {
                    'process_execution_payload': {
                        'engine_api': {
                            'request': req,
                            'response': resp
                        }
                    }
                }
            })
            return status == StatusCode.VALID

    # Spec stub replacement
    get_pow_block_backup = spec.get_pow_block
    spec.get_pow_block = get_pow_block

    execute_engine_backup = spec.EXECUTION_ENGINE
    spec.EXECUTION_ENGINE = TestEngine()

    class AtomicBoolean():
        value = False
    is_called = AtomicBoolean()

    def wrap(flag: AtomicBoolean):
        yield from func()
        flag.value = True

    try:
        yield from wrap(is_called)
    finally:
        # Revert replacement
        spec.get_pow_block = get_pow_block_backup
        spec.EXECUTION_ENGINE = execute_engine_backup
    assert is_called.value
