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
	eip6800   \
	eip7441   \
	eip7732   \
  eip7805

# A list of fake targets.
.PHONY: \
	clean         \
	coverage      \
	detect_errors \
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
	@echo "make $(BOLD)clean$(NORM)         -- delete all untracked files"
	@echo "make $(BOLD)coverage$(NORM)      -- run pyspec tests with coverage"
	@echo "make $(BOLD)detect_errors$(NORM) -- detect generator errors"
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
MDFORMAT_VENV = $(VENV)/bin/mdformat

# Make a virtual environment.
$(VENV):
	@echo "Creating virtual environment"
	@python3 -m venv $(VENV)
	@$(PIP_VENV) install --quiet uv==0.5.24

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

MYPY_CONFIG = $(CURDIR)/mypy.ini
PYLINT_CONFIG = $(CURDIR)/pylint.ini

PYLINT_SCOPE := $(foreach S,$(ALL_EXECUTABLE_SPEC_NAMES), $(PYSPEC_DIR)/eth2spec/$S)
MYPY_SCOPE := $(foreach S,$(ALL_EXECUTABLE_SPEC_NAMES), -p eth2spec.$S)
MARKDOWN_FILES = $(wildcard $(SPEC_DIR)/*/*.md) \
                 $(wildcard $(SPEC_DIR)/*/*/*.md) \
                 $(wildcard $(SPEC_DIR)/_features/*/*.md) \
                 $(wildcard $(SPEC_DIR)/_features/*/*/*.md) \
                 $(wildcard $(SSZ_DIR)/*.md)

# Check for mistakes.
lint: pyspec
	@$(MDFORMAT_VENV) --number $(MARKDOWN_FILES)
	@$(CODESPELL_VENV) . --skip "./.git,$(VENV),$(PYSPEC_DIR)/.mypy_cache" -I .codespell-whitelist
	@$(PYTHON_VENV) -m black $(CURDIR)/tests
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
# This will forcibly rebuild pyspec just in case.
# To check modules for a generator, append modcheck=true, eg:
#   make gen_genesis modcheck=true
gen_%: MAYBE_MODCHECK := $(if $(filter true,$(modcheck)),--modcheck)
gen_%: pyspec
	@mkdir -p $(TEST_VECTOR_DIR)
	@$(PYTHON_VENV) $(GENERATOR_DIR)/$*/main.py \
		--output $(TEST_VECTOR_DIR) \
		$(MAYBE_MODCHECK)

# Run all generators then check for errors.
gen_all: $(GENERATOR_TARGETS)
	@$(MAKE) detect_errors

# Detect errors in generators.
detect_errors: $(TEST_VECTOR_DIR)
	@incomplete_files=$$(find $(TEST_VECTOR_DIR) -name "INCOMPLETE"); \
	if [ -n "$$incomplete_files" ]; then \
		echo "[ERROR] incomplete detected"; \
		exit 1; \
	fi
	@if [ -f $(GENERATOR_ERROR_LOG_FILE) ]; then \
		echo "[ERROR] $(GENERATOR_ERROR_LOG_FILE) file exists"; \
		exit 1; \
	fi
	@echo "[PASSED] no errors detected"

# Generate KZG trusted setups for testing.
kzg_setups: pyspec
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
