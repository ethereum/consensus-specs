SPEC_DIR = ./specs
SSZ_DIR = ./ssz
TEST_LIBS_DIR = ./tests/core
TEST_GENERATORS_DIR = ./tests/generators
PY_SPEC_DIR = $(TEST_LIBS_DIR)/pyspec
TEST_VECTOR_DIR = ../eth2.0-spec-tests/tests
GENERATOR_DIR = ./tests/generators
SOLIDITY_DEPOSIT_CONTRACT_DIR = ./solidity_deposit_contract
SOLIDITY_DEPOSIT_CONTRACT_SOURCE = ${SOLIDITY_DEPOSIT_CONTRACT_DIR}/deposit_contract.sol
SOLIDITY_FILE_NAME = deposit_contract.json
DEPOSIT_CONTRACT_TESTER_DIR = ${SOLIDITY_DEPOSIT_CONTRACT_DIR}/web3_tester
CONFIGS_DIR = ./configs

# Collect a list of generator names
GENERATORS = $(sort $(dir $(wildcard $(GENERATOR_DIR)/*/.)))
# Map this list of generator paths to "gen_{generator name}" entries
GENERATOR_TARGETS = $(patsubst $(GENERATOR_DIR)/%/, gen_%, $(GENERATORS))
GENERATOR_VENVS = $(patsubst $(GENERATOR_DIR)/%, $(GENERATOR_DIR)/%venv, $(GENERATORS))

# To check generator matching:
#$(info $$GENERATOR_TARGETS is [${GENERATOR_TARGETS}])

MARKDOWN_FILES = $(wildcard $(SPEC_DIR)/phase0/*.md) $(wildcard $(SPEC_DIR)/phase1/*.md) $(wildcard $(SPEC_DIR)/lightclient/*.md) $(wildcard $(SSZ_DIR)/*.md) $(wildcard $(SPEC_DIR)/networking/*.md) $(wildcard $(SPEC_DIR)/validator/*.md)

COV_HTML_OUT=.htmlcov
COV_INDEX_FILE=$(PY_SPEC_DIR)/$(COV_HTML_OUT)/index.html

CURRENT_DIR = ${CURDIR}
LINTER_CONFIG_FILE = $(CURRENT_DIR)/linter.ini

export DAPP_SKIP_BUILD:=1
export DAPP_SRC:=$(SOLIDITY_DEPOSIT_CONTRACT_DIR)
export DAPP_LIB:=$(SOLIDITY_DEPOSIT_CONTRACT_DIR)/lib
export DAPP_JSON:=build/combined.json

.PHONY: clean partial_clean all test citest lint generate_tests pyspec install_test open_cov \
        install_deposit_contract_tester test_deposit_contract install_deposit_contract_compiler \
        compile_deposit_contract test_compile_deposit_contract check_toc

all: $(PY_SPEC_ALL_TARGETS)

# deletes everything except the venvs
partial_clean:
	rm -rf $(TEST_VECTOR_DIR)
	rm -rf $(GENERATOR_VENVS)
	rm -rf .pytest_cache
	rm -f .coverage
	rm -rf $(PY_SPEC_DIR)/.pytest_cache
	rm -rf $(DEPOSIT_CONTRACT_TESTER_DIR)/.pytest_cache
	rm -rf $(PY_SPEC_DIR)/phase0
	rm -rf $(PY_SPEC_DIR)/phase1
	rm -rf $(PY_SPEC_DIR)/lightclient
	rm -rf $(PY_SPEC_DIR)/$(COV_HTML_OUT)
	rm -rf $(PY_SPEC_DIR)/.coverage
	rm -rf $(PY_SPEC_DIR)/test-reports
	rm -rf eth2spec.egg-info dist build
	rm -rf build

clean: partial_clean
	rm -rf venv
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
	. venv/bin/activate; python3 setup.py pyspecdev

# installs the packages to run pyspec tests
install_test:
	python3 -m venv venv; . venv/bin/activate; python3 -m pip install .[lint]; python3 -m pip install -e .[test]

test: pyspec
	. venv/bin/activate; cd $(PY_SPEC_DIR); \
	python3 -m pytest -n 4 --disable-bls --cov=eth2spec.phase0.spec --cov=eth2spec.phase1.spec --cov=eth2spec.lightclient_patch.spec -cov-report="html:$(COV_HTML_OUT)" --cov-branch eth2spec

find_test: pyspec
	. venv/bin/activate; cd $(PY_SPEC_DIR); \
	python3 -m pytest -k=$(K) --disable-bls --cov=eth2spec.phase0.spec --cov=eth2spec.phase1.spec --cov=eth2spec.lightclient_patch.spec --cov-report="html:$(COV_HTML_OUT)" --cov-branch eth2spec

citest: pyspec
	mkdir -p tests/core/pyspec/test-reports/eth2spec; . venv/bin/activate; cd $(PY_SPEC_DIR); \
	python3 -m pytest -n 4 --bls-type=milagro --junitxml=eth2spec/test_results.xml eth2spec

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

lint: pyspec
	. venv/bin/activate; cd $(PY_SPEC_DIR); \
	flake8  --config $(LINTER_CONFIG_FILE) ./eth2spec \
	&& mypy --config-file $(LINTER_CONFIG_FILE) -p eth2spec.phase0 -p eth2spec.phase1 -p eth2spec.lightclient_patch

lint_generators: pyspec
	. venv/bin/activate; cd $(TEST_GENERATORS_DIR); \
	flake8  --config $(LINTER_CONFIG_FILE)

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
gen_%: $(TEST_VECTOR_DIR)
	$(call run_generator,$*)
