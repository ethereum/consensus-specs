"""
Implementation of the randomized block test generator.

This module generates randomized test scenarios for Ethereum consensus layer
testing. It produces Python test files that exercise state transitions with
various combinations of epoch/slot skips, block production, and leak states.

How to run (from project root):
    # Regenerate all random test files (default behavior)
    .venv/bin/python -m tests.infra.block_randomized

    # Then format with ruff
    .venv/bin/ruff check --fix tests/core/pyspec/eth2spec/test/*/random/test_random.py
    .venv/bin/ruff format tests/core/pyspec/eth2spec/test/*/random/test_random.py

    # Generate for specific fork only
    .venv/bin/python -m tests.infra.block_randomized --fork phase0

    # Print to stdout instead of writing files
    .venv/bin/python -m tests.infra.block_randomized --stdout

    # List available forks
    .venv/bin/python -m tests.infra.block_randomized --list-forks
"""

from __future__ import annotations

import argparse
import itertools
import sys
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
from random import Random
from typing import Any, ClassVar

from eth2spec.test.helpers.constants import (
    ALTAIR,
    BELLATRIX,
    CAPELLA,
    DENEB,
    ELECTRA,
    FULU,
    GLOAS,
    PHASE0,
)
from eth2spec.test.utils.randomized_block_tests import (
    epoch_transition,
    last_slot_in_epoch,
    no_block,
    no_op_validation,
    penultimate_slot_in_epoch,
    random_block,
    random_block_altair_with_cycling_sync_committee_participation,
    random_block_bellatrix,
    random_block_capella,
    random_block_deneb,
    random_block_electra,
    random_block_fulu,
    random_block_gloas,
    random_slot_in_epoch,
    randomize_state,
    randomize_state_altair,
    randomize_state_bellatrix,
    randomize_state_capella,
    randomize_state_deneb,
    randomize_state_electra,
    randomize_state_fulu,
    randomize_state_gloas,
    slot_transition,
    transition_to_leaking,
    transition_with_random_block,
    transition_without_leak,
)

# Constants
BLOCK_TRANSITIONS_COUNT: int = 2
DEFAULT_SEED: int = 1447
DEFAULT_OUTPUT_DIR: str = "tests/core/pyspec/eth2spec/test"


# Type aliases for transition dicts (preserving original key order)
TransitionDict = dict[str, Any]
ScenarioDict = dict[str, Any]


def transition_to_id_string(transition: TransitionDict) -> str:
    """Generate human-readable ID string for a transition."""
    return ",".join(
        [
            f"epochs:{transition['epochs_to_skip']}",
            f"slots:{transition['slots_to_skip']}",
            f"with-block:{transition['block_producer']}",
        ]
    )


def scenario_to_id_string(scenario: ScenarioDict) -> str:
    """Generate human-readable ID string for a scenario."""
    return "|".join(transition_to_id_string(t) for t in scenario["transitions"])


@dataclass
class ForkConfig:
    """Configuration for a specific fork's test generation."""

    name: str
    state_randomizer: Callable[..., Any]
    block_randomizer: Callable[..., Any]


class ScenarioGenerator:
    """Generates randomized test scenarios using combinatorial logic."""

    def __init__(
        self,
        block_randomizer: Callable[..., Any],
        seed: int = DEFAULT_SEED,
    ) -> None:
        self._block_randomizer = block_randomizer
        self._seed = seed
        self._rng = Random(seed)

    def generate(self) -> list[ScenarioDict]:
        """Generate all randomized scenarios."""
        # Define the sets of transitions to combine
        epochs_set = (
            epoch_transition(n=0),
            epoch_transition(n=1),
        )
        slots_set = (
            slot_transition(last_slot_in_epoch),
            slot_transition(n=0),
            slot_transition(random_slot_in_epoch),
            slot_transition(penultimate_slot_in_epoch),
        )
        blocks_set = (transition_with_random_block(self._block_randomizer),)

        # Generate randomized skip combinations
        all_skips = list(itertools.product(epochs_set, slots_set))
        randomized_skips = (
            self._rng.sample(all_skips, len(all_skips)) for _ in range(BLOCK_TRANSITIONS_COUNT)
        )

        # Build block transitions from combinations
        transitions_generator = (
            itertools.product(prefix, blocks_set) for prefix in randomized_skips
        )
        block_transitions = zip(*transitions_generator)

        # Combine with leak transitions
        leak_transitions = (
            transition_without_leak,
            transition_to_leaking,
        )

        scenarios: list[ScenarioDict] = []
        for combo in itertools.product(leak_transitions, block_transitions):
            transitions = self._flatten_transitions(combo)
            self._normalize_scenarios_in_place(transitions)
            scenarios.append({"transitions": transitions})

        return scenarios

    def _flatten_transitions(self, combo: tuple[Any, ...]) -> list[TransitionDict]:
        """Flatten nested transition structure."""
        leak_transition = combo[0]
        result = [leak_transition]

        for transition_batch in combo[1]:
            for transition in transition_batch:
                if isinstance(transition, tuple):
                    for subtransition in transition:
                        result.append(subtransition)
                else:
                    result.append(transition)

        return result

    def _normalize_scenarios_in_place(self, transitions: list[TransitionDict]) -> None:
        """Normalize transitions in place, matching original key order behavior."""
        for i, transition in enumerate(transitions):
            transitions[i] = self._normalize_transition(transition)

    def _normalize_transition(self, transition: Any) -> TransitionDict:
        """Normalize a transition dict, preserving original key order."""
        if callable(transition):
            transition = transition()

        # Add missing keys in specific order (matching original behavior)
        if "epochs_to_skip" not in transition:
            transition["epochs_to_skip"] = 0
        if "slots_to_skip" not in transition:
            transition["slots_to_skip"] = 0
        if "block_producer" not in transition:
            transition["block_producer"] = no_block
        if "validation" not in transition:
            transition["validation"] = no_op_validation

        return transition


class ScenarioRenderer:
    """Renders scenarios to Python test file content."""

    IMPORTS_TEMPLATE: ClassVar[str] = '''"""
This module is generated from the ``random`` test generator.
Please do not edit this file manually.
See the README for that generator for more information.
"""

from eth2spec.test.helpers.constants import {phase}
from eth2spec.test.context import (
    misc_balances_in_default_range_with_many_validators,
    with_phases,
    zero_activation_threshold,
    only_generator,
)
from eth2spec.test.context import (
    always_bls,
    spec_test,
    with_custom_state,
    single_phase,
)
from eth2spec.test.utils.randomized_block_tests import (
    run_generated_randomized_test,
)'''

    TEST_TEMPLATE: ClassVar[str] = """
@only_generator("randomized test for broad coverage, not point-to-point CI")
@with_phases([{phase}])
@with_custom_state(
    balances_fn=misc_balances_in_default_range_with_many_validators,
    threshold_fn=zero_activation_threshold
)
@spec_test
@single_phase
@always_bls
def test_randomized_{index}(spec, state):
    # scenario as high-level, informal text:
{name_as_comment}
    scenario = {scenario}  # noqa: E501
    yield from run_generated_randomized_test(
        spec,
        state,
        scenario,
    )"""

    def __init__(self, fork_name: str, state_randomizer_name: str) -> None:
        self._fork_name = fork_name
        self._state_randomizer_name = state_randomizer_name

    def render(self, scenarios: list[ScenarioDict]) -> str:
        """Render all scenarios to a complete test file."""
        parts: list[str] = []

        # Add imports
        imports = self.IMPORTS_TEMPLATE.format(phase=self._fork_name.upper())
        parts.append(imports)

        # Add each test
        for index, scenario in enumerate(scenarios):
            scenario["state_randomizer"] = self._state_randomizer_name
            self._convert_callables_to_names(scenario)
            test_code = self._render_test(index, scenario)
            parts.append(test_code)

        return "\n\n".join(parts)

    def _convert_callables_to_names(self, scenario: ScenarioDict) -> None:
        """Convert all callable values to their __name__ strings."""
        for transition in scenario["transitions"]:
            for key, value in transition.items():
                if callable(value):
                    transition[key] = value.__name__

    def _render_test(self, index: int, scenario: ScenarioDict) -> str:
        """Render a single test function."""
        name_comment = self._to_comment(scenario_to_id_string(scenario), indent_level=1)

        return self.TEST_TEMPLATE.format(
            phase=self._fork_name.upper(),
            index=index,
            name_as_comment=name_comment,
            scenario=scenario,
        )

    def _to_comment(self, name: str, indent_level: int) -> str:
        """Convert scenario ID string to comment lines."""
        parts = name.split("|")
        indentation = "    " * indent_level
        return "\n".join(f"{indentation}# {part}" for part in parts)


class RandomizedTestGenerator:
    """Main orchestrator for generating randomized tests."""

    FORK_CONFIGS: ClassVar[dict[str, ForkConfig]] = {
        PHASE0: ForkConfig(
            name=PHASE0,
            state_randomizer=randomize_state,
            block_randomizer=random_block,
        ),
        ALTAIR: ForkConfig(
            name=ALTAIR,
            state_randomizer=randomize_state_altair,
            block_randomizer=random_block_altair_with_cycling_sync_committee_participation,
        ),
        BELLATRIX: ForkConfig(
            name=BELLATRIX,
            state_randomizer=randomize_state_bellatrix,
            block_randomizer=random_block_bellatrix,
        ),
        CAPELLA: ForkConfig(
            name=CAPELLA,
            state_randomizer=randomize_state_capella,
            block_randomizer=random_block_capella,
        ),
        DENEB: ForkConfig(
            name=DENEB,
            state_randomizer=randomize_state_deneb,
            block_randomizer=random_block_deneb,
        ),
        ELECTRA: ForkConfig(
            name=ELECTRA,
            state_randomizer=randomize_state_electra,
            block_randomizer=random_block_electra,
        ),
        FULU: ForkConfig(
            name=FULU,
            state_randomizer=randomize_state_fulu,
            block_randomizer=random_block_fulu,
        ),
        GLOAS: ForkConfig(
            name=GLOAS,
            state_randomizer=randomize_state_gloas,
            block_randomizer=random_block_gloas,
        ),
    }

    def __init__(self, fork: str) -> None:
        if fork not in self.FORK_CONFIGS:
            raise ValueError(f"Unknown fork: {fork}. Available: {list(self.FORK_CONFIGS.keys())}")
        self._fork = fork
        self._config = self.FORK_CONFIGS[fork]

    def generate(self) -> str:
        """Generate the complete test file content."""
        generator = ScenarioGenerator(
            block_randomizer=self._config.block_randomizer,
            seed=DEFAULT_SEED,
        )
        scenarios = generator.generate()

        renderer = ScenarioRenderer(
            fork_name=self._config.name,
            state_randomizer_name=self._config.state_randomizer.__name__,
        )

        return renderer.render(scenarios)

    def generate_scenarios(self) -> list[ScenarioDict]:
        """Generate scenarios without rendering (for testing)."""
        generator = ScenarioGenerator(
            block_randomizer=self._config.block_randomizer,
            seed=DEFAULT_SEED,
        )
        return generator.generate()

    @classmethod
    def available_forks(cls) -> list[str]:
        """Return list of available fork names."""
        return list(cls.FORK_CONFIGS.keys())


def main() -> None:
    """CLI entry point."""
    parser = argparse.ArgumentParser(
        description="Generate randomized block tests for Ethereum consensus layer."
    )
    parser.add_argument(
        "--fork",
        type=str,
        help="Generate for specific fork only. If not specified, generates for all forks.",
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=Path(DEFAULT_OUTPUT_DIR),
        help=f"Output directory (default: {DEFAULT_OUTPUT_DIR}).",
    )
    parser.add_argument(
        "--stdout",
        action="store_true",
        help="Print to stdout instead of writing files.",
    )
    parser.add_argument(
        "--list-forks",
        action="store_true",
        help="List available forks and exit.",
    )

    args = parser.parse_args()

    if args.list_forks:
        print("Available forks:")
        for fork in RandomizedTestGenerator.available_forks():
            print(f"  {fork}")
        return

    forks = [args.fork] if args.fork else RandomizedTestGenerator.available_forks()

    for fork in forks:
        generator = RandomizedTestGenerator(fork)
        content = generator.generate()

        if args.stdout:
            if len(forks) > 1:
                print(f"# === {fork.upper()} ===", file=sys.stderr)
            print(content)
            if len(forks) > 1 and fork != forks[-1]:
                print("\n" + "=" * 80 + "\n")
        else:
            output_path = args.output_dir / fork / "random" / "test_random.py"
            output_path.parent.mkdir(parents=True, exist_ok=True)
            output_path.write_text(content + "\n")
            print(f"Generated: {output_path}", file=sys.stderr)


if __name__ == "__main__":
    main()
