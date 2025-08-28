all: help

# A list of executable specifications.
# These must pass a strict linter.
ALL_EXECUTABLE_SPEC_NAMES = \
	phase0    \
	altair    \
	bellatrix \
	capella   \
	deneb     \
	electra   \
	fulu      \
	gloas     \
	eip6800   \
	eip7441   \
	eip7805   \
	eip7928

# A list of fake targets.
.PHONY: \
	clean         \
	coverage      \
	help          \
	kzg_setups    \
	lint          \
	pyspec        \
	reftests      \
	serve_docs    \
	test

###############################################################################
# Help
###############################################################################

BOLD = $(shell tput bold)
NORM = $(shell tput sgr0)

# Print target descriptions.
help: MAYBE_VERBOSE := $(if $(filter true,$(verbose)),true)
help:
	@if [ "$(MAYBE_VERBOSE)" = "true" ]; then \
		$(MAKE) -s help-verbose; \
	else \
		$(MAKE) -s help-nonverbose; \
	fi

# Print basic help output.
help-nonverbose:
	@echo "make $(BOLD)clean$(NORM)      -- delete all untracked files"
	@echo "make $(BOLD)comptests$(NORM)  -- generate compliance tests"
	@echo "make $(BOLD)coverage$(NORM)   -- run pyspec tests with coverage"
	@echo "make $(BOLD)kzg_setups$(NORM) -- generate trusted setups"
	@echo "make $(BOLD)lint$(NORM)       -- run the linters"
	@echo "make $(BOLD)pyspec$(NORM)     -- build python specifications"
	@echo "make $(BOLD)reftests$(NORM)   -- generate reference tests"
	@echo "make $(BOLD)serve_docs$(NORM) -- start a local docs web server"
	@echo "make $(BOLD)test$(NORM)       -- run pyspec tests"
	@echo ""
	@echo "Run $(BOLD)make help verbose=true$(NORM) for detailed usage/examples"

# Print verbose help output.
help-verbose:
	@echo ""
	@echo "$(BOLD)BUILDING$(NORM)"
	@echo "$(BOLD)--------------------------------------------------------------------------------$(NORM)"
	@echo ""
	@echo "$(BOLD)make pyspec$(NORM)"
	@echo ""
	@echo "  Builds Python specifications for all consensus phases. This command installs"
	@echo "  the eth2spec package and copies mainnet/minimal configs to the test directory."
	@echo "  Must be run before testing or linting."
	@echo ""
	@echo "  Example: make pyspec"
	@echo ""
	@echo "$(BOLD)TESTING$(NORM)"
	@echo "$(BOLD)--------------------------------------------------------------------------------$(NORM)"
	@echo ""
	@echo "$(BOLD)make test$(NORM)"
	@echo ""
	@echo "  Runs pyspec tests with various configuration options. Tests run in parallel"
	@echo "  by default using pytest with the minimal preset and fastest BLS library."
	@echo ""
	@echo "  Parameters:"
	@echo "    k=<test>        Run specific test by name"
	@echo "    fork=<fork>     Test specific fork (phase0, altair, bellatrix, capella, deneb, etc.)"
	@echo "    preset=<preset> Use specific preset (mainnet or minimal, default: minimal)"
	@echo "    bls=<type>      BLS library type (fastest, arkworks, default: fastest)"
	@echo ""
	@echo "  Examples:"
	@echo "    make test"
	@echo "    make test k=test_verify_kzg_proof"
	@echo "    make test fork=deneb"
	@echo "    make test preset=mainnet"
	@echo "    make test preset=mainnet fork=deneb k=test_verify_kzg_proof"
	@echo "    make test bls=arkworks"
	@echo ""
	@echo "$(BOLD)make coverage$(NORM)"
	@echo ""
	@echo "  Runs tests with code coverage tracking and generates an HTML report."
	@echo "  Automatically opens the coverage report in your browser after completion."
	@echo ""
	@echo "  Parameters:"
	@echo "    k=<test>    Run specific test by name"
	@echo "    fork=<fork> Test specific fork"
	@echo ""
	@echo "  Examples:"
	@echo "    make coverage"
	@echo "    make coverage k=test_process_attestation"
	@echo "    make coverage fork=electra"
	@echo ""
	@echo "$(BOLD)CODE QUALITY$(NORM)"
	@echo "$(BOLD)--------------------------------------------------------------------------------$(NORM)"
	@echo ""
	@echo "$(BOLD)make lint$(NORM)"
	@echo ""
	@echo "  Runs all linters and formatters to check code quality:"
	@echo "    - mdformat: Formats markdown files (80 char wrap, numbered lists)"
	@echo "    - codespell: Checks for spelling mistakes"
	@echo "    - ruff: Python linter and formatter"
	@echo "    - mypy: Static type checker for Python"
	@echo ""
	@echo "  Example: make lint"
	@echo ""
	@echo "$(BOLD)TEST GENERATION$(NORM)"
	@echo "$(BOLD)--------------------------------------------------------------------------------$(NORM)"
	@echo ""
	@echo "$(BOLD)make reftests$(NORM)"
	@echo ""
	@echo "  Generates reference test vectors for consensus spec tests. These tests are"
	@echo "  used by client implementations to verify correctness."
	@echo ""
	@echo "  Parameters:"
	@echo "    runner=<runner>   Generate tests for specific runner (bls, operations, etc.)"
	@echo "    k=<test>          Generate specific test cases (comma-separated)"
	@echo "    fork=<fork>       Generate for specific fork (comma-separated)"
	@echo "    preset=<preset>   Generate for specific preset (comma-separated)"
	@echo "    threads=N         Number of threads to use (default: auto)"
	@echo "    verbose=true      Enable verbose output"
	@echo ""
	@echo "  Examples:"
	@echo "    make reftests"
	@echo "    make reftests runner=bls"
	@echo "    make reftests runner=operations k=invalid_committee_index"
	@echo "    make reftests runner=operations fork=fulu"
	@echo "    make reftests runner=operations preset=mainnet"
	@echo "    make reftests runner=operations k=invalid_committee_index,invalid_too_many_committee_bits"
	@echo "    make reftests runner=operations preset=mainnet fork=fulu k=invalid_committee_index"
	@echo "    make reftests runner=bls threads=1 verbose=true"
	@echo ""
	@echo "$(BOLD)make comptests$(NORM)"
	@echo ""
	@echo "  Generates compliance tests for fork choice. These tests verify that"
	@echo "  implementations correctly handle fork choice scenarios."
	@echo ""
	@echo "  Parameters:"
	@echo "    fc_gen_config=<config> Configuration size (tiny, small, standard, default: tiny)"
	@echo "    fork=<fork>            Generate for specific fork (comma-separated)"
	@echo "    preset=<preset>        Generate for specific preset (comma-separated)"
	@echo "    threads=N              Number of threads to use"
	@echo ""
	@echo "  Examples:"
	@echo "    make comptests"
	@echo "    make comptests fc_gen_config=standard"
	@echo "    make comptests fc_gen_config=standard fork=deneb preset=mainnet threads=8"
	@echo ""
	@echo "$(BOLD)make kzg_setups$(NORM)"
	@echo ""
	@echo "  Generates KZG trusted setup files for testing. Creates trusted setups for"
	@echo "  both minimal and mainnet presets with predefined parameters."
	@echo ""
	@echo "  Example: make kzg_setups"
	@echo ""
	@echo "$(BOLD)DOCUMENTATION$(NORM)"
	@echo "$(BOLD)--------------------------------------------------------------------------------$(NORM)"
	@echo ""
	@echo "$(BOLD)make serve_docs$(NORM)"
	@echo ""
	@echo "  Builds and serves the documentation locally using MkDocs. Copies spec files,"
	@echo "  removes deprecated content, and starts a local web server for viewing docs."
	@echo ""
	@echo "  Example: make serve_docs"
	@echo "  Then open: http://127.0.0.1:8000"
	@echo ""
	@echo "$(BOLD)MAINTENANCE$(NORM)"
	@echo "$(BOLD)--------------------------------------------------------------------------------$(NORM)"
	@echo ""
	@echo "$(BOLD)make clean$(NORM)"
	@echo ""
	@echo "  Removes all untracked files using 'git clean -fdx'. This includes:"
	@echo "    - Virtual environment (venv/)"
	@echo "    - Build artifacts"
	@echo "    - Cache files"
	@echo "    - Generated test files"
	@echo ""
	@echo "  $(BOLD)WARNING:$(NORM) This will delete ALL untracked files. Make sure to commit or"
	@echo "           stash any important changes first."
	@echo ""
	@echo "  Example: make clean"
	@echo ""

###############################################################################
# Virtual Environment
###############################################################################

VENV = venv
PYTHON_VENV = $(VENV)/bin/python3
PIP_VENV = $(VENV)/bin/pip3
CODESPELL_VENV = $(VENV)/bin/codespell
MDFORMAT_VENV = $(VENV)/bin/mdformat
MKDOCS_VENV = $(VENV)/bin/mkdocs

# Make a virtual environment.
$(VENV):
	@echo "Creating virtual environment"
	@python3 -m venv $(VENV)
	@$(PIP_VENV) install --quiet --upgrade uv

###############################################################################
# Specification
###############################################################################

TEST_LIBS_DIR = $(CURDIR)/tests/core
PYSPEC_DIR = $(TEST_LIBS_DIR)/pyspec

# Create the pyspec for all phases.
pyspec: $(VENV) setup.py pyproject.toml
	@$(PYTHON_VENV) -m uv pip install --reinstall-package=eth2spec .[docs,lint,test,generator]
	@for dir in $(ALL_EXECUTABLE_SPEC_NAMES); do \
	    mkdir -p "./tests/core/pyspec/eth2spec/$$dir"; \
	    cp "./build/lib/eth2spec/$$dir/mainnet.py" "./tests/core/pyspec/eth2spec/$$dir/mainnet.py"; \
	    cp "./build/lib/eth2spec/$$dir/minimal.py" "./tests/core/pyspec/eth2spec/$$dir/minimal.py"; \
	done

###############################################################################
# Testing
###############################################################################

TEST_REPORT_DIR = $(PYSPEC_DIR)/test-reports

# Run pyspec tests.
#
# To run a specific test, append k=<test>, eg:
#   make test k=test_verify_kzg_proof
# To run tests for a specific fork, append fork=<fork>, eg:
#   make test fork=deneb
# To run tests for a specific preset, append preset=<preset>, eg:
#   make test preset=mainnet
# Or all at the same time, eg:
#   make test preset=mainnet fork=deneb k=test_verify_kzg_proof
# To run tests with a specific bls library, append bls=<bls>, eg:
#   make test bls=arkworks
test: MAYBE_TEST := $(if $(k),-k=$(k))
# Disable parallelism which running a specific test.
# Parallelism makes debugging difficult (print doesn't work).
test: MAYBE_PARALLEL := $(if $(k),,-n auto)
test: MAYBE_FORK := $(if $(fork),--fork=$(fork))
test: PRESET := --preset=$(if $(preset),$(preset),minimal)
test: BLS := --bls-type=$(if $(bls),$(bls),fastest)
test: pyspec
	@mkdir -p $(TEST_REPORT_DIR)
	@$(PYTHON_VENV) -m pytest \
		$(MAYBE_PARALLEL) \
		--capture=no \
		$(MAYBE_TEST) \
		$(MAYBE_FORK) \
		$(PRESET) \
		$(BLS) \
		--junitxml=$(TEST_REPORT_DIR)/test_results.xml \
		$(CURDIR)/tests/infra \
		$(PYSPEC_DIR)/eth2spec

###############################################################################
# Coverage
###############################################################################

TEST_PRESET_TYPE ?= minimal
COV_HTML_OUT=$(PYSPEC_DIR)/.htmlcov
COV_INDEX_FILE=$(COV_HTML_OUT)/index.html
COVERAGE_SCOPE := $(foreach S,$(ALL_EXECUTABLE_SPEC_NAMES), --cov=eth2spec.$S.$(TEST_PRESET_TYPE))

# Run pytest with coverage tracking
_test_with_coverage: MAYBE_TEST := $(if $(k),-k=$(k))
_test_with_coverage: MAYBE_FORK := $(if $(fork),--fork=$(fork))
_test_with_coverage: pyspec
	@$(PYTHON_VENV) -m pytest \
		-n auto \
		$(MAYBE_TEST) \
		$(MAYBE_FORK) \
		--disable-bls \
		$(COVERAGE_SCOPE) \
		--cov-report="html:$(COV_HTML_OUT)" \
		--cov-branch \
		$(PYSPEC_DIR)/eth2spec

# Run tests with coverage then open the coverage report.
# See `make test` for a list of options.
coverage: _test_with_coverage
	@echo "Opening result: $(COV_INDEX_FILE)"
	@((open "$(COV_INDEX_FILE)" || xdg-open "$(COV_INDEX_FILE)") &> /dev/null) &

###############################################################################
# Documentation
###############################################################################

DOCS_DIR = ./docs
FORK_CHOICE_DIR = ./fork_choice
SPEC_DIR = ./specs
SSZ_DIR = ./ssz
SYNC_DIR = ./sync

# Copy files to the docs directory.
_copy_docs:
	@cp -r $(SPEC_DIR) $(DOCS_DIR)
	@rm -rf $(DOCS_DIR)/specs/_deprecated
	@rm -rf $(DOCS_DIR)/specs/_features
	@cp -r $(SYNC_DIR) $(DOCS_DIR)
	@cp -r $(SSZ_DIR) $(DOCS_DIR)
	@cp -r $(FORK_CHOICE_DIR) $(DOCS_DIR)
	@cp $(CURDIR)/README.md $(DOCS_DIR)/README.md

# Start a local documentation server.
serve_docs: pyspec _copy_docs
	@$(MKDOCS_VENV) build
	@$(MKDOCS_VENV) serve

###############################################################################
# Checks
###############################################################################

MYPY_CONFIG = $(CURDIR)/mypy.ini
PYLINT_CONFIG = $(CURDIR)/pylint.ini

PYLINT_SCOPE := $(foreach S,$(ALL_EXECUTABLE_SPEC_NAMES), $(PYSPEC_DIR)/eth2spec/$S)
MYPY_SCOPE := $(foreach S,$(ALL_EXECUTABLE_SPEC_NAMES), -p eth2spec.$S)
MARKDOWN_FILES := $(shell find $(CURDIR) -name '*.md')

# Check for mistakes.
lint: pyspec
	@$(MDFORMAT_VENV) --number --wrap=80 $(MARKDOWN_FILES)
	@$(CODESPELL_VENV) . --skip "./.git,$(VENV),$(PYSPEC_DIR)/.mypy_cache" -I .codespell-whitelist
	@$(PYTHON_VENV) -m ruff check --fix --quiet $(CURDIR)/tests $(CURDIR)/pysetup $(CURDIR)/setup.py
	@$(PYTHON_VENV) -m ruff format --quiet $(CURDIR)/tests $(CURDIR)/pysetup $(CURDIR)/setup.py
	@$(PYTHON_VENV) -m mypy --config-file $(MYPY_CONFIG) $(MYPY_SCOPE)

###############################################################################
# Generators
###############################################################################

COMMA:= ,
TEST_VECTOR_DIR = $(CURDIR)/../consensus-spec-tests/tests

# Generate reference tests.
# This will forcibly rebuild pyspec just in case.
# To generate reference tests for a single runner, append runner=<runner>, eg:
#   make reftests runner=bls
# To generate reference tests with more details, append verbose=true, eg:
#   make reftests runner=bls verbose=true
# To generate reference tests with fewer threads, append threads=N, eg:
#   make reftests runner=bls threads=1
# To generate reference tests for a specific test, append k=<test>, eg:
#   make reftests runner=operations k=invalid_committee_index
# To generate reference tests for a specific fork, append fork=<fork>, eg:
#   make reftests runner=operations fork=fulu
# To generate reference tests for a specific preset, append preset=<preset>, eg:
#   make reftests runner=operations preset=mainnet
# To generate reference tests for a list of tests, forks, and/or presets, append them as comma-separated lists, eg:
#   make reftests runner=operations k=invalid_committee_index,invalid_too_many_committee_bits
# Or all at the same time, eg:
#   make reftests runner=operations preset=mainnet fork=fulu k=invalid_committee_index
reftests: MAYBE_VERBOSE := $(if $(filter true,$(verbose)),--verbose)
reftests: MAYBE_THREADS := $(if $(threads),--threads=$(threads))
reftests: MAYBE_RUNNERS := $(if $(runner),--runners $(subst ${COMMA}, ,$(runner)))
reftests: MAYBE_TESTS := $(if $(k),--cases $(subst ${COMMA}, ,$(k)))
reftests: MAYBE_FORKS := $(if $(fork),--forks $(subst ${COMMA}, ,$(fork)))
reftests: MAYBE_PRESETS := $(if $(preset),--presets $(subst ${COMMA}, ,$(preset)))
reftests: pyspec
	@$(PYTHON_VENV) -m tests.generators.main \
		--output $(TEST_VECTOR_DIR) \
		$(MAYBE_VERBOSE) \
		$(MAYBE_THREADS) \
		$(MAYBE_RUNNERS) \
		$(MAYBE_TESTS) \
		$(MAYBE_FORKS) \
		$(MAYBE_PRESETS)

# Generate KZG trusted setups for testing.
kzg_setups: pyspec
	@for preset in minimal mainnet; do \
		$(PYTHON_VENV) $(CURDIR)/scripts/gen_kzg_trusted_setups.py \
			--secret=1337 \
			--g1-length=4096 \
			--g2-length=65 \
			--output-dir $(CURDIR)/presets/$$preset/trusted_setups; \
	done

COMP_TEST_VECTOR_DIR = $(CURDIR)/../compliance-spec-tests/tests

# Generate compliance tests (fork choice).
# This will forcibly rebuild pyspec just in case.
# To generate compliance tests with a particular configuration, append fc_gen_config=<config>,
# where <config> can be either tiny, small or standard, eg:
#   make comptests fc_gen_config=standard
# One can specify threads=N, fork=<fork> or preset=<preset> as with reftests, eg:
#   make comptests fc_gen_config=standard fork=deneb preset=mainnet threads=8
comptests: FC_GEN_CONFIG := $(if $(fc_gen_config),$(fc_gen_config),tiny)
comptests: MAYBE_THREADS := $(if $(threads),--threads=$(threads),--fc-gen-multi-processing)
comptests: MAYBE_FORKS := $(if $(fork),--forks $(subst ${COMMA}, ,$(fork)))
comptests: MAYBE_PRESETS := $(if $(preset),--presets $(subst ${COMMA}, ,$(preset)))
comptests: pyspec
	@$(PYTHON_VENV) -m tests.generators.compliance_runners.fork_choice.test_gen \
		--output $(COMP_TEST_VECTOR_DIR) \
		--fc-gen-config $(FC_GEN_CONFIG) \
		$(MAYBE_THREADS) \
		$(MAYBE_FORKS) \
		$(MAYBE_PRESETS)

###############################################################################
# Cleaning
###############################################################################

# Delete all untracked files.
clean:
	@git clean -fdx
