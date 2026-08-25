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
    def proof_engine_cls(cls) -> str:
        return """
class NoopProofEngine(ProofEngine):

    def verify_execution_proof(self: ProofEngine,
                               execution_proof: ExecutionProof) -> bool:
        return False

    def request_proofs(self: ProofEngine,
                       new_payload_request: NewPayloadRequest,
                       proof_attributes: ProofAttributes) -> None:
        raise NotImplementedError("no default proof generation")

    def get_proof(self: ProofEngine,
                  new_payload_request_root: Root,
                  proof_type: ProofType) -> ProofData:
        raise NotImplementedError("no default proof retrieval")


PROOF_ENGINE = NoopProofEngine()"""
