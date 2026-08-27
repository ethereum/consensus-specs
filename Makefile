all: help

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
	@echo "make $(BOLD)test$(NORM)       -- run pyspec tests"
	@echo "make $(BOLD)website$(NORM)    -- build/serve website"
	@echo ""
	@echo "Run 'make $(BOLD)help verbose=true$(NORM)' to print detailed usage/examples."
	@echo ""

# Print verbose help output.
help-verbose:
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
	@echo "$(BOLD)make lint$(NORM)"
	@echo ""
	@echo "  Runs all linters, formatters, and checks:"
	@echo "    - mdformat: Formats markdown files"
	@echo "    - codespell: Checks for spelling mistakes"
	@echo "    - ruff: Python linter and formatter"
	@echo "    - ty: Static type checker for Python"
	@echo "    - Fork comments validation (scripts/check_fork_comments.py)"
	@echo "    - Markdown headings validation (scripts/check_markdown_headings.py)"
	@echo "    - Markdown note style fix (scripts/fix_note_style.py)"
	@echo "    - Trailing whitespace check"
	@echo ""
	@echo "  Example: make lint"
	@echo ""
	@echo "$(BOLD)make test$(NORM)"
	@echo ""
	@echo "  Runs pyspec tests with various configuration options. Tests run in parallel"
	@echo "  by default using pytest with the minimal preset."
	@echo ""
	@echo "  Filtering:"
	@echo "    k=<name>           Run only tests matching this name"
	@echo "    fork=<fork>        Run only tests for this fork (phase0, altair, bellatrix, capella, etc.)"
	@echo "    preset=<preset>    Preset to use: mainnet, minimal (default: minimal)"
	@echo ""
	@echo "  Output:"
	@echo "    verbose=true       Enable verbose pytest output"
	@echo "    debug=true         Enable print() output; disables parallelism"
	@echo "    reftests=true      Generate reference test vectors"
	@echo "    coverage=true      Enable code coverage tracking"
	@echo ""
	@echo "  Examples:"
	@echo "    make test"
	@echo "    make test k=test_compute_fork_digest"
	@echo "    make test k=test_compute_fork_digest debug=true"
	@echo "    make test fork=deneb"
	@echo "    make test preset=mainnet"
	@echo "    make test preset=mainnet fork=deneb k=test_compute_fork_digest"
	@echo "    make test reftests=true"
	@echo "    make test reftests=true fork=fulu"
	@echo "    make test reftests=true preset=mainnet fork=fulu k=invalid_committee_index"
	@echo "    make test coverage=true k=test_process_attestation"
	@echo "    make test coverage=true fork=electra"
	@echo ""
	@echo "$(BOLD)make comptests$(NORM)"
	@echo ""
	@echo "  Generates compliance tests. These tests verify that implementations"
	@echo "  correctly handle fork choice and state transition scenarios."
	@echo "  Uses pytest collection and xdist parallelism."
	@echo ""
	@echo "  Parameters:"
	@echo "    kind=<kind>            Test kind: fork_choice (default), state_transition"
	@echo "    fc_gen_config=<config> Configuration size (tiny, small, standard; default: tiny)"
	@echo "    fork=<fork>            Generate for specific fork (comma-separated)"
	@echo "    preset=<preset>        Generate for specific preset (comma-separated)"
	@echo "    comptests_dir=<dir>    Output directory for generated compliance tests"
	@echo "    handler=<handler>      State-transition handler (default: all)"
	@echo "    profile=<profile>      State-transition profile (smoke, standard, all; default: standard)"
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
	@echo "    make comptests kind=state_transition"
	@echo "    make comptests kind=state_transition handler=withdrawals profile=smoke"
	@echo ""
	@echo "$(BOLD)make website$(NORM)"
	@echo ""
	@echo "  Build/serve the documentation website."
	@echo ""
	@echo "  Serving:"
	@echo "    serve=true         Host the website locally"
	@echo ""
	@echo "  Examples:"
	@echo "    make website"
	@echo "    make website serve=true"
	@echo ""

###############################################################################
# Setup
###############################################################################

PYSPEC_DIR = $(CURDIR)/tests/core/pyspec

# Sync dependencies using uv.
sync: MAYBE_VERBOSE := $(if $(filter true,$(verbose)),--verbose)
sync: pyproject.toml
	@command -v uv >/dev/null 2>&1 || { \
		echo "Error: uv is required but not installed."; \
		echo "Install with: curl -LsSf https://astral.sh/uv/install.sh | sh"; \
		exit 1; \
	}
	@uv sync --all-extras $(MAYBE_VERBOSE)

# Generate executable specifications.
build: MAYBE_VERBOSE := $(if $(filter true,$(verbose)),--verbose)
build: sync
	@uv run python -m pysetup.generate_specs --all-forks $(MAYBE_VERBOSE)

# Delete all untracked files.
clean:
	@git clean -fdx

###############################################################################
# Lint
###############################################################################

LINT_DIFF_BEFORE := .lint_diff_before
LINT_DIFF_AFTER := .lint_diff_after
MARKDOWN_FILES := $(shell find $(CURDIR) -name '*.md' -not -path '$(CURDIR)/.git/*' -not -path '$(CURDIR)/.venv/*')

# Check for mistakes.
lint: sync
	@rm -f $(LINT_DIFF_BEFORE) $(LINT_DIFF_AFTER)
	@git diff > $(LINT_DIFF_BEFORE)
	@uv --quiet lock --check
	@uv run codespell
	@uv run python $(CURDIR)/scripts/fix_note_style.py
	@uv run python $(CURDIR)/scripts/fix_trailing_whitespace.py
	@uv run python $(CURDIR)/scripts/check_fork_comments.py
	@uv run python $(CURDIR)/scripts/check_markdown_headings.py
	@uv run python $(CURDIR)/scripts/check_value_annotations.py
	@uv run mdformat --number --wrap=80 $(MARKDOWN_FILES)
	@uv run ruff check --fix --quiet $(CURDIR)/tests $(CURDIR)/pysetup $(CURDIR)/specs
	@uv run ruff format --quiet $(CURDIR)/tests $(CURDIR)/pysetup
	@uv run ruff format --preview --quiet $(CURDIR)/specs
	@$(MAKE) --no-print-directory --assume-old=sync build
	@uv run ty check --no-progress \
		$(PYSPEC_DIR)/eth_consensus_specs/*/mainnet.py \
		$(PYSPEC_DIR)/eth_consensus_specs/*/minimal.py
	@git diff > $(LINT_DIFF_AFTER)
	@diff -q $(LINT_DIFF_BEFORE) $(LINT_DIFF_AFTER) >/dev/null 2>&1 || \
		echo "$(BOLD)Note: make lint modified tracked files$(NORM)"
	@rm -f $(LINT_DIFF_BEFORE) $(LINT_DIFF_AFTER)

###############################################################################
# Test
###############################################################################

TEST_REPORT_DIR = $(PYSPEC_DIR)/test-reports
REFTESTS_DIR = $(CURDIR)/reftests
COV_REPORT_DIR = $(PYSPEC_DIR)/.htmlcov
UPGRADE_NAMES := $(filter-out _features,$(notdir $(wildcard specs/*)))

# Run pyspec tests.
#
# Filtering
test: MAYBE_TEST := $(if $(k),-k "$(k)")
test: MAYBE_FORK := $(if $(fork),--fork=$(fork))
test: PRESET := $(if $(preset),--preset=$(preset),)
# Disable parallelism when debugging so print() output is visible (xdist swallows it).
test: MAYBE_PARALLEL := $(if $(filter true,$(debug)),,-n logical --dist=worksteal)
# Output
test: MAYBE_VERBOSE := $(if $(filter true,$(verbose)),-v)
test: MAYBE_REFTESTS := $(if $(filter true,$(reftests)),--reftests --reftests-output=$(REFTESTS_DIR))
test: COVERAGE_PRESETS := $(if $(preset),$(preset),$(if $(filter true,$(reftests)),minimal mainnet,minimal))
test: COV_SCOPE_SINGLE := $(foreach P,$(COVERAGE_PRESETS), --cov=eth_consensus_specs.$(fork).$P)
test: COV_SCOPE_ALL := $(foreach P,$(COVERAGE_PRESETS),$(foreach U,$(UPGRADE_NAMES), --cov=eth_consensus_specs.$U.$P))
test: COV_SCOPE := $(if $(filter true,$(coverage)),$(if $(fork),$(COV_SCOPE_SINGLE),$(COV_SCOPE_ALL)))
test: COVERAGE := $(if $(filter true,$(coverage)),--coverage $(COV_SCOPE) --cov-report="html:$(COV_REPORT_DIR)" --cov-report="json:$(COV_REPORT_DIR)/coverage.json" --cov-branch --no-cov-on-fail)
test: build
	@mkdir -p $(TEST_REPORT_DIR)
	@uv run pytest \
		$(MAYBE_PARALLEL) \
		--capture=no \
		$(MAYBE_VERBOSE) \
		$(MAYBE_TEST) \
		$(MAYBE_FORK) \
		$(PRESET) \
		--junitxml=$(TEST_REPORT_DIR)/test_results.xml \
		--html=$(TEST_REPORT_DIR)/test_results.html \
		--self-contained-html \
		$(MAYBE_REFTESTS) \
		$(COVERAGE) \
		$(PYSPEC_DIR)/eth_consensus_specs

COMMA:= ,
DEFAULT_COMPTESTS_DIR = $(CURDIR)/../compliance-spec-tests/tests
COMPTESTS_DIR = $(if $(comptests_dir),$(comptests_dir),$(DEFAULT_COMPTESTS_DIR))
COMPTESTS_KIND = $(if $(kind),$(kind),fork_choice)

ifeq ($(COMPTESTS_KIND),fork_choice)

# Generate compliance tests (fork choice).
comptests: FC_GEN_CONFIG := $(if $(fc_gen_config),$(fc_gen_config),tiny)
comptests: MAYBE_TEST := $(if $(k),-k "$(k)")
comptests: MAYBE_PARALLEL := $(if $(filter 1,$(threads)),,$(if $(threads),-n $(threads) --dist=worksteal,-n logical --dist=worksteal))
comptests: MAYBE_FORKS := $(foreach F,$(subst ${COMMA}, ,$(fork)),--forks $(F))
comptests: MAYBE_PRESETS := $(foreach P,$(subst ${COMMA}, ,$(preset)),--presets $(P))
comptests: MAYBE_SEED := $(if $(seed),--fc-gen-seed $(seed))
comptests: MAYBE_GROUP_SLICE_INDEX := $(if $(group_slice_index),--group-slice-index $(group_slice_index))
comptests: MAYBE_GROUP_SLICE_COUNT := $(if $(group_slice_count),--group-slice-count $(group_slice_count))
comptests: build
	@uv run pytest \
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

else ifeq ($(COMPTESTS_KIND),state_transition)

# Generate compliance tests (state transition).
comptests: MAYBE_HANDLER := $(if $(handler),--handler $(handler))
comptests: MAYBE_PROFILE := $(if $(profile),--profile $(profile))
comptests: MAYBE_PARALLEL := $(if $(filter 1,$(threads)),,$(if $(threads),-n $(threads) --dist=worksteal,-n logical --dist=worksteal))
comptests: _pyspec
	@$(UV_RUN) pytest \
		$(MAYBE_PARALLEL) \
		--capture=no \
		--comptests-output=$(COMPTESTS_DIR) \
		$(MAYBE_HANDLER) \
		$(MAYBE_PROFILE) \
		$(CURDIR)/tests/generators/compliance_runners/state_transition/generate_comptests.py

else

comptests:
	@echo "Unsupported compliance test kind: $(COMPTESTS_KIND)" >&2
	@exit 1

endif

###############################################################################
# Website
###############################################################################

DOCS_CONFIG = ./zensical.toml
DOCS_BUILD_CONFIG = ./.zensical.build.toml
DOCS_DIR = ./docs
SPEC_DIR = ./specs

# Build/serve the documentation website.
website: sync
	@rm -rf $(DOCS_DIR)
	@mkdir -p $(DOCS_DIR)
	@cp -r $(SPEC_DIR) $(DOCS_DIR)/specs
	@cp $(CURDIR)/README.md $(DOCS_DIR)/index.md
	@uv run python $(CURDIR)/scripts/strip_inline_tocs.py $(DOCS_DIR)
	@uv run python $(CURDIR)/scripts/gen_spec_indices.py $(DOCS_DIR) $(DOCS_CONFIG) $(DOCS_BUILD_CONFIG)
ifeq ($(serve),true)
	@uv run zensical serve -f $(DOCS_BUILD_CONFIG)
else
	@uv run zensical build --clean --strict -f $(DOCS_BUILD_CONFIG)
endif
