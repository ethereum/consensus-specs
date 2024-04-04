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
    def hardcoded_custom_type_dep_constants(cls, spec_object) -> Dict[str, str]:
        return {
            'FIELD_ELEMENTS_PER_CELL': spec_object.preset_vars['FIELD_ELEMENTS_PER_CELL'].value,
            'FIELD_ELEMENTS_PER_EXT_BLOB': spec_object.preset_vars['FIELD_ELEMENTS_PER_EXT_BLOB'].value,
        }
