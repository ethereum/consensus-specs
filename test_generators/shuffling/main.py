from eth2spec.phase0 import spec as spec
from eth_utils import to_tuple
from gen_base import gen_runner, gen_typing
from preset_loader import loader
from typing import Iterable


def shuffling_case_fn(seed, count):
    yield 'mapping', 'data', {
        'seed': '0x' + seed.hex(),
        'count': count,
        'mapping': [int(spec.compute_shuffled_index(i, count, seed)) for i in range(count)]
    }


def shuffling_case(seed, count):
    return f'shuffle_0x{seed.hex()}_{count}', lambda: shuffling_case_fn(seed, count)


@to_tuple
def shuffling_test_cases():
    for seed in [spec.hash(seed_init_value.to_bytes(length=4, byteorder='little')) for seed_init_value in range(30)]:
        for count in [0, 1, 2, 3, 5, 10, 33, 100, 1000, 9999]:
            yield shuffling_case(seed, count)


def create_provider(config_name: str) -> gen_typing.TestProvider:

    def prepare_fn(configs_path: str) -> str:
        presets = loader.load_presets(configs_path, config_name)
        spec.apply_constants_preset(presets)
        return config_name

    def cases_fn() -> Iterable[gen_typing.TestCase]:
        for (case_name, case_fn) in shuffling_test_cases():
            yield gen_typing.TestCase(
                fork_name='phase0',
                runner_name='shuffling',
                handler_name='core',
                suite_name='shuffle',
                case_name=case_name,
                case_fn=case_fn
            )

    return gen_typing.TestProvider(prepare=prepare_fn, make_cases=cases_fn)


if __name__ == "__main__":
    gen_runner.run_generator("shuffling", [create_provider("minimal"), create_provider("mainnet")])
