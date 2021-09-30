from enum import Enum
from eth_utils import encode_hex

from eth2spec.test.exceptions import BlockNotFoundException


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


def with_mock_engine_prepare_payload(spec,
                                     parent_hash,
                                     timestamp,
                                     random,
                                     fee_recipient,
                                     payload_id,
                                     func,
                                     test_steps):
    def prepare_payload(parent_hash,
                        timestamp,
                        random,
                        fee_recipient):
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
            'block_production': {
                'prepare_execution_payload': {
                    'engine_api': {
                        'request': req,
                        'response': resp
                    }
                }
            }
        })
        # FIXME: remove debugging msgs
        print('req', req)
        print('resp', resp)
        return payload_id

    prepare_payload_backup = spec.EXECUTION_ENGINE.prepare_payload
    spec.EXECUTION_ENGINE.prepare_payload = prepare_payload

    class AtomicBoolean():
        value = False
    is_called = AtomicBoolean()

    def wrap(flag: AtomicBoolean):
        func()
        flag.value = True

    try:
        wrap(is_called)
    finally:
        spec.EXECUTION_ENGINE.prepare_payload = prepare_payload_backup
    assert is_called.value


def with_pow_blocks_and_execute_payload(
    spec,
    pow_chain,
    payload,
    status,
    func,
    test_steps
):
    def get_pow_block(block_hash):
        for block in pow_chain:  # type: ignore
            if block.block_hash == block_hash:
                return block
        raise BlockNotFoundException()

    class TestEngine(spec.NoopExecutionEngine):
        def execute_payload(self, execution_payload):
            req = to_json_rpc_request(
                method='engine_executePayload',
                params={
                    "parentHash": encode_hex(payload.parent_hash),
                    "coinbase": encode_hex(payload.coinbase),
                    "stateRoot": encode_hex(payload.state_root),
                    "receiptRoot": encode_hex(payload.receipt_root),
                    "logsBloom": encode_hex(payload.logs_bloom),
                    "random": encode_hex(payload.random),
                    "blockNumber": int(payload.block_number),
                    "gasLimit": int(payload.gas_limit),
                    "gasUsed": int(payload.gas_used),
                    "timestamp": int(payload.timestamp),
                    "extraData": encode_hex(payload.extra_data),
                    "baseFeePerGas": int.from_bytes(payload.base_fee_per_gas, byteorder='little'),
                    "blockHash": encode_hex(payload.block_hash),
                    "transactions": [encode_hex(tx) for tx in payload.transactions],
                }
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
            # FIXME: remove debugging msgs
            print('req', req)
            print('resp', resp)
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
