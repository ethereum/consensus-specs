from abc import ABC, abstractmethod


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
    def classes(cls) -> str:
        """
        Define special classes.
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
    def hardcoded_ssz_dep_constants(cls) -> dict[str, str]:
        """
        The constants that are required for SSZ objects.
        """
        return {}

    @classmethod
    def hardcoded_func_dep_presets(cls, spec_object) -> dict[str, str]:
        return {}

    @classmethod
    def implement_optimizations(cls, functions: dict[str, str]) -> dict[str, str]:
        return functions

    @classmethod
    def deprecate_constants(cls) -> set[str]:
        return set()

    @classmethod
    def deprecate_presets(cls) -> set[str]:
        return set()
