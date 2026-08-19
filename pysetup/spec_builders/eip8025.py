from pysetup.constants import EIP8025

from .base import BaseSpecBuilder


class EIP8025SpecBuilder(BaseSpecBuilder):
    fork: str = EIP8025

    @classmethod
    def imports(cls, preset_name: str):
        return f"""
from eth_consensus_specs.gloas import {preset_name} as gloas
"""

    @classmethod
    def preparations(cls) -> str:
        return """
EIP8025_FEATURES = {
    "prover": {
        "tag": "eip8025-prover",
        "status": "optional",
    },
}
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
                                  payload_attributes: Optional[PayloadAttributes],
                                  custody_columns: Optional[CustodyColumnBits]) -> Optional[PayloadId]:
        pass

    def get_payload(self: ExecutionEngine, payload_id: PayloadId) -> GetPayloadResponse:
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
"""

    @classmethod
    def proof_engine_cls(cls) -> str:
        return """
class NoopProofEngine(ProofEngine):

    def verify_execution_proof(self: ProofEngine,
                               execution_proof: ExecutionProof,
                               chain_config_root: Root) -> bool:
        return False

    def request_proof(self: ProofEngine,
                      private_input: PrivateInput,
                      proof_type: ProofType) -> Root:
        raise NotImplementedError("no default proof generation")

    def get_proof(self: ProofEngine,
                  beacon_block_root: Root,
                  proof_type: ProofType) -> ExecutionProof:
        raise NotImplementedError("no default proof retrieval")


PROOF_ENGINE = NoopProofEngine()"""
