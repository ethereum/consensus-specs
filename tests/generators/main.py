import importlib
import os

from eth2spec.gen_helpers.gen_base import gen_runner

if __name__ == "__main__":
    current_dir = os.path.dirname(__file__)
    runners_dir = os.path.join(current_dir, "runners")

    test_cases = []
    for filename in os.listdir(runners_dir):
        if not filename.endswith(".py"):
            continue
        module_name = filename.replace(".py", "")
        full_module = f"tests.generators.runners.{module_name}"
        mod = importlib.import_module(full_module)
        assert hasattr(mod, "get_test_cases"), full_module
        test_cases.extend(mod.get_test_cases())

    gen_runner.run_generator(test_cases)
