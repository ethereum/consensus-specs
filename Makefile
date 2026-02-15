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
	eip7928   \
	eip8025

# A list of fake targets.
.PHONY: \
	_sync         \
	clean         \
	coverage      \
	help          \
	lint          \
	reftests      \
	serve_docs    \
	test

###############################################################################
# Help
###############################################################################

BOLD = $(shell tput bold)
NORM = $(shell tput sgr0)

# Print help.
help:
ifeq ($(verbose),true)
	@$(MAKE) -s help-verbose
else
	@$(MAKE) -s help-nonverbose
endif

# Print basic help output.
help-nonverbose:
	@echo "make $(BOLD)clean$(NORM)      -- delete all untracked files"
	@echo "make $(BOLD)comptests$(NORM)  -- generate compliance tests"
	@echo "make $(BOLD)coverage$(NORM)   -- run pyspec tests with coverage"
	@echo "make $(BOLD)lint$(NORM)       -- run linters and checks"
	@echo "make $(BOLD)reftests$(NORM)   -- generate reference tests"
	@echo "make $(BOLD)serve_docs$(NORM) -- start a local docs web server"
	@echo "make $(BOLD)test$(NORM)       -- run pyspec tests"
	@echo ""
	@echo "Run 'make $(BOLD)help verbose=true$(NORM)' to print detailed usage/examples."
	@echo ""

# Print verbose help output.
help-verbose:
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
	@echo "    k=<test>          Run specific test by name"
	@echo "    fork=<fork>       Test specific fork (phase0, altair, bellatrix, capella, etc.)"
	@echo "    preset=<preset>   Use specific preset (mainnet or minimal; default: minimal)"
	@echo "    bls=<type>        BLS library type (py_ecc, milagro, arkworks, fastest; default: fastest)"
	@echo "    component=<value> Test component: (all, pyspec, fw; default: all)"
	@echo ""
	@echo "  Examples:"
	@echo "    make test"
	@echo "    make test k=test_verify_kzg_proof"
	@echo "    make test fork=deneb"
	@echo "    make test preset=mainnet"
	@echo "    make test preset=mainnet fork=deneb k=test_verify_kzg_proof"
	@echo "    make test bls=arkworks"
	@echo "    make test component=fw"
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
	@echo "  Runs all linters, formatters, and checks:"
	@echo "    - mdformat: Formats markdown files"
	@echo "    - codespell: Checks for spelling mistakes"
	@echo "    - ruff: Python linter and formatter"
	@echo "    - mypy: Static type checker for Python"
	@echo "    - Fork comments validation (scripts/check_fork_comments.py)"
	@echo "    - Markdown headings validation (scripts/check_markdown_headings.py)"
	@echo "    - Trailing whitespace check"
	@echo ""
	@echo "  Example: make lint"
	@echo ""
	@echo "$(BOLD)TEST GENERATION$(NORM)"
	@echo "$(BOLD)--------------------------------------------------------------------------------$(NORM)"
	@echo ""
	@echo "$(BOLD)make reftests$(NORM)"
	@echo ""
	@echo "  Generates reference test vectors for consensus spec tests. These tests are"
	@echo "  used by client implementations to verify correctness. This command will write"
	@echo "  reference tests to the ../consensus-spec-tests/ directory."
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
	@echo "    fc_gen_config=<config> Configuration size (tiny, small, standard; default: tiny)"
	@echo "    fork=<fork>            Generate for specific fork (comma-separated)"
	@echo "    preset=<preset>        Generate for specific preset (comma-separated)"
	@echo "    threads=N              Number of threads to use"
	@echo "    seed=N                 Override test seeds (fuzzing mode)"
	@echo ""
	@echo "  Examples:"
	@echo "    make comptests"
	@echo "    make comptests fc_gen_config=standard"
	@echo "    make comptests fc_gen_config=standard fork=deneb preset=mainnet threads=8"
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
	@echo "  Removes all untracked files. This includes:"
	@echo "    - Virtual environment (.venv/)"
	@echo "    - Build artifacts"
	@echo "    - Cache files"
	@echo ""
	@echo "  $(BOLD)WARNING:$(NORM) This will delete ALL untracked files. Make sure to commit or"
	@echo "           stash any important changes first."
	@echo ""
	@echo "  Example: make clean"
	@echo ""

###############################################################################
# Virtual Environment
###############################################################################

VENV = .venv

# Use editable installs for all non-generation targets, but use non-editable
# installs for generators. More details: ethereum/consensus-specs#4633.
UV_RUN    = uv run
UV_RUN_NE = uv run --no-editable --reinstall-package=eth2spec

# Sync dependencies using uv.
_sync: MAYBE_VERBOSE := $(if $(filter true,$(verbose)),--verbose)
_sync: pyproject.toml
	@command -v uv >/dev/null 2>&1 || { \
		echo "Error: uv is required but not installed."; \
		echo "Install with: curl -LsSf https://astral.sh/uv/install.sh | sh"; \
		exit 1; \
	}
	@uv sync --all-extras $(MAYBE_VERBOSE)

###############################################################################
# Specification
###############################################################################

TEST_LIBS_DIR = $(CURDIR)/tests/core
PYSPEC_DIR = $(TEST_LIBS_DIR)/pyspec

# Create the pyspec for all phases.
_pyspec: MAYBE_VERBOSE := $(if $(filter true,$(verbose)),--verbose)
_pyspec: _sync
	@$(UV_RUN) python -m pysetup.generate_specs --all-forks $(MAYBE_VERBOSE)

###############################################################################
# Testing
###############################################################################

TEST_REPORT_DIR = $(PYSPEC_DIR)/test-reports

# Run pyspec tests.
test: MAYBE_TEST := $(if $(k),-k=$(k))
# Disable parallelism when running a specific test.
# Parallelism makes debugging difficult (print doesn't work).
test: MAYBE_PARALLEL := $(if $(k),,-n auto)
test: MAYBE_FORK := $(if $(fork),--fork=$(fork))
test: PRESET := $(if $(filter fw,$(component)),,--preset=$(if $(preset),$(preset),minimal))
test: BLS := $(if $(filter fw,$(component)),,--bls-type=$(if $(bls),$(bls),fastest))
test: MAYBE_ETH2SPEC := $(if $(filter fw,$(component)),,$(PYSPEC_DIR)/eth2spec)
test: MAYBE_INFRA := $(if $(filter pyspec,$(component)),,$(CURDIR)/tests/infra)
test: _pyspec
	@mkdir -p $(TEST_REPORT_DIR)
	@$(UV_RUN) pytest \
		$(MAYBE_PARALLEL) \
		--capture=no \
		$(MAYBE_TEST) \
		$(MAYBE_FORK) \
		$(PRESET) \
		$(BLS) \
		--junitxml=$(TEST_REPORT_DIR)/test_results.xml \
		--html=$(TEST_REPORT_DIR)/test_results.html \
		--self-contained-html \
		$(MAYBE_INFRA) \
		$(MAYBE_ETH2SPEC)

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
_test_with_coverage: _pyspec
	@$(UV_RUN) pytest \
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
	@cp -r $(SYNC_DIR) $(DOCS_DIR)
	@cp -r $(SSZ_DIR) $(DOCS_DIR)
	@cp -r $(FORK_CHOICE_DIR) $(DOCS_DIR)
	@cp $(CURDIR)/README.md $(DOCS_DIR)/README.md

# Start a local documentation server.
serve_docs: _pyspec _copy_docs
	@$(UV_RUN) mkdocs build
	@$(UV_RUN) mkdocs serve

###############################################################################
# Checks
###############################################################################

LINT_DIFF_BEFORE := .lint_diff_before
LINT_DIFF_AFTER := .lint_diff_after
MARKDOWN_FILES := $(shell find $(CURDIR) -name '*.md')
MYPY_PACKAGE_BASE := $(subst /,.,$(PYSPEC_DIR:$(CURDIR)/%=%))
MYPY_SCOPE := $(foreach S,$(ALL_EXECUTABLE_SPEC_NAMES), -p $(MYPY_PACKAGE_BASE).eth2spec.$S)

# Check for mistakes.
lint: _pyspec
	@rm -f $(LINT_DIFF_BEFORE) $(LINT_DIFF_AFTER)
	@git diff > $(LINT_DIFF_BEFORE)
	@uv --quiet lock --check
	@$(UV_RUN) codespell
	@$(UV_RUN) python $(CURDIR)/scripts/check_fork_comments.py
	@$(UV_RUN) python $(CURDIR)/scripts/fix_trailing_whitespace.py
	@$(UV_RUN) python $(CURDIR)/scripts/check_markdown_headings.py
	@$(UV_RUN) python $(CURDIR)/scripts/check_value_annotations.py
	@$(UV_RUN) mdformat --number --wrap=80 $(MARKDOWN_FILES)
	@$(UV_RUN) ruff check --fix --quiet $(CURDIR)/tests $(CURDIR)/pysetup $(CURDIR)/setup.py
	@$(UV_RUN) ruff format --quiet $(CURDIR)/tests $(CURDIR)/pysetup $(CURDIR)/setup.py
	@output="$$($(UV_RUN) mypy $(MYPY_SCOPE) 2>&1)" || \
		{ echo "$$output"; exit 1; }
	@git diff > $(LINT_DIFF_AFTER)
	@diff -q $(LINT_DIFF_BEFORE) $(LINT_DIFF_AFTER) >/dev/null 2>&1 || \
		echo "$(BOLD)Note: make lint modified tracked files$(NORM)"
	@rm -f $(LINT_DIFF_BEFORE) $(LINT_DIFF_AFTER)

###############################################################################
# Generators
###############################################################################

COMMA:= ,
TEST_VECTOR_DIR = $(CURDIR)/../consensus-spec-tests/tests
COMP_TEST_VECTOR_DIR = $(CURDIR)/../compliance-spec-tests/tests

# Generate reference tests.
reftests: MAYBE_VERBOSE := $(if $(filter true,$(verbose)),--verbose)
reftests: MAYBE_THREADS := $(if $(threads),--threads=$(threads))
reftests: MAYBE_RUNNERS := $(if $(runner),--runners $(subst ${COMMA}, ,$(runner)))
reftests: MAYBE_TESTS := $(if $(k),--cases $(subst ${COMMA}, ,$(k)))
reftests: MAYBE_FORKS := $(if $(fork),--forks $(subst ${COMMA}, ,$(fork)))
reftests: MAYBE_PRESETS := $(if $(preset),--presets $(subst ${COMMA}, ,$(preset)))
reftests: _pyspec
	@$(UV_RUN_NE) python -m tests.generators.main \
		--output $(TEST_VECTOR_DIR) \
		$(MAYBE_VERBOSE) \
		$(MAYBE_THREADS) \
		$(MAYBE_RUNNERS) \
		$(MAYBE_TESTS) \
		$(MAYBE_FORKS) \
		$(MAYBE_PRESETS)

# Generate compliance tests (fork choice).
comptests: FC_GEN_CONFIG := $(if $(fc_gen_config),$(fc_gen_config),tiny)
comptests: MAYBE_THREADS := $(if $(threads),--threads=$(threads),--fc-gen-multi-processing)
comptests: MAYBE_FORKS := $(if $(fork),--forks $(subst ${COMMA}, ,$(fork)))
comptests: MAYBE_PRESETS := $(if $(preset),--presets $(subst ${COMMA}, ,$(preset)))
comptests: MAYBE_SEED := $(if $(seed),--fc-gen-seed $(seed))
comptests: _pyspec
	@$(UV_RUN_NE) python -m tests.generators.compliance_runners.fork_choice.test_gen \
		--output $(COMP_TEST_VECTOR_DIR) \
		--fc-gen-config $(FC_GEN_CONFIG) \
		$(MAYBE_THREADS) \
		$(MAYBE_FORKS) \
		$(MAYBE_PRESETS) \
		$(MAYBE_SEED)

###############################################################################
# Cleaning
###############################################################################

# Delete all untracked files.
clean:
	@git clean -fdx
