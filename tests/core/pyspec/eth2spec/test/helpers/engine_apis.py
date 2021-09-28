from eth_utils import encode_hex


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
        test_steps.append({'engine_api': {
            'request': req,
            'response': resp
        }})
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
        spec.EXECUTION_ENGINE.get_pow_block = prepare_payload_backup
    assert is_called.value
