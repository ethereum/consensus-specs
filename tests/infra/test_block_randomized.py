"""
Unit tests for the block_randomized module.
"""

import pytest

from eth2spec.test.utils.randomized_block_tests import random_block
from tests.infra.block_randomized import (
    DEFAULT_SEED,
    ForkConfig,
    RandomizedTestGenerator,
    scenario_to_id_string,
    ScenarioGenerator,
    ScenarioRenderer,
    transition_to_id_string,
)


class TestTransitionToIdString:
    """Tests for transition_to_id_string helper."""

    def test_basic_transition(self) -> None:
        transition = {
            "epochs_to_skip": 0,
            "slots_to_skip": 0,
            "block_producer": "no_block",
            "validation": "no_op_validation",
        }
        result = transition_to_id_string(transition)
        assert result == "epochs:0,slots:0,with-block:no_block"

    def test_transition_with_function_name(self) -> None:
        transition = {
            "epochs_to_skip": 1,
            "slots_to_skip": "random_slot_in_epoch",
            "block_producer": "random_block",
            "validation": "no_op_validation",
        }
        result = transition_to_id_string(transition)
        assert result == "epochs:1,slots:random_slot_in_epoch,with-block:random_block"


class TestScenarioToIdString:
    """Tests for scenario_to_id_string helper."""

    def test_single_transition(self) -> None:
        scenario = {
            "transitions": [
                {
                    "epochs_to_skip": 0,
                    "slots_to_skip": 0,
                    "block_producer": "no_block",
                    "validation": "no_op_validation",
                }
            ],
            "state_randomizer": "randomize_state",
        }
        result = scenario_to_id_string(scenario)
        assert result == "epochs:0,slots:0,with-block:no_block"

    def test_multiple_transitions(self) -> None:
        scenario = {
            "transitions": [
                {
                    "epochs_to_skip": 0,
                    "slots_to_skip": 0,
                    "block_producer": "no_block",
                    "validation": "validate_is_not_leaking",
                },
                {
                    "epochs_to_skip": 1,
                    "slots_to_skip": 0,
                    "block_producer": "random_block",
                    "validation": "no_op_validation",
                },
            ],
            "state_randomizer": "randomize_state",
        }
        result = scenario_to_id_string(scenario)
        expected = "epochs:0,slots:0,with-block:no_block|epochs:1,slots:0,with-block:random_block"
        assert result == expected


class TestForkConfig:
    """Tests for ForkConfig dataclass."""

    def test_creation(self) -> None:
        def dummy_state_randomizer() -> None:
            pass

        def dummy_block_randomizer() -> None:
            pass

        config = ForkConfig(
            name="test_fork",
            state_randomizer=dummy_state_randomizer,
            block_randomizer=dummy_block_randomizer,
        )
        assert config.name == "test_fork"
        assert config.state_randomizer == dummy_state_randomizer
        assert config.block_randomizer == dummy_block_randomizer


class TestScenarioGenerator:
    """Tests for ScenarioGenerator class."""

    def test_deterministic_output(self) -> None:
        """Verify same seed produces same scenarios."""
        gen1 = ScenarioGenerator(block_randomizer=random_block, seed=DEFAULT_SEED)
        gen2 = ScenarioGenerator(block_randomizer=random_block, seed=DEFAULT_SEED)

        scenarios1 = gen1.generate()
        scenarios2 = gen2.generate()

        assert len(scenarios1) == len(scenarios2)
        # Compare the structure (not deep equality since dicts may have callables)
        assert len(scenarios1[0]["transitions"]) == len(scenarios2[0]["transitions"])

    def test_different_seeds_produce_different_output(self) -> None:
        """Verify different seeds produce different scenarios."""
        gen1 = ScenarioGenerator(block_randomizer=random_block, seed=1)
        gen2 = ScenarioGenerator(block_randomizer=random_block, seed=2)

        scenarios1 = gen1.generate()
        scenarios2 = gen2.generate()

        # The scenarios should have different orderings
        # Compare by converting to id strings after normalizing callables
        def scenario_key(s: dict) -> str:
            return str(
                [(t.get("epochs_to_skip"), t.get("slots_to_skip")) for t in s["transitions"]]
            )

        keys1 = [scenario_key(s) for s in scenarios1]
        keys2 = [scenario_key(s) for s in scenarios2]
        assert keys1 != keys2

    def test_generates_expected_number_of_scenarios(self) -> None:
        """Verify the number of generated scenarios."""
        gen = ScenarioGenerator(block_randomizer=random_block, seed=DEFAULT_SEED)
        scenarios = gen.generate()

        # 2 leak transitions * 8 block transition combinations = 16 scenarios
        assert len(scenarios) == 16


class TestScenarioRenderer:
    """Tests for ScenarioRenderer class."""

    def test_render_includes_imports(self) -> None:
        renderer = ScenarioRenderer(
            fork_name="phase0",
            state_randomizer_name="randomize_state",
        )
        scenarios: list[dict] = [
            {
                "transitions": [
                    {
                        "epochs_to_skip": 0,
                        "slots_to_skip": 0,
                        "block_producer": "no_block",
                        "validation": "no_op_validation",
                    }
                ]
            }
        ]
        result = renderer.render(scenarios)

        assert "from eth2spec.test.helpers.constants import PHASE0" in result
        assert "run_generated_randomized_test" in result

    def test_render_includes_test_function(self) -> None:
        renderer = ScenarioRenderer(
            fork_name="altair",
            state_randomizer_name="randomize_state_altair",
        )
        scenarios: list[dict] = [
            {
                "transitions": [
                    {
                        "epochs_to_skip": 0,
                        "slots_to_skip": 0,
                        "block_producer": "no_block",
                        "validation": "no_op_validation",
                    }
                ]
            }
        ]
        result = renderer.render(scenarios)

        assert "def test_randomized_0(spec, state):" in result
        assert "@with_phases([ALTAIR])" in result


class TestRandomizedTestGenerator:
    """Tests for RandomizedTestGenerator class."""

    def test_available_forks(self) -> None:
        forks = RandomizedTestGenerator.available_forks()
        assert "phase0" in forks
        assert "altair" in forks
        assert "fulu" in forks
        assert "gloas" in forks
        assert len(forks) == 8

    def test_invalid_fork_raises(self) -> None:
        with pytest.raises(ValueError, match="Unknown fork"):
            RandomizedTestGenerator("invalid_fork")

    def test_generate_returns_string(self) -> None:
        gen = RandomizedTestGenerator("phase0")
        result = gen.generate()
        assert isinstance(result, str)
        assert "test_randomized_0" in result

    def test_generate_scenarios_returns_list(self) -> None:
        gen = RandomizedTestGenerator("phase0")
        scenarios = gen.generate_scenarios()
        assert isinstance(scenarios, list)
        assert len(scenarios) == 16
        assert "transitions" in scenarios[0]
