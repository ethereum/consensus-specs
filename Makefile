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
	whisk     \
	eip6800   \
	eip7732

# A list of fake targets.
.PHONY: \
	check_toc     \
	clean         \
	coverage      \
	detect_errors \
	eth2spec      \
	gen_all       \
	gen_list      \
	help          \
	kzg_setups    \
	lint          \
	pyspec        \
	serve_docs    \
	test

###############################################################################
# Help
###############################################################################

BOLD = $(shell tput bold)
NORM = $(shell tput sgr0)

# Print target descriptions.
help:
	@echo "make $(BOLD)check_toc$(NORM)     -- check table of contents"
	@echo "make $(BOLD)clean$(NORM)         -- delete all untracked files"
	@echo "make $(BOLD)coverage$(NORM)      -- run pyspec tests with coverage"
	@echo "make $(BOLD)detect_errors$(NORM) -- detect generator errors"
	@echo "make $(BOLD)eth2spec$(NORM)      -- force rebuild eth2spec package"
	@echo "make $(BOLD)gen_<gen>$(NORM)     -- run a single generator"
	@echo "make $(BOLD)gen_all$(NORM)       -- run all generators"
	@echo "make $(BOLD)gen_list$(NORM)      -- list all generator targets"
	@echo "make $(BOLD)kzg_setups$(NORM)    -- generate trusted setups"
	@echo "make $(BOLD)lint$(NORM)          -- run the linters"
	@echo "make $(BOLD)pyspec$(NORM)        -- generate python specifications"
	@echo "make $(BOLD)serve_docs$(NORM)    -- start a local docs web server"
	@echo "make $(BOLD)test$(NORM)          -- run pyspec tests"

###############################################################################
# Virtual Environment
###############################################################################

VENV = venv
PYTHON_VENV = $(VENV)/bin/python3
PIP_VENV = $(VENV)/bin/pip3
CODESPELL_VENV = $(VENV)/bin/codespell

# Make a virtual environment will all of the necessary dependencies.
$(VENV): requirements_preinstallation.txt
	@echo "Creating virtual environment"
	@python3 -m venv $(VENV)
	@$(PIP_VENV) install -r requirements_preinstallation.txt

###############################################################################
# Specification
###############################################################################

TEST_LIBS_DIR = $(CURDIR)/tests/core
PYSPEC_DIR = $(TEST_LIBS_DIR)/pyspec
SITE_PACKAGES := $(wildcard $(VENV)/lib/python*/site-packages)
ETH2SPEC := $(SITE_PACKAGES)/eth2spec

# Install the eth2spec package.
# The pipe indicates that venv is an order-only prerequisite.
# When restoring venv cache, its timestamp is newer than eth2spec.
$(ETH2SPEC): setup.py | $(VENV)
	@$(PIP_VENV) install .[docs,lint,test,generator]

# Force rebuild/install the eth2spec package.
eth2spec:
	$(MAKE) --always-make $(ETH2SPEC)

# Create the pyspec for all phases.
pyspec: $(VENV) setup.py
	@echo "Building all pyspecs"
	@$(PYTHON_VENV) setup.py pyspecdev

###############################################################################
# Testing
###############################################################################

TEST_REPORT_DIR = $(PYSPEC_DIR)/test-reports

# Run pyspec tests.
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
test: MAYBE_FORK := $(if $(fork),--fork=$(fork))
test: PRESET := --preset=$(if $(preset),$(preset),minimal)
test: BLS := --bls-type=$(if $(bls),$(bls),fastest)
test: $(ETH2SPEC) pyspec
	@mkdir -p $(TEST_REPORT_DIR)
	@$(PYTHON_VENV) -m pytest \
		-n auto \
		$(MAYBE_TEST) \
		$(MAYBE_FORK) \
		$(PRESET) \
		$(BLS) \
		--junitxml=$(TEST_REPORT_DIR)/test_results.xml \
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
_test_with_coverage: $(ETH2SPEC) pyspec
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
	@cp -r $(SYNC_DIR) $(DOCS_DIR)
	@cp -r $(SSZ_DIR) $(DOCS_DIR)
	@cp -r $(FORK_CHOICE_DIR) $(DOCS_DIR)
	@cp $(CURDIR)/README.md $(DOCS_DIR)/README.md

# Start a local documentation server.
serve_docs: _copy_docs
	@mkdocs build
	@mkdocs serve

###############################################################################
# Checks
###############################################################################

FLAKE8_CONFIG = $(CURDIR)/flake8.ini
MYPY_CONFIG = $(CURDIR)/mypy.ini
PYLINT_CONFIG = $(CURDIR)/pylint.ini

PYLINT_SCOPE := $(foreach S,$(ALL_EXECUTABLE_SPEC_NAMES), $(PYSPEC_DIR)/eth2spec/$S)
MYPY_SCOPE := $(foreach S,$(ALL_EXECUTABLE_SPEC_NAMES), -p eth2spec.$S)
TEST_GENERATORS_DIR = ./tests/generators
MARKDOWN_FILES = $(wildcard $(SPEC_DIR)/*/*.md) \
                 $(wildcard $(SPEC_DIR)/*/*/*.md) \
                 $(wildcard $(SPEC_DIR)/_features/*/*.md) \
                 $(wildcard $(SPEC_DIR)/_features/*/*/*.md) \
                 $(wildcard $(SSZ_DIR)/*.md)

# Check all files and error if any ToC were modified.
check_toc: $(MARKDOWN_FILES:=.toc)
	@[ "$$(find . -name '*.md.tmp' -print -quit)" ] && exit 1 || exit 0

# Generate ToC sections & save copy of original if modified.
%.toc:
	@cp $* $*.tmp; \
	doctoc $* > /dev/null; \
	if diff -q $* $*.tmp > /dev/null; then \
		echo "Good $*"; \
		rm $*.tmp; \
	else \
		echo "\033[1;33m Bad $*\033[0m"; \
		echo "\033[1;34m See $*.tmp\033[0m"; \
	fi

# Check for mistakes.
lint: $(ETH2SPEC) pyspec check_toc
	@$(CODESPELL_VENV) . --skip "./.git,$(VENV),$(PYSPEC_DIR)/.mypy_cache" -I .codespell-whitelist
	@$(PYTHON_VENV) -m flake8 --config $(FLAKE8_CONFIG) $(PYSPEC_DIR)/eth2spec
	@$(PYTHON_VENV) -m flake8 --config $(FLAKE8_CONFIG) $(TEST_GENERATORS_DIR)
	@$(PYTHON_VENV) -m pylint --rcfile $(PYLINT_CONFIG) $(PYLINT_SCOPE)
	@$(PYTHON_VENV) -m mypy --config-file $(MYPY_CONFIG) $(MYPY_SCOPE)

###############################################################################
# Generators
###############################################################################

TEST_VECTOR_DIR = $(CURDIR)/../consensus-spec-tests/tests
GENERATOR_DIR = $(CURDIR)/tests/generators
SCRIPTS_DIR = $(CURDIR)/scripts
GENERATOR_ERROR_LOG_FILE = $(TEST_VECTOR_DIR)/testgen_error_log.txt
GENERATORS = $(sort $(dir $(wildcard $(GENERATOR_DIR)/*/.)))
GENERATOR_TARGETS = $(patsubst $(GENERATOR_DIR)/%/, gen_%, $(GENERATORS))

# List available generators.
gen_list:
	@for target in $(shell echo $(GENERATOR_TARGETS) | tr ' ' '\n' | sort -n); do \
		echo $$target; \
	done

# Run one generator.
# To check modules for a generator, append modcheck=true, eg:
#   make gen_genesis modcheck=true
gen_%: MAYBE_MODCHECK := $(if $(filter true,$(modcheck)),--modcheck)
gen_%: $(ETH2SPEC) pyspec
	@mkdir -p $(TEST_VECTOR_DIR)
	@$(PYTHON_VENV) $(GENERATOR_DIR)/$*/main.py \
		--output $(TEST_VECTOR_DIR) \
		$(MAYBE_MODCHECK)

# Run all generators then check for errors.
gen_all: $(GENERATOR_TARGETS) detect_errors

# Detect errors in generators.
detect_errors: $(TEST_VECTOR_DIR)
	@find $(TEST_VECTOR_DIR) -name "INCOMPLETE"
	@if [ -f $(GENERATOR_ERROR_LOG_FILE) ]; then \
		echo "[ERROR] $(GENERATOR_ERROR_LOG_FILE) file exists"; \
	else \
		echo "[PASSED] error log file does not exist"; \
	fi

# Generate KZG trusted setups for testing.
kzg_setups: $(ETH2SPEC)
	@for preset in minimal mainnet; do \
		$(PYTHON_VENV) $(SCRIPTS_DIR)/gen_kzg_trusted_setups.py \
			--secret=1337 \
			--g1-length=4096 \
			--g2-length=65 \
			--output-dir $(CURDIR)/presets/$$preset/trusted_setups; \
	done

###############################################################################
# Cleaning
###############################################################################

# Delete all untracked files.
clean:
	@git clean -fdx