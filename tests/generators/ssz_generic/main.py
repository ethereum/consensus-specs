from typing import Iterable
from eth2spec.gen_helpers.gen_base import gen_runner, gen_typing
import ssz_basic_progressivelist
import ssz_basic_vector
import ssz_bitlist
import ssz_bitvector
import ssz_boolean
import ssz_uints
import ssz_container
import ssz_stablecontainer
import ssz_profile
from eth2spec.test.helpers.constants import PHASE0


def create_provider(handler_name: str, suite_name: str, case_maker) -> gen_typing.TestProvider:

    def prepare_fn() -> None:
        return

    def cases_fn() -> Iterable[gen_typing.TestCase]:
        for case_name, case_fn in case_maker():
            yield gen_typing.TestCase(
                fork_name=PHASE0,
                preset_name="general",
                runner_name="ssz_generic",
                handler_name=handler_name,
                suite_name=suite_name,
                case_name=case_name,
                case_fn=case_fn,
            )

    return gen_typing.TestProvider(prepare=prepare_fn, make_cases=cases_fn)


if __name__ == "__main__":
    gen_runner.run_generator(
        "ssz_generic",
        [
            create_provider(
                "basic_progressivelist", "valid", ssz_basic_progressivelist.valid_cases
            ),
            create_provider(
                "basic_progressivelist", "invalid", ssz_basic_progressivelist.invalid_cases
            ),
            create_provider("basic_vector", "valid", ssz_basic_vector.valid_cases),
            create_provider("basic_vector", "invalid", ssz_basic_vector.invalid_cases),
            create_provider("bitlist", "valid", ssz_bitlist.valid_cases),
            create_provider("bitlist", "invalid", ssz_bitlist.invalid_cases),
            create_provider("bitvector", "valid", ssz_bitvector.valid_cases),
            create_provider("bitvector", "invalid", ssz_bitvector.invalid_cases),
            create_provider("boolean", "valid", ssz_boolean.valid_cases),
            create_provider("boolean", "invalid", ssz_boolean.invalid_cases),
            create_provider("containers", "valid", ssz_container.valid_cases),
            create_provider("containers", "invalid", ssz_container.invalid_cases),
            create_provider("profiles", "valid", ssz_profile.valid_cases),
            create_provider("profiles", "invalid", ssz_profile.invalid_cases),
            create_provider("stablecontainers", "valid", ssz_stablecontainer.valid_cases),
            create_provider("stablecontainers", "invalid", ssz_stablecontainer.invalid_cases),
            create_provider("uints", "valid", ssz_uints.valid_cases),
            create_provider("uints", "invalid", ssz_uints.invalid_cases),
        ],
    )
