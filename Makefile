SPEC_DIR = ./specs
SCRIPT_DIR = ./scripts
BUILD_DIR = ./build

.PHONY: clean all


clean:
	rm -rf $(BUILD_DIR)


$(BUILD_DIR)/phase0:
	mkdir -p $@
	python3 $(SCRIPT_DIR)/phase0/build_spec.py  $(SPEC_DIR)/core/0_beacon-chain.md $(SCRIPT_DIR)/phase0/minimal_ssz.py \
		$(SCRIPT_DIR)/phase0/bls_stub.py $(SCRIPT_DIR)/phase0/state_transition.py $(SCRIPT_DIR)/phase0/monkey_patches.py > $@/spec.py
