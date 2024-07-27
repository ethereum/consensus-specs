SPEC_DIR = ./specs
SSZ_DIR = ./ssz
TEST_LIBS_DIR = ./tests/core
TEST_GENERATORS_DIR = ./tests/generators
# The working dir during testing
PY_SPEC_DIR = $(TEST_LIBS_DIR)/pyspec
ETH2SPEC_MODULE_DIR = $(PY_SPEC_DIR)/eth2spec
TEST_REPORT_DIR = $(PY_SPEC_DIR)/test-reports
TEST_VECTOR_DIR = ../consensus-spec-tests/tests
GENERATOR_DIR = ./tests/generators
SOLIDITY_DEPOSIT_CONTRACT_DIR = ./solidity_deposit_contract
SOLIDITY_DEPOSIT_CONTRACT_SOURCE = ${SOLIDITY_DEPOSIT_CONTRACT_DIR}/deposit_contract.sol
SOLIDITY_FILE_NAME = deposit_contract.json
DEPOSIT_CONTRACT_TESTER_DIR = ${SOLIDITY_DEPOSIT_CONTRACT_DIR}/web3_tester
CONFIGS_DIR = ./configs
TEST_PRESET_TYPE ?= minimal
# Collect a list of generator names
GENERATORS = $(sort $(dir $(wildcard $(GENERATOR_DIR)/*/.)))
# Map this list of generator paths to "gen_{generator name}" entries
GENERATOR_TARGETS = $(patsubst $(GENERATOR_DIR)/%/, gen_%, $(GENERATORS))
GENERATOR_VENVS = $(patsubst $(GENERATOR_DIR)/%, $(GENERATOR_DIR)/%venv, $(GENERATORS))
# Documents
DOCS_DIR = ./docs
SSZ_DIR = ./ssz
SYNC_DIR = ./sync
FORK_CHOICE_DIR = ./fork_choice

# To check generator matching:
#$(info $$GENERATOR_TARGETS is [${GENERATOR_TARGETS}])

MARKDOWN_FILES = $(wildcard $(SPEC_DIR)/*/*.md) \
                 $(wildcard $(SPEC_DIR)/*/*/*.md) \
                 $(wildcard $(SPEC_DIR)/_features/*/*.md) \
                 $(wildcard $(SPEC_DIR)/_features/*/*/*.md) \
                 $(wildcard $(SSZ_DIR)/*.md)

ALL_EXECUTABLE_SPEC_NAMES = phase0 altair bellatrix capella deneb electra whisk eip6800
# The parameters for commands. Use `foreach` to avoid listing specs again.
COVERAGE_SCOPE := $(foreach S,$(ALL_EXECUTABLE_SPEC_NAMES), --cov=eth2spec.$S.$(TEST_PRESET_TYPE))
PYLINT_SCOPE := $(foreach S,$(ALL_EXECUTABLE_SPEC_NAMES), ./eth2spec/$S)
MYPY_SCOPE := $(foreach S,$(ALL_EXECUTABLE_SPEC_NAMES), -p eth2spec.$S)

COV_HTML_OUT=.htmlcov
COV_HTML_OUT_DIR=$(PY_SPEC_DIR)/$(COV_HTML_OUT)
COV_INDEX_FILE=$(COV_HTML_OUT_DIR)/index.html

CURRENT_DIR = ${CURDIR}
LINTER_CONFIG_FILE = $(CURRENT_DIR)/linter.ini
GENERATOR_ERROR_LOG_FILE = $(CURRENT_DIR)/$(TEST_VECTOR_DIR)/testgen_error_log.txt

SCRIPTS_DIR = ${CURRENT_DIR}/scripts

export DAPP_SKIP_BUILD:=1
export DAPP_SRC:=$(SOLIDITY_DEPOSIT_CONTRACT_DIR)
export DAPP_LIB:=$(SOLIDITY_DEPOSIT_CONTRACT_DIR)/lib
export DAPP_JSON:=build/combined.json

.PHONY: clean partial_clean all test citest lint generate_tests pyspec install_test open_cov \
        install_deposit_contract_tester test_deposit_contract install_deposit_contract_compiler \
        compile_deposit_contract test_compile_deposit_contract check_toc \
        detect_generator_incomplete detect_generator_error_log

all: $(PY_SPEC_ALL_TARGETS)

# deletes everything except the venvs
partial_clean:
	rm -rf $(TEST_VECTOR_DIR)
	rm -rf $(GENERATOR_VENVS)
	rm -rf .pytest_cache
	rm -f .coverage
	rm -rf $(PY_SPEC_DIR)/.pytest_cache
	rm -rf $(DEPOSIT_CONTRACT_TESTER_DIR)/.pytest_cache
	rm -rf $(COV_HTML_OUT_DIR)
	rm -rf $(TEST_REPORT_DIR)
	rm -rf eth2spec.egg-info dist build
	rm -rf build;
	@for spec_name in $(ALL_EXECUTABLE_SPEC_NAMES) ; do \
		echo $$spec_name; \
		rm -rf $(ETH2SPEC_MODULE_DIR)/$$spec_name; \
	done

clean: partial_clean
	rm -rf venv
	# legacy cleanup. The pyspec venv should be located at the repository root
	rm -rf $(PY_SPEC_DIR)/venv
	rm -rf $(DEPOSIT_CONTRACT_COMPILER_DIR)/venv
	rm -rf $(DEPOSIT_CONTRACT_TESTER_DIR)/venv

# The pyspec is rebuilt to enforce the /specs being part of eth2specs source distribution. It could be forgotten otherwise.
dist_build: pyspec
	python3 setup.py sdist bdist_wheel

dist_check:
	python3 -m twine check dist/*

dist_upload:
	python3 -m twine upload dist/*


# "make generate_tests" to run all generators
generate_tests: $(GENERATOR_TARGETS)

# "make pyspec" to create the pyspec for all phases.
pyspec:
	python3 -m venv venv; . venv/bin/activate; python3 setup.py pyspecdev

# check the setup tool requirements
preinstallation:
	python3 -m venv venv && \
	. venv/bin/activate && \
	python3 -m pip install -r requirements_preinstallation.txt

install_test: preinstallation
	. venv/bin/activate && \
	python3 -m pip install -e .[lint,test]

# Testing against `minimal` or `mainnet` config by default
test: pyspec
	. venv/bin/activate; cd $(PY_SPEC_DIR); \
	python3 -m pytest -n auto --disable-bls $(COVERAGE_SCOPE) --cov-report="html:$(COV_HTML_OUT)" --cov-branch eth2spec

# Testing against `minimal` or `mainnet` config by default
find_test: pyspec
	. venv/bin/activate; cd $(PY_SPEC_DIR); \
	python3 -m pytest -k=$(K) --disable-bls $(COVERAGE_SCOPE) --cov-report="html:$(COV_HTML_OUT)" --cov-branch eth2spec

citest: pyspec
	mkdir -p $(TEST_REPORT_DIR);
ifdef fork
	. venv/bin/activate; cd $(PY_SPEC_DIR); \
	python3 -m pytest -n auto --bls-type=fastest --preset=$(TEST_PRESET_TYPE) --fork=$(fork) --junitxml=test-reports/test_results.xml eth2spec
else
	. venv/bin/activate; cd $(PY_SPEC_DIR); \
	python3 -m pytest -n auto --bls-type=fastest --preset=$(TEST_PRESET_TYPE) --junitxml=test-reports/test_results.xml eth2spec
endif


open_cov:
	((open "$(COV_INDEX_FILE)" || xdg-open "$(COV_INDEX_FILE)") &> /dev/null) &

check_toc: $(MARKDOWN_FILES:=.toc)

%.toc:
	cp $* $*.tmp && \
	doctoc $* && \
	diff -q $* $*.tmp && \
	rm $*.tmp

codespell:
	codespell . --skip "./.git,./venv,$(PY_SPEC_DIR)/.mypy_cache" -I .codespell-whitelist

lint: pyspec
	. venv/bin/activate; cd $(PY_SPEC_DIR); \
	flake8  --config $(LINTER_CONFIG_FILE) ./eth2spec \
	&& python -m pylint --rcfile $(LINTER_CONFIG_FILE) $(PYLINT_SCOPE) \
	&& python -m mypy --config-file $(LINTER_CONFIG_FILE) $(MYPY_SCOPE)

lint_generators: pyspec
	. venv/bin/activate; cd $(TEST_GENERATORS_DIR); \
	flake8 --config $(LINTER_CONFIG_FILE)

compile_deposit_contract:
	@cd $(SOLIDITY_DEPOSIT_CONTRACT_DIR)
	@git submodule update --recursive --init
	@solc --metadata-literal --optimize --optimize-runs 5000000 --bin --abi --combined-json=abi,bin,bin-runtime,srcmap,srcmap-runtime,ast,metadata,storage-layout --overwrite -o build $(SOLIDITY_DEPOSIT_CONTRACT_SOURCE) $(SOLIDITY_DEPOSIT_CONTRACT_DIR)/tests/deposit_contract.t.sol
	@/bin/echo -n '{"abi": ' > $(SOLIDITY_FILE_NAME)
	@cat build/DepositContract.abi >> $(SOLIDITY_FILE_NAME)
	@/bin/echo -n ', "bytecode": "0x' >> $(SOLIDITY_FILE_NAME)
	@cat build/DepositContract.bin >> $(SOLIDITY_FILE_NAME)
	@/bin/echo -n '"}' >> $(SOLIDITY_FILE_NAME)

test_deposit_contract:
	dapp test -v --fuzz-runs 5

install_deposit_contract_web3_tester:
	cd $(DEPOSIT_CONTRACT_TESTER_DIR); python3 -m venv venv; . venv/bin/activate; python3 -m pip install -r requirements.txt

test_deposit_contract_web3_tests:
	cd $(DEPOSIT_CONTRACT_TESTER_DIR); . venv/bin/activate; \
	python3 -m pytest .

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
	python3 main.py -o $(CURRENT_DIR)/$(TEST_VECTOR_DIR); \
	echo "generator $(1) finished"
endef

# The tests dir itself is simply built by creating the directory (recursively creating deeper directories if necessary)
$(TEST_VECTOR_DIR):
	$(info creating test output directory, for generators: ${GENERATOR_TARGETS})
	mkdir -p $@
$(TEST_VECTOR_DIR)/:
	$(info ignoring duplicate tests dir)

gen_kzg_setups:
	cd $(SCRIPTS_DIR); \
	if ! test -d venv; then python3 -m venv venv; fi; \
	. venv/bin/activate; \
	pip3 install -r requirements.txt; \
	python3 ./gen_kzg_trusted_setups.py --secret=1337 --g1-length=4096 --g2-length=65 --output-dir ${CURRENT_DIR}/presets/minimal/trusted_setups; \
	python3 ./gen_kzg_trusted_setups.py --secret=1337 --g1-length=4096 --g2-length=65 --output-dir ${CURRENT_DIR}/presets/mainnet/trusted_setups

# For any generator, build it using the run_generator function.
# (creation of output dir is a dependency)
gen_%: $(TEST_VECTOR_DIR)
	$(call run_generator,$*)

detect_generator_incomplete: $(TEST_VECTOR_DIR)
	find $(TEST_VECTOR_DIR) -name "INCOMPLETE"

detect_generator_error_log: $(TEST_VECTOR_DIR)
	[ -f $(GENERATOR_ERROR_LOG_FILE) ] && echo "[ERROR] $(GENERATOR_ERROR_LOG_FILE) file exists" || echo "[PASSED] error log file does not exist"


# For docs reader
install_docs:
	python3 -m venv venv; . venv/bin/activate; python3 -m pip install -e .[docs];

copy_docs:
	cp -r $(SPEC_DIR) $(DOCS_DIR);
	cp -r $(SYNC_DIR) $(DOCS_DIR);
	cp -r $(SSZ_DIR) $(DOCS_DIR);
	cp -r $(FORK_CHOICE_DIR) $(DOCS_DIR);
	cp $(CURRENT_DIR)/README.md $(DOCS_DIR)/README.md

build_docs: copy_docs
	. venv/bin/activate;
	mkdocs build

serve_docs:
	. venv/bin/activate;
	mkdocs serve
