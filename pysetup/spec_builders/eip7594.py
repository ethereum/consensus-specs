from typing import Dict

from .base import BaseSpecBuilder
from ..constants import EIP7594


class EIP7594SpecBuilder(BaseSpecBuilder):
    fork: str = EIP7594

    @classmethod
    def imports(cls, preset_name: str):
        return f'''
from eth2spec.deneb import {preset_name} as deneb
'''
    

    @classmethod
    def sundry_functions(cls) -> str:
        return """
def retrieve_column_sidecars(beacon_block_root: Root) -> Sequence[DataColumnSidecar]:
    return []
"""

    @classmethod
    def hardcoded_custom_type_dep_constants(cls, spec_object) -> str:
        return {
            'FIELD_ELEMENTS_PER_CELL': spec_object.preset_vars['FIELD_ELEMENTS_PER_CELL'].value,
            'FIELD_ELEMENTS_PER_EXT_BLOB': spec_object.preset_vars['FIELD_ELEMENTS_PER_EXT_BLOB'].value,
            'NUMBER_OF_COLUMNS': spec_object.config_vars['NUMBER_OF_COLUMNS'].value,
            'MAX_CELLS_IN_EXTENDED_MATRIX': spec_object.config_vars['MAX_CELLS_IN_EXTENDED_MATRIX'].value,
        }

    @classmethod
    def hardcoded_func_dep_presets(cls, spec_object) -> Dict[str, str]:
        return {
            'KZG_COMMITMENTS_INCLUSION_PROOF_DEPTH': spec_object.preset_vars['KZG_COMMITMENTS_INCLUSION_PROOF_DEPTH'].value,
        }
