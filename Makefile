SPEC_DIR = ./specs
SCRIPT_DIR = ./scripts
TEST_LIBS_DIR = ./test_libs
PY_SPEC_DIR = $(TEST_LIBS_DIR)/pyspec

YAML_TEST_DIR = ./yaml_tests
GENERATOR_DIR = ./test_generators
GENERATOR_VENVS_DIR = $(GENERATOR_DIR)/.venvs

# Collect a list of generator names
GENERATORS = $(sort $(dir $(wildcard $(GENERATOR_DIR)/*/)))
# Map this list of generator paths to a list of test output paths
YAML_TEST_TARGETS = $(patsubst $(GENERATOR_DIR)/%, $(YAML_TEST_DIR)/%, $(GENERATORS))

PY_SPEC_PHASE_0_TARGETS = $(PY_SPEC_DIR)/eth2/phase0/spec.py
PY_SPEC_ALL_TARGETS = $(PY_SPEC_PHASE_0_TARGETS)


.PHONY: clean all test yaml_tests pyspec phase0

all: $(YAML_TEST_DIR) $(YAML_TEST_TARGETS) $(PY_SPEC_ALL_TARGETS)

clean:
	rm -rf $(YAML_TEST_DIR)
	rm -rf $(GENERATOR_VENVS_DIR)
	rm -rf $(PY_SPEC_ALL_TARGETS)

# "make yaml_tests" to run generators
yaml_tests: $(YAML_TEST_TARGETS)

# runs a limited set of tests against a minimal config
# run pytest with `-m` option to full suite
test: $(PY_SPEC_TARGETS)
	pytest -m minimal_config tests/

# "make pyspec" to create the pyspec for all phases.
pyspec: $(PY_SPEC_TARGETS)

# "make phase0" to create pyspec for phase0
phase0: $(PY_SPEC_PHASE_0_TARGETS)


$(PY_SPEC_DIR)/eth2/phase0/spec.py:
	python3 $(SCRIPT_DIR)/phase0/build_spec.py  $(SPEC_DIR)/core/0_beacon-chain.md $@



# The function that builds a set of suite files, by calling a generator for the given type (param 1)
define build_yaml_tests
	$(info running generator $(1))
	# Create the output
	mkdir -p $(YAML_TEST_DIR)$(1)

	# Create a virtual environment
	python3 -m venv $(VENV_DIR)$(1)
	# Activate the venv, this is where dependencies are installed for the generator
	. $(GENERATOR_VENVS_DIR)$(1)bin/activate
	# Install all the necessary requirements
	pip3 install -r $(GENERATOR_DIR)$(1)requirements.txt

	# Run the generator. The generator is assumed to have an "main.py" file.
	# We output to the tests dir (generator program should accept a "-p <filepath>" argument.
	python3 $(GENERATOR_DIR)$(1)main.py -o $(YAML_TEST_DIR)$(1)
	$(info generator $(1) finished)
endef

# The tests dir itself is simply build by creating the directory (recursively creating deeper directories if necessary)
$(YAML_TEST_DIR):
	$(info ${YAML_TEST_TARGETS})
	mkdir -p $@

# For any target within the tests dir, build it using the build_yaml_tests function.
$(YAML_TEST_DIR)%:
	$(call build_yaml_tests,$*)
