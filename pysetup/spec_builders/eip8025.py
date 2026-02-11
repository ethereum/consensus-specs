from ..constants import EIP8025
from .base import BaseSpecBuilder


class EIP8025SpecBuilder(BaseSpecBuilder):
    fork: str = EIP8025

    @classmethod
    def imports(cls, preset_name: str):
        return f"""
from eth2spec.fulu import {preset_name} as fulu
"""

    @classmethod
    def execution_engine_cls(cls) -> str:
        return """
class NoopExecutionEngine(ExecutionEngine):

    def notify_new_payload(self: ExecutionEngine,
                           execution_payload: ExecutionPayload,
                           parent_beacon_block_root: Root,
                           execution_requests_list: Sequence[bytes]) -> bool:
        return True

    def notify_forkchoice_updated(self: ExecutionEngine,
                                  head_block_hash: Hash32,
                                  safe_block_hash: Hash32,
                                  finalized_block_hash: Hash32,
                                  payload_attributes: Optional[PayloadAttributes]) -> Optional[PayloadId]:
        pass

    def get_payload(self: ExecutionEngine, payload_id: PayloadId) -> GetPayloadResponse:
        # pylint: disable=unused-argument
        raise NotImplementedError("no default block production")

    def is_valid_block_hash(self: ExecutionEngine,
                            execution_payload: ExecutionPayload,
                            parent_beacon_block_root: Root,
                            execution_requests_list: Sequence[bytes]) -> bool:
        return True

    def is_valid_versioned_hashes(self: ExecutionEngine, new_payload_request: NewPayloadRequest) -> bool:
        return True

    def verify_and_notify_new_payload(self: ExecutionEngine,
                                      new_payload_request: NewPayloadRequest) -> bool:
        return True


EXECUTION_ENGINE = NoopExecutionEngine()


class NoopProofEngine(ProofEngine):

    def verify_execution_proof(self: ProofEngine,
                               execution_proof: ExecutionProof) -> bool:
        return True

    def verify_new_payload_request_header(self: ProofEngine,
                                          new_payload_request_header: NewPayloadRequestHeader) -> bool:
        return True

    def request_proofs(self: ProofEngine,
                       new_payload_request: NewPayloadRequest,
                       proof_attributes: ProofAttributes) -> ProofGenId:
        # pylint: disable=unused-argument
        raise NotImplementedError("no default proof generation")


PROOF_ENGINE = NoopProofEngine()"""
