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
    def hardcoded_custom_type_dep_constants(cls, spec_object) -> Dict[str, str]:
        return {
            'BYTES_PER_FIELD_ELEMENT': spec_object.constant_vars['BYTES_PER_FIELD_ELEMENT'].value,
            'FIELD_ELEMENTS_PER_BLOB': spec_object.preset_vars['FIELD_ELEMENTS_PER_BLOB'].value,
            'MAX_BLOBS_PER_BLOCK': spec_object.preset_vars['MAX_BLOBS_PER_BLOCK'].value,
            'MAX_BLOB_COMMITMENTS_PER_BLOCK': spec_object.preset_vars['MAX_BLOB_COMMITMENTS_PER_BLOCK'].value,
        }

    @classmethod
    def hardcoded_func_dep_presets(cls, spec_object) -> Dict[str, str]:
        return {
            'KZG_COMMITMENT_INCLUSION_PROOF_DEPTH': spec_object.preset_vars['KZG_COMMITMENT_INCLUSION_PROOF_DEPTH'].value,
        }
