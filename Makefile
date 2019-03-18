SPEC_DIR = ./specs
SCRIPT_DIR = ./scripts
BUILD_DIR = ./build
UTILS_DIR = ./utils


.PHONY: clean all test


all: $(BUILD_DIR)/phase0


clean:
	rm -rf $(BUILD_DIR)


test:
	pytest -m "sanity and minimal_config" tests/

$(BUILD_DIR)/phase0:
	mkdir -p $@
	python3 $(SCRIPT_DIR)/phase0/build_spec.py  $(SPEC_DIR)/core/0_beacon-chain.md $@/spec.py
	mkdir -p $@/utils
	cp $(UTILS_DIR)/phase0/* $@/utils
	cp $(UTILS_DIR)/phase0/state_transition.py $@
	touch $@/__init__.py $@/utils/__init__.py
