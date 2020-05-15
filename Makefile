all: compile

clean:
	@rm -f DepositContract.abi DepositContract.bin IDepositContract.abi IDepositContract.bin deposit_contract.json
	@rm -f DepositContractTest.abi DepositContractTest.bin
	@rm -f VyperSetup.abi VyperSetup.bin
	@rm -f DSTest.abi DSTest.bin
	@rm -rf combined.json

compile: clean
	@# Note: using /bin/echo for macOS
	@git submodule update --recursive --init
	@solc --metadata-literal --optimize --optimize-runs 5000000 --bin --abi --combined-json=abi,bin,bin-runtime,srcmap,srcmap-runtime,ast,metadata,storage-layout --overwrite -o . deposit_contract.sol tests/deposit_contract.t.sol
	@/bin/echo -n '{"abi": ' > deposit_contract.json
	@cat DepositContract.abi >> deposit_contract.json
	@/bin/echo -n ', "bytecode": "0x' >> deposit_contract.json
	@cat DepositContract.bin >> deposit_contract.json
	@/bin/echo -n '"}' >> deposit_contract.json


export DAPP_SKIP_BUILD:=1
export DAPP_SRC:=.
export DAPP_JSON:=combined.json

test:
	dapp test -v --fuzz-runs 5
