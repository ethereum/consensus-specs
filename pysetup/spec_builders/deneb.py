from typing import Dict
from .base import BaseSpecBuilder
from ..constants import DENEB


class DenebSpecBuilder(BaseSpecBuilder):
    fork: str = DENEB

    @classmethod
    def imports(cls, preset_name: str):
        return f'''
from eth2spec.capella import {preset_name} as capella
'''

    @classmethod
    def classes(cls):
        return f'''
class BLSFieldElement(bls.Scalar):
    pass


class Polynomial(list):
    def __init__(self, evals: Optional[Sequence[BLSFieldElement]] = None):
        if evals is None:
            evals = [BLSFieldElement(0)] * FIELD_ELEMENTS_PER_BLOB
        if len(evals) != FIELD_ELEMENTS_PER_BLOB:
            raise ValueError("expected FIELD_ELEMENTS_PER_BLOB evals")
        super().__init__(evals)
'''

    @classmethod
    def preparations(cls):
        return '''
T = TypeVar('T')  # For generic function
TPoint = TypeVar('TPoint')  # For generic function. G1 or G2 point.
'''

    @classmethod
    def sundry_functions(cls) -> str:
        return '''
def retrieve_blobs_and_proofs(beacon_block_root: Root) -> Tuple[Sequence[Blob], Sequence[KZGProof]]:
    # pylint: disable=unused-argument
    return [], []
'''

    @classmethod
    def execution_engine_cls(cls) -> str:
        return """
class NoopExecutionEngine(ExecutionEngine):

    def notify_new_payload(self: ExecutionEngine,
                           execution_payload: ExecutionPayload,
                           parent_beacon_block_root: Root) -> bool:
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
                            parent_beacon_block_root: Root) -> bool:
        return True

    def is_valid_versioned_hashes(self: ExecutionEngine, new_payload_request: NewPayloadRequest) -> bool:
        return True

    def verify_and_notify_new_payload(self: ExecutionEngine,
                                      new_payload_request: NewPayloadRequest) -> bool:
        return True


EXECUTION_ENGINE = NoopExecutionEngine()"""


    @classmethod
    def hardcoded_func_dep_presets(cls, spec_object) -> Dict[str, str]:
        return {
            'KZG_COMMITMENT_INCLUSION_PROOF_DEPTH': spec_object.preset_vars['KZG_COMMITMENT_INCLUSION_PROOF_DEPTH'].value,
        }
