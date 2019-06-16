SPEC_DIR = ./specs
SCRIPT_DIR = ./scripts
TEST_LIBS_DIR = ./test_libs
PY_SPEC_DIR = $(TEST_LIBS_DIR)/pyspec
YAML_TEST_DIR = ./eth2.0-spec-tests/tests
GENERATOR_DIR = ./test_generators
DEPOSIT_CONTRACT_DIR = ./deposit_contract
CONFIGS_DIR = ./configs

# Collect a list of generator names
GENERATORS = $(sort $(dir $(wildcard $(GENERATOR_DIR)/*/)))
# Map this list of generator paths to a list of test output paths
YAML_TEST_TARGETS = $(patsubst $(GENERATOR_DIR)/%, $(YAML_TEST_DIR)/%, $(GENERATORS))
GENERATOR_VENVS = $(patsubst $(GENERATOR_DIR)/%, $(GENERATOR_DIR)/%venv, $(GENERATORS))

PY_SPEC_PHASE_0_TARGETS = $(PY_SPEC_DIR)/eth2spec/phase0/spec.py
PY_SPEC_PHASE_0_DEPS = $(SPEC_DIR)/core/0_*.md

PY_SPEC_PHASE_1_TARGETS = $(PY_SPEC_DIR)/eth2spec/phase1/spec.py
PY_SPEC_PHASE_1_DEPS = $(SPEC_DIR)/core/1_*.md

PY_SPEC_ALL_TARGETS = $(PY_SPEC_PHASE_0_TARGETS) $(PY_SPEC_PHASE_1_TARGETS)

COV_HTML_OUT=.htmlcov
COV_INDEX_FILE=$(PY_SPEC_DIR)/$(COV_HTML_OUT)/index.html

.PHONY: clean all test citest lint gen_yaml_tests pyspec phase0 phase1 install_test open_cov \
        install_deposit_contract_test test_deposit_contract compile_deposit_contract

all: $(PY_SPEC_ALL_TARGETS) $(YAML_TEST_DIR) $(YAML_TEST_TARGETS)

clean:
	rm -rf $(YAML_TEST_DIR)
	rm -rf $(GENERATOR_VENVS)
	rm -rf $(PY_SPEC_DIR)/venv $(PY_SPEC_DIR)/.pytest_cache
	rm -rf $(PY_SPEC_ALL_TARGETS)
	rm -rf $(DEPOSIT_CONTRACT_DIR)/venv $(DEPOSIT_CONTRACT_DIR)/.pytest_cache
	rm -rf $(PY_SPEC_DIR)/$(COV_HTML_OUT)
	rm -rf $(PY_SPEC_DIR)/.coverage
	rm -rf $(PY_SPEC_DIR)/test-reports

# "make gen_yaml_tests" to run generators
gen_yaml_tests: $(PY_SPEC_ALL_TARGETS) $(YAML_TEST_TARGETS)

# installs the packages to run pyspec tests
install_test:
	cd $(PY_SPEC_DIR); python3 -m venv venv; . venv/bin/activate; pip3 install -r requirements-testing.txt;

test: $(PY_SPEC_ALL_TARGETS)
	cd $(PY_SPEC_DIR); . venv/bin/activate;	export PYTHONPATH="./"; \
	python -m pytest --cov=eth2spec.phase0.spec --cov=eth2spec.phase1.spec --cov-report="html:$(COV_HTML_OUT)" --cov-branch eth2spec

citest: $(PY_SPEC_ALL_TARGETS)
	cd $(PY_SPEC_DIR); mkdir -p test-reports/eth2spec; . venv/bin/activate; \
	python -m pytest --junitxml=test-reports/eth2spec/test_results.xml eth2spec

open_cov:
	((open "$(COV_INDEX_FILE)" || xdg-open "$(COV_INDEX_FILE)") &> /dev/null) &

lint: $(PY_SPEC_ALL_TARGETS)
	cd $(PY_SPEC_DIR); . venv/bin/activate; \
	flake8  --ignore=E252,W504,W503 --max-line-length=120 ./eth2spec;

install_deposit_contract_test: $(PY_SPEC_ALL_TARGETS)
	cd $(DEPOSIT_CONTRACT_DIR); python3 -m venv venv; . venv/bin/activate; pip3 install -r requirements-testing.txt

compile_deposit_contract:
	cd $(DEPOSIT_CONTRACT_DIR); . venv/bin/activate; \
	python tool/compile_deposit_contract.py contracts/validator_registration.v.py;

test_deposit_contract:
	cd $(DEPOSIT_CONTRACT_DIR); . venv/bin/activate; \
	python -m pytest .

# "make pyspec" to create the pyspec for all phases.
pyspec: $(PY_SPEC_ALL_TARGETS)

$(PY_SPEC_PHASE_0_TARGETS): $(PY_SPEC_PHASE_0_DEPS)
	python3 $(SCRIPT_DIR)/build_spec.py -p0 $(SPEC_DIR)/core/0_beacon-chain.md $@

$(PY_SPEC_DIR)/eth2spec/phase1/spec.py: $(PY_SPEC_PHASE_1_DEPS)
	python3 $(SCRIPT_DIR)/build_spec.py -p1 $(SPEC_DIR)/core/0_beacon-chain.md $(SPEC_DIR)/core/1_custody-game.md $(SPEC_DIR)/core/1_shard-data-chains.md $@

CURRENT_DIR = ${CURDIR}

# The function that builds a set of suite files, by calling a generator for the given type (param 1)
define build_yaml_tests
	# Started!
	# Create output directory
	# Navigate to the generator
	# Create a virtual environment, if it does not exist already
	# Activate the venv, this is where dependencies are installed for the generator
	# Install all the necessary requirements
	# Run the generator. The generator is assumed to have an "main.py" file.
	# We output to the tests dir (generator program should accept a "-o <filepath>" argument.
	echo "generator $(1) started"; \
	mkdir -p $(YAML_TEST_DIR)$(1); \
	cd $(GENERATOR_DIR)$(1); \
	if ! test -d venv; then python3 -m venv venv; fi; \
	. venv/bin/activate; \
	pip3 install -r requirements.txt; \
	python3 main.py -o $(CURRENT_DIR)/$(YAML_TEST_DIR)$(1) -c $(CURRENT_DIR)/$(CONFIGS_DIR); \
	echo "generator $(1) finished"
endef

# The tests dir itself is simply build by creating the directory (recursively creating deeper directories if necessary)
$(YAML_TEST_DIR):
	$(info creating directory, to output yaml targets to: ${YAML_TEST_TARGETS})
	mkdir -p $@
$(YAML_TEST_DIR)/:
	$(info ignoring duplicate yaml tests dir)

# For any target within the tests dir, build it using the build_yaml_tests function.
# (creation of output dir is a dependency)
$(YAML_TEST_DIR)%: $(PY_SPEC_ALL_TARGETS) $(YAML_TEST_DIR)
	$(call build_yaml_tests,$*)
