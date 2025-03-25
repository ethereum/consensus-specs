from typing import Iterable

from eth2spec.test.helpers.constants import (
    MINIMAL,
    MAINNET,
    ALL_PRE_POST_FORKS,
)
from eth2spec.gen_helpers.gen_base import gen_runner, gen_typing
from eth2spec.gen_helpers.gen_from_tests.gen import (
    generate_from_tests,
)
from eth2spec.test.altair.transition import (
    test_transition as test_altair_transition,
    test_activations_and_exits as test_altair_activations_and_exits,
    test_leaking as test_altair_leaking,
    test_slashing as test_altair_slashing,
    test_operations as test_altair_operations,
)
from eth2spec.test.deneb.transition import (
    test_operations as test_deneb_operations,
    test_transition as test_deneb_transition,
)
from eth2spec.test.electra.transition import (
    test_operations as test_electra_operations,
)


def create_provider(
    tests_src, preset_name: str, pre_fork_name: str, post_fork_name: str
) -> gen_typing.TestProvider:
    def prepare_fn() -> None:
        return

    def cases_fn() -> Iterable[gen_typing.TestCase]:
        return generate_from_tests(
            runner_name="transition",
            handler_name="core",
            src=tests_src,
            fork_name=post_fork_name,
            phase=pre_fork_name,
            preset_name=preset_name,
        )

    return gen_typing.TestProvider(prepare=prepare_fn, make_cases=cases_fn)


if __name__ == "__main__":
    all_tests = (
        test_altair_transition,
        test_altair_activations_and_exits,
        test_altair_leaking,
        test_altair_slashing,
        test_altair_operations,
        test_deneb_operations,
        test_deneb_transition,
        test_electra_operations,
    )
    for transition_test_module in all_tests:
        for pre_fork, post_fork in ALL_PRE_POST_FORKS:
            gen_runner.run_generator(
                "transition",
                [
                    create_provider(transition_test_module, MINIMAL, pre_fork, post_fork),
                    create_provider(transition_test_module, MAINNET, pre_fork, post_fork),
                ],
            )
