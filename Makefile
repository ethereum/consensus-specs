SPEC_DIR = ./specs
SCRIPT_DIR = ./scripts
BUILD_DIR = ./build

.PHONY: clean all


$(BUILD_DIR)/phase0:
	mkdir -p $@
	python3 $(SCRIPT_DIR)/phase0/build_spec.py  $(SPEC_DIR)/core/0_beacon-chain.md $@/spec.py
	touch $(BUILD_DIR)/__init__.py $(BUILD_DIR)/phase0/__init__.py
