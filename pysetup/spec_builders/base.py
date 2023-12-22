from abc import ABC, abstractmethod
from typing import Sequence, Dict
from pathlib import Path

class BaseSpecBuilder(ABC):
    @property
    @abstractmethod
    def fork(self) -> str:
        raise NotImplementedError()

    @classmethod
    def imports(cls, preset_name: str) -> str:
        """
        Import objects from other libraries.
        """
        return ""

    @classmethod
    def preparations(cls) -> str:
        """
        Define special types/constants for building pyspec or call functions.
        """
        return ""

    @classmethod
    def sundry_functions(cls) -> str:
        """
        The functions that are (1) defined abstractly in specs or (2) adjusted for getting better performance.
        """
        return ""

    @classmethod
    def execution_engine_cls(cls) -> str:
        return ""

    @classmethod
    def hardcoded_ssz_dep_constants(cls) -> Dict[str, str]:
        """
        The constants that are required for SSZ objects.
        """
        return {}

    @classmethod
    def hardcoded_custom_type_dep_constants(cls, spec_object) -> Dict[str, str]:  # TODO
        """
        The constants that are required for custom types.
        """
        return {}

    @classmethod
    def hardcoded_func_dep_presets(cls, spec_object) -> Dict[str, str]:
        return {}

    @classmethod
    def implement_optimizations(cls, functions: Dict[str, str]) -> Dict[str, str]:
        return functions
