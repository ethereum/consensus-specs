SPEC_DIR = ./specs
SSZ_DIR = ./ssz
SCRIPT_DIR = ./scripts
TEST_LIBS_DIR = ./tests/core
PY_SPEC_DIR = $(TEST_LIBS_DIR)/pyspec
TEST_VECTOR_DIR = ./eth2.0-spec-tests/tests
GENERATOR_DIR = ./tests/generators
DEPOSIT_CONTRACT_COMPILER_DIR = ./deposit_contract/compiler
DEPOSIT_CONTRACT_TESTER_DIR = ./deposit_contract/tester
CONFIGS_DIR = ./configs

# Collect a list of generator names
GENERATORS = $(sort $(dir $(wildcard $(GENERATOR_DIR)/*/.)))
# Map this list of generator paths to "gen_{generator name}" entries
GENERATOR_TARGETS = $(patsubst $(GENERATOR_DIR)/%/, gen_%, $(GENERATORS))
GENERATOR_VENVS = $(patsubst $(GENERATOR_DIR)/%, $(GENERATOR_DIR)/%venv, $(GENERATORS))

# To check generator matching:
#$(info $$GENERATOR_TARGETS is [${GENERATOR_TARGETS}])

PHASE0_SPEC_DIR = $(SPEC_DIR)/phase0
PY_SPEC_PHASE_0_TARGETS = $(PY_SPEC_DIR)/eth2spec/phase0/spec.py
PY_SPEC_PHASE_0_DEPS = $(wildcard $(SPEC_DIR)/phase0/*.md)

PHASE1_SPEC_DIR = $(SPEC_DIR)/phase1
PY_SPEC_PHASE_1_TARGETS = $(PY_SPEC_DIR)/eth2spec/phase1/spec.py
PY_SPEC_PHASE_1_DEPS = $(wildcard $(SPEC_DIR)/phase1/*.md)

PY_SPEC_ALL_DEPS = $(PY_SPEC_PHASE_0_DEPS) $(PY_SPEC_PHASE_1_DEPS)

PY_SPEC_ALL_TARGETS = $(PY_SPEC_PHASE_0_TARGETS) $(PY_SPEC_PHASE_1_TARGETS)

MARKDOWN_FILES = $(PY_SPEC_ALL_DEPS) $(wildcard $(SPEC_DIR)/*.md) $(wildcard $(SSZ_DIR)/*.md) $(wildcard $(SPEC_DIR)/networking/*.md) $(wildcard $(SPEC_DIR)/validator/*.md)

COV_HTML_OUT=.htmlcov
COV_INDEX_FILE=$(PY_SPEC_DIR)/$(COV_HTML_OUT)/index.html

.PHONY: clean partial_clean all test citest lint generate_tests pyspec phase0 phase1 install_test open_cov \
        install_deposit_contract_tester test_deposit_contract install_deposit_contract_compiler \
        compile_deposit_contract test_compile_deposit_contract check_toc

all: $(PY_SPEC_ALL_TARGETS)

# deletes everything except the venvs
partial_clean:
	rm -rf $(TEST_VECTOR_DIR)
	rm -rf $(GENERATOR_VENVS)
	rm -rf $(PY_SPEC_DIR)/.pytest_cache
	rm -rf $(PY_SPEC_ALL_TARGETS)
	rm -rf $(DEPOSIT_CONTRACT_COMPILER_DIR)/.pytest_cache
	rm -rf $(DEPOSIT_CONTRACT_TESTER_DIR)/.pytest_cache
	rm -rf $(PY_SPEC_DIR)/$(COV_HTML_OUT)
	rm -rf $(PY_SPEC_DIR)/.coverage
	rm -rf $(PY_SPEC_DIR)/test-reports

clean: partial_clean
	rm -rf $(PY_SPEC_DIR)/venv
	rm -rf $(DEPOSIT_CONTRACT_COMPILER_DIR)/venv
	rm -rf $(DEPOSIT_CONTRACT_TESTER_DIR)/venv

# "make generate_tests" to run all generators
generate_tests: $(PY_SPEC_ALL_TARGETS) $(GENERATOR_TARGETS)

# installs the packages to run pyspec tests
install_test:
	cd $(PY_SPEC_DIR); python3 -m venv venv; . venv/bin/activate; pip3 install -r requirements-testing.txt;

test: $(PY_SPEC_ALL_TARGETS)
	cd $(PY_SPEC_DIR); . venv/bin/activate;	export PYTHONPATH="./"; \
	python -m pytest -n 4 --cov=eth2spec.phase0.spec --cov=eth2spec.phase1.spec --cov-report="html:$(COV_HTML_OUT)" --cov-branch eth2spec

citest: $(PY_SPEC_ALL_TARGETS)
	cd $(PY_SPEC_DIR); mkdir -p test-reports/eth2spec; . venv/bin/activate; export PYTHONPATH="./"; \
	python -m pytest -n 4 --junitxml=test-reports/eth2spec/test_results.xml eth2spec

open_cov:
	((open "$(COV_INDEX_FILE)" || xdg-open "$(COV_INDEX_FILE)") &> /dev/null) &

check_toc: $(MARKDOWN_FILES:=.toc)

%.toc:
	cp $* $*.tmp && \
	doctoc $* && \
	diff -q $* $*.tmp && \
	rm $*.tmp

codespell:
	codespell . --skip ./.git -I .codespell-whitelist

lint: $(PY_SPEC_ALL_TARGETS)
	cd $(PY_SPEC_DIR); . venv/bin/activate; \
	flake8  --ignore=E252,W504,W503 --max-line-length=120 ./eth2spec \
	&& cd ./eth2spec && mypy --follow-imports=silent --warn-unused-ignores --ignore-missing-imports --check-untyped-defs --disallow-incomplete-defs --disallow-untyped-defs -p phase0 \
	&& mypy --follow-imports=silent --warn-unused-ignores --ignore-missing-imports --check-untyped-defs --disallow-incomplete-defs --disallow-untyped-defs -p phase1;

install_deposit_contract_tester: $(PY_SPEC_ALL_TARGETS)
	cd $(DEPOSIT_CONTRACT_TESTER_DIR); python3 -m venv venv; . venv/bin/activate; pip3 install -r requirements.txt

test_deposit_contract:
	cd $(DEPOSIT_CONTRACT_TESTER_DIR); . venv/bin/activate; \
	python -m pytest .

install_deposit_contract_compiler:
	cd $(DEPOSIT_CONTRACT_COMPILER_DIR); python3.7 -m venv venv; . venv/bin/activate; pip3.7 install -r requirements.txt

compile_deposit_contract:
	cd $(DEPOSIT_CONTRACT_COMPILER_DIR); . venv/bin/activate; \
	python3.7 deposit_contract/compile.py contracts/validator_registration.vy

test_compile_deposit_contract:
	cd $(DEPOSIT_CONTRACT_COMPILER_DIR); . venv/bin/activate; \
	python3.7 -m pytest .

# "make pyspec" to create the pyspec for all phases.
pyspec: $(PY_SPEC_ALL_TARGETS)

$(PY_SPEC_PHASE_0_TARGETS): $(PY_SPEC_PHASE_0_DEPS)
	python3 $(SCRIPT_DIR)/build_spec.py -p0 $(PHASE0_SPEC_DIR)/beacon-chain.md $(PHASE0_SPEC_DIR)/fork-choice.md $(PHASE0_SPEC_DIR)/validator.md $@

$(PY_SPEC_DIR)/eth2spec/phase1/spec.py: $(PY_SPEC_PHASE_1_DEPS)
	python3 $(SCRIPT_DIR)/build_spec.py -p1 $(PHASE0_SPEC_DIR)/beacon-chain.md $(PHASE0_SPEC_DIR)/fork-choice.md $(SSZ_DIR)/merkle-proofs.md $(PHASE1_SPEC_DIR)/custody-game.md $(PHASE1_SPEC_DIR)/shard-data-chains.md $(PHASE1_SPEC_DIR)/beacon-chain-misc.md $@

CURRENT_DIR = ${CURDIR}

# Runs a generator, identified by param 1
define run_generator
	# Started!
	# Create output directory
	# Navigate to the generator
	# Create a virtual environment, if it does not exist already
	# Activate the venv, this is where dependencies are installed for the generator
	# Install all the necessary requirements
	# Run the generator. The generator is assumed to have an "main.py" file.
	# We output to the tests dir (generator program should accept a "-o <filepath>" argument.
	# `-l minimal general` can be added to the generator call to filter to smaller configs, when testing.
	echo "generator $(1) started"; \
	mkdir -p $(TEST_VECTOR_DIR); \
	cd $(GENERATOR_DIR)/$(1); \
	if ! test -d venv; then python3 -m venv venv; fi; \
	. venv/bin/activate; \
	pip3 install -r requirements.txt; \
	python3 main.py -o $(CURRENT_DIR)/$(TEST_VECTOR_DIR) -c $(CURRENT_DIR)/$(CONFIGS_DIR); \
	echo "generator $(1) finished"
endef

# The tests dir itself is simply build by creating the directory (recursively creating deeper directories if necessary)
$(TEST_VECTOR_DIR):
	$(info creating test output directory, for generators: ${GENERATOR_TARGETS})
	mkdir -p $@
$(TEST_VECTOR_DIR)/:
	$(info ignoring duplicate tests dir)

# For any generator, build it using the run_generator function.
# (creation of output dir is a dependency)
gen_%: $(PY_SPEC_ALL_TARGETS) $(TEST_VECTOR_DIR)
	$(call run_generator,$*)
