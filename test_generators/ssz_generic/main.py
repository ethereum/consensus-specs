
from gen_base import gen_runner, gen_typing


if __name__ == "__main__":
    gen_runner.run_generator("ssz_generic", [ssz_random_uint_suite, ssz_wrong_uint_suite, ssz_uint_bounds_suite])
