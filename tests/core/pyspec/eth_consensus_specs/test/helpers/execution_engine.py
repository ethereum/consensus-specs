from eth_consensus_specs.test.helpers.execution_payload import (
    compute_el_block_hash_with_new_fields,
    compute_requests_hash,
)
from eth_consensus_specs.test.helpers.forks import is_post_deneb, is_post_electra


def get_test_execution_engine(spec):
    """
    Return the execution engine which tests use by default.
    """

    class TestExecutionEngine(spec.NoopExecutionEngine):
        def is_valid_block_hash(
            self,
            execution_payload,
            parent_beacon_block_root=None,
            execution_requests_list=None,
        ) -> bool:
            requests_hash = None
            if is_post_electra(spec):
                requests_hash = compute_requests_hash(execution_requests_list)
            expected_block_hash = compute_el_block_hash_with_new_fields(
                spec, execution_payload, parent_beacon_block_root, requests_hash
            )
            return execution_payload.block_hash == expected_block_hash

        def verify_and_notify_new_payload(self, new_payload_request) -> bool:
            args = [new_payload_request.execution_payload]
            if is_post_deneb(spec):
                args.append(new_payload_request.parent_beacon_block_root)
            if is_post_electra(spec):
                requests = new_payload_request.execution_requests
                requests_list = spec.get_execution_requests_list(requests)
                args.append(requests_list)
            if not self.is_valid_block_hash(*args):
                return False
            return super().verify_and_notify_new_payload(new_payload_request)

    return TestExecutionEngine()
