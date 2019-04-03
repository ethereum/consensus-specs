SPEC_DIR = ./specs
SCRIPT_DIR = ./scripts
TEST_LIBS_DIR = ./test_libs
PY_SPEC_DIR = $(TEST_LIBS_DIR)/pyspec
PY_TEST_DIR = ./py_tests
YAML_TEST_DIR = ./yaml_tests
GENERATOR_DIR = ./test_generators

# Collect a list of generator names
GENERATORS = $(sort $(dir $(wildcard $(GENERATOR_DIR)/*/)))
# Map this list of generator paths to a list of test output paths
YAML_TEST_TARGETS = $(patsubst $(GENERATOR_DIR)/%, $(YAML_TEST_DIR)/%, $(GENERATORS))
GENERATOR_VENVS = $(patsubst $(GENERATOR_DIR)/%, $(GENERATOR_DIR)/%venv, $(GENERATORS))

PY_SPEC_PHASE_0_TARGETS = $(PY_SPEC_DIR)/eth2spec/phase0/spec.py
PY_SPEC_ALL_TARGETS = $(PY_SPEC_PHASE_0_TARGETS)


.PHONY: clean all test gen_yaml_tests pyspec phase0

all: $(PY_SPEC_ALL_TARGETS) $(YAML_TEST_DIR) $(YAML_TEST_TARGETS)

clean:
	rm -rf $(YAML_TEST_DIR)
	rm -rf $(GENERATOR_VENVS)
	rm -rf $(PY_TEST_DIR)/venv $(PY_TEST_DIR)/.pytest_cache
	rm -rf $(PY_SPEC_ALL_TARGETS)

# "make gen_yaml_tests" to run generators
gen_yaml_tests: $(YAML_TEST_DIR) $(YAML_TEST_TARGETS)

# runs a limited set of tests against a minimal config
test: $(PY_SPEC_ALL_TARGETS)
	cd $(PY_TEST_DIR); python3 -m venv venv; . venv/bin/activate; pip3 install -r requirements.txt; pytest -m minimal_config .

# "make pyspec" to create the pyspec for all phases.
pyspec: $(PY_SPEC_ALL_TARGETS)

# "make phase0" to create pyspec for phase0
phase0: $(PY_SPEC_PHASE_0_TARGETS)


$(PY_SPEC_DIR)/eth2spec/phase0/spec.py:
	python3 $(SCRIPT_DIR)/phase0/build_spec.py  $(SPEC_DIR)/core/0_beacon-chain.md $@


CURRENT_DIR = ${CURDIR}

# The function that builds a set of suite files, by calling a generator for the given type (param 1)
define build_yaml_tests
	$(info running generator $(1))
	# Create the output
	mkdir -p $(YAML_TEST_DIR)$(1)

	# 1) Create a virtual environment
	# 2) Activate the venv, this is where dependencies are installed for the generator
	# 3) Install all the necessary requirements
	# 4) Run the generator. The generator is assumed to have an "main.py" file.
	# 5) We output to the tests dir (generator program should accept a "-o <filepath>" argument.
	cd $(GENERATOR_DIR)$(1); python3 -m venv venv; . venv/bin/activate; pip3 install -r requirements.txt; python3 main.py -o $(CURRENT_DIR)/$(YAML_TEST_DIR)$(1)

	$(info generator $(1) finished)
endef

# The tests dir itself is simply build by creating the directory (recursively creating deeper directories if necessary)
$(YAML_TEST_DIR):
	$(info creating directory, to output yaml targets to: ${YAML_TEST_TARGETS})
	mkdir -p $@

# For any target within the tests dir, build it using the build_yaml_tests function.
# (creation of output dir is a dependency)
$(YAML_TEST_DIR)%: $(YAML_TEST_DIR)
	$(call build_yaml_tests,$*)
