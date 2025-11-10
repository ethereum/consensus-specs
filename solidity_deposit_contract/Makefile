SOLIDITY_FILE_NAME = deposit_contract.json
SOLIDITY_DEPOSIT_CONTRACT_SOURCE = deposit_contract.sol
DEPOSIT_CONTRACT_TESTER_DIR = web3_tester

export DAPP_SKIP_BUILD:=1
export DAPP_SRC:=$(CURDIR)
export DAPP_LIB:=$(CURDIR)/lib
export DAPP_JSON:=build/combined.json

all: \
	compile_deposit_contract \
	install_deposit_contract_web3_tester \
	test_deposit_contract_web3_tests

compile_deposit_contract:
	@git submodule update --recursive --init
	@solc --metadata-literal --optimize --optimize-runs 5000000 --bin --abi \
		--combined-json=abi,bin,bin-runtime,srcmap,srcmap-runtime,ast,metadata,storage-layout \
		--overwrite -o build $(SOLIDITY_DEPOSIT_CONTRACT_SOURCE) tests/deposit_contract.t.sol
	@/bin/echo -n '{"abi": ' > $(SOLIDITY_FILE_NAME)
	@cat build/DepositContract.abi >> $(SOLIDITY_FILE_NAME)
	@/bin/echo -n ', "bytecode": "0x' >> $(SOLIDITY_FILE_NAME)
	@cat build/DepositContract.bin >> $(SOLIDITY_FILE_NAME)
	@/bin/echo -n '"}' >> $(SOLIDITY_FILE_NAME)

test_deposit_contract:
	@dapp test -v --fuzz-runs 5

install_deposit_contract_web3_tester:
	@cd $(DEPOSIT_CONTRACT_TESTER_DIR); \
	python3 -m venv venv; \
	source venv/bin/activate; \
	python3 -m pip install -r requirements_preinstallation.txt; \
	python3 -m pip install -r requirements.txt

test_deposit_contract_web3_tests:
	@cd $(DEPOSIT_CONTRACT_TESTER_DIR); \
	source venv/bin/activate; \
	python3 -m pytest .

clean:
	@git clean -fdx
