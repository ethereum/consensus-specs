from eth_utils import to_tuple
from typing import Iterable

from eth2spec.gen_helpers.gen_base import gen_runner, gen_typing
from eth2spec.test.helpers.typing import PresetBaseName

from eth2spec.phase0 import mainnet as spec_mainnet, minimal as spec_minimal
from eth2spec.test.helpers.constants import PHASE0, MINIMAL, MAINNET


def shuffling_case_fn(spec, seed, count):
    yield 'mapping', 'data', {
        'seed': '0x' + seed.hex(),
        'count': count,
        'mapping': [int(spec.compute_shuffled_index(i, count, seed)) for i in range(count)]
    }


def shuffling_case(spec, seed, count):
    return f'shuffle_0x{seed.hex()}_{count}', lambda: shuffling_case_fn(spec, seed, count)


@to_tuple
def shuffling_test_cases(spec):
    for seed in [spec.hash(seed_init_value.to_bytes(length=4, byteorder='little')) for seed_init_value in range(30)]:
        for count in [0, 1, 2, 3, 5, 10, 33, 100, 1000, 9999]:
            yield shuffling_case(spec, seed, count)


def create_provider(preset_name: PresetBaseName) -> gen_typing.TestProvider:

    def prepare_fn() -> None:
        return

    def cases_fn() -> Iterable[gen_typing.TestCase]:
        if preset_name == MAINNET:
            spec = spec_mainnet
        elif preset_name == MINIMAL:
            spec = spec_minimal
        else:
            raise Exception(f"unrecognized preset: {preset_name}")
        for (case_name, case_fn) in shuffling_test_cases(spec):
            yield gen_typing.TestCase(
                fork_name=PHASE0,
                preset_name=preset_name,
                runner_name='shuffling',
                handler_name='core',
                suite_name='shuffle',
                case_name=case_name,
                case_fn=case_fn
            )

    return gen_typing.TestProvider(prepare=prepare_fn, make_cases=cases_fn)


if __name__ == "__main__":
    gen_runner.run_generator("shuffling", [create_provider(MINIMAL), create_provider(MAINNET)])
