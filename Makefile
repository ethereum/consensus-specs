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
	heze      \
	eip8025

# A list of fake targets.
.PHONY: \
	_sync         \
	clean         \
	help          \
	lint          \
	serve_docs    \
	test

###############################################################################
# Help
###############################################################################

BOLD := $(shell tput bold)
NORM := $(shell tput sgr0)

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
	@echo "make $(BOLD)lint$(NORM)       -- run linters and checks"
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
	@echo "  Filtering:"
	@echo "    k=<name>           Run only tests matching this name"
	@echo "    fork=<fork>        Run only tests for this fork (phase0, altair, bellatrix, capella, etc.)"
	@echo "    preset=<preset>    Preset to use: mainnet, minimal (default: minimal)"
	@echo "    component=<comp>   What to test: all, pyspec, fw (default: all)"
	@echo ""
	@echo "  Libraries:"
	@echo "    bls=<type>         BLS library: py_ecc, milagro, arkworks, fastest (default: fastest)"
	@echo "    kzg=<type>         KZG library: spec, ckzg (default: ckzg)"
	@echo ""
	@echo "  Output:"
	@echo "    verbose=true       Enable verbose pytest output"
	@echo "    reftests=true      Generate reference test vectors"
	@echo "    coverage=true      Enable code coverage tracking"
	@echo ""
	@echo "  Examples:"
	@echo "    make test"
	@echo "    make test k=test_verify_kzg_proof"
	@echo "    make test fork=deneb"
	@echo "    make test preset=mainnet"
	@echo "    make test preset=mainnet fork=deneb k=test_verify_kzg_proof"
	@echo "    make test component=fw"
	@echo "    make test bls=arkworks"
	@echo "    make test reftests=true"
	@echo "    make test reftests=true fork=fulu"
	@echo "    make test reftests=true preset=mainnet fork=fulu k=invalid_committee_index"
	@echo "    make test coverage=true k=test_process_attestation"
	@echo "    make test coverage=true fork=electra"
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
	@echo "$(BOLD)make comptests$(NORM)"
	@echo ""
	@echo "  Generates compliance tests for fork choice. These tests verify that"
	@echo "  implementations correctly handle fork choice scenarios."
	@echo "  Uses pytest collection and xdist parallelism."
	@echo ""
	@echo "  Parameters:"
	@echo "    fc_gen_config=<config> Configuration size (tiny, small, standard; default: tiny)"
	@echo "    fork=<fork>            Generate for specific fork (comma-separated)"
	@echo "    preset=<preset>        Generate for specific preset (comma-separated)"
	@echo "    comptests_dir=<dir>    Output directory for generated compliance tests"
	@echo "    threads=N              Number of threads to use"
	@echo "    seed=N                 Override test seeds (fuzzing mode)"
	@echo "    group_slice_index=N    0-based shard index for deterministic test-group slicing"
	@echo "    group_slice_count=N    Number of deterministic test-group slices"
	@echo "    k=<name>               Run only generated cases matching this pytest pattern"
	@echo ""
	@echo "  Examples:"
	@echo "    make comptests"
	@echo "    make comptests fc_gen_config=standard"
	@echo "    make comptests comptests_dir=./compliance-spec-tests/tests"
	@echo "    make comptests fc_gen_config=standard fork=deneb preset=mainnet threads=8"
	@echo "    make comptests fc_gen_config=tiny fork=gloas group_slice_index=0 group_slice_count=4"
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

UV_RUN    = uv run

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
REFTESTS_DIR = $(CURDIR)/reftests
COV_REPORT_DIR = $(PYSPEC_DIR)/.htmlcov

# Run pyspec tests.
#
# Filtering
test: MAYBE_TEST := $(if $(k),-k "$(k)")
test: MAYBE_FORK := $(if $(fork),--fork=$(fork))
test: PRESET := $(if $(filter fw,$(component)),,$(if $(preset),--preset=$(preset),))
# Disable parallelism when running a specific test. Makes debugging difficult (print doesn't work).
test: MAYBE_PARALLEL := $(if $(k),,-n logical --dist=worksteal)
test: MAYBE_SPEC := $(if $(filter fw,$(component)),,$(PYSPEC_DIR)/eth_consensus_specs)
test: MAYBE_INFRA := $(if $(filter pyspec,$(component)),,$(CURDIR)/tests/infra)
#
# Libraries
test: BLS := $(if $(filter fw,$(component)),,--bls-type=$(if $(bls),$(bls),fastest))
test: KZG := $(if $(filter fw,$(component)),,--kzg-type=$(if $(kzg),$(kzg),ckzg))
#
# Output
test: MAYBE_VERBOSE := $(if $(filter true,$(verbose)),-v)
test: MAYBE_REFTESTS := $(if $(filter true,$(reftests)),--reftests --reftests-output=$(REFTESTS_DIR))
test: COVERAGE_PRESETS := $(if $(preset),$(preset),$(if $(filter true,$(reftests)),minimal mainnet,minimal))
test: COV_SCOPE_SINGLE := $(foreach P,$(COVERAGE_PRESETS), --cov=eth_consensus_specs.$(fork).$P)
test: COV_SCOPE_ALL := $(foreach P,$(COVERAGE_PRESETS),$(foreach S,$(ALL_EXECUTABLE_SPEC_NAMES), --cov=eth_consensus_specs.$S.$P))
test: COV_SCOPE := $(if $(filter true,$(coverage)),$(if $(fork),$(COV_SCOPE_SINGLE),$(COV_SCOPE_ALL)))
test: COVERAGE := $(if $(filter true,$(coverage)),--coverage $(COV_SCOPE) --cov-report="html:$(COV_REPORT_DIR)" --cov-report="json:$(COV_REPORT_DIR)/coverage.json" --cov-branch --no-cov-on-fail)
test: _pyspec
	@mkdir -p $(TEST_REPORT_DIR)
	@$(UV_RUN) pytest \
		$(MAYBE_PARALLEL) \
		--capture=no \
		$(MAYBE_VERBOSE) \
		$(MAYBE_TEST) \
		$(MAYBE_FORK) \
		$(PRESET) \
		$(BLS) \
		$(KZG) \
		--junitxml=$(TEST_REPORT_DIR)/test_results.xml \
		--html=$(TEST_REPORT_DIR)/test_results.html \
		--self-contained-html \
		$(MAYBE_REFTESTS) \
		$(COVERAGE) \
		$(MAYBE_INFRA) \
		$(MAYBE_SPEC)


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
MARKDOWN_FILES := $(shell find $(CURDIR) -name '*.md' -not -path '$(CURDIR)/.*')
MYPY_PACKAGE_BASE := $(subst /,.,$(PYSPEC_DIR:$(CURDIR)/%=%))
MYPY_SCOPE := $(foreach S,$(ALL_EXECUTABLE_SPEC_NAMES), -p $(MYPY_PACKAGE_BASE).eth_consensus_specs.$S)

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
DEFAULT_COMPTESTS_DIR = $(CURDIR)/../compliance-spec-tests/tests
COMPTESTS_DIR = $(if $(comptests_dir),$(comptests_dir),$(DEFAULT_COMPTESTS_DIR))

# Generate compliance tests (fork choice).
comptests: FC_GEN_CONFIG := $(if $(fc_gen_config),$(fc_gen_config),tiny)
comptests: MAYBE_TEST := $(if $(k),-k "$(k)")
comptests: MAYBE_PARALLEL := $(if $(filter 1,$(threads)),,$(if $(threads),-n $(threads) --dist=worksteal,-n logical --dist=worksteal))
comptests: MAYBE_FORKS := $(foreach F,$(subst ${COMMA}, ,$(fork)),--forks $(F))
comptests: MAYBE_PRESETS := $(foreach P,$(subst ${COMMA}, ,$(preset)),--presets $(P))
comptests: MAYBE_SEED := $(if $(seed),--fc-gen-seed $(seed))
comptests: MAYBE_GROUP_SLICE_INDEX := $(if $(group_slice_index),--group-slice-index $(group_slice_index))
comptests: MAYBE_GROUP_SLICE_COUNT := $(if $(group_slice_count),--group-slice-count $(group_slice_count))
comptests: _pyspec
	@$(UV_RUN) pytest \
		$(MAYBE_PARALLEL) \
		--capture=no \
		$(MAYBE_TEST) \
		--comptests-output=$(COMPTESTS_DIR) \
		--fc-gen-config $(FC_GEN_CONFIG) \
		$(MAYBE_FORKS) \
		$(MAYBE_PRESETS) \
		$(MAYBE_SEED) \
		$(MAYBE_GROUP_SLICE_INDEX) \
		$(MAYBE_GROUP_SLICE_COUNT) \
		$(CURDIR)/tests/generators/compliance_runners/fork_choice/generate_comptests.py

###############################################################################
# Cleaning
###############################################################################

# Delete all untracked files.
clean:
	@git clean -fdx
