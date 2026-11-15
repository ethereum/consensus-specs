import random
from pathlib import Path

import pytest
from ruamel.yaml import YAML

from .instantiators import test_case

CONFIG_DIR = Path(__file__).parent


@pytest.mark.parametrize(("initial_seed", "nr_variations"), [(1, 64), (5548, 4), (0, 1)])
def test_variation_seeds_unique_and_reproducible(initial_seed, nr_variations):
    seeds = test_case.generate_variation_seeds(initial_seed, nr_variations)

    assert len(seeds) == len(set(seeds)) == nr_variations
    assert seeds[0] == initial_seed
    assert all(1 <= seed <= 10000 for seed in seeds[1:])
    assert seeds == test_case.generate_variation_seeds(initial_seed, nr_variations)


@pytest.mark.parametrize(
    ("initial_seed", "nr_variations"),
    [(1, 10000), (10000, 10000), (0, 10001), (10001, 10001)],
)
def test_variation_seed_capacity(initial_seed, nr_variations):
    seeds = test_case.generate_variation_seeds(initial_seed, nr_variations)

    assert seeds[0] == initial_seed
    assert len(seeds) == nr_variations
    assert set(seeds) == set(range(1, 10001)) | {initial_seed}


@pytest.mark.parametrize(
    ("initial_seed", "nr_variations"),
    [(1, 0), (1, -1), (1, 10001), (0, 10002), (10001, 10002)],
)
def test_invalid_variation_count(initial_seed, nr_variations):
    with pytest.raises(ValueError, match="nr_variations must be between 1 and"):
        test_case.generate_variation_seeds(initial_seed, nr_variations)


def test_variation_case_names_unique():
    config_dir = CONFIG_DIR / "standard"
    params = YAML(typ="safe").load(config_dir / "test_gen.yaml")["block_weight_test"]
    params["seed"] = 1
    groups = list(test_case.enumerate_mutation_groups(config_dir, "block_weight_test", params))

    for solution_index in {group.solution_index for group in groups}:
        seeds = [
            group.test_dna_base.variation_seed
            for group in groups
            if group.solution_index == solution_index
        ]
        assert len(seeds) == len(set(seeds)) == 64

    case_names = [
        case_name
        for group in groups
        for chunk in test_case.split_mutation_group(group)
        for case_name, _ in test_case.enumerate_test_dnas(group, chunk)
    ]
    assert len(case_names) == len(set(case_names)) == 2048


@pytest.mark.parametrize("config_name", ["tiny", "small", "standard"])
def test_default_variation_case_names_unchanged(config_name):
    config_dir = CONFIG_DIR / config_name
    config = YAML(typ="safe").load(config_dir / "test_gen.yaml")
    for test_name, params in config.items():
        # Reproduce the historical sequence, including its overwritten first draw.
        rnd = random.Random(params["seed"])
        seeds = [rnd.randint(1, 10000) for _ in range(params["nr_variations"])]
        seeds[0] = params["seed"]
        assert len(seeds) == len(set(seeds))

        groups = list(test_case.enumerate_mutation_groups(config_dir, test_name, params))
        solutions = YAML(typ="safe").load(config_dir / params["instances"])
        expected_names = [
            f"{test_name}_{i}_{test_case.derive_effective_seed(seed, i)}_{case_id}"
            for i in range(len(solutions))
            for seed in seeds
            for case_id in range(params["nr_mutations"] + 1)
        ]
        actual_names = [
            case_name
            for group in groups
            for chunk in test_case.split_mutation_group(group)
            for case_name, _ in test_case.enumerate_test_dnas(group, chunk)
        ]
        assert actual_names == expected_names
        if test_name == "block_weight_test":
            assert actual_names[0] == "block_weight_test_0_466812698_0"
