all: compile

clean:
	@rm -rf build
	@rm -f deposit_contract.json

# Note: using /bin/echo for macOS support
compile: clean
	@git submodule update --recursive --init
	@solc --metadata-literal --optimize --optimize-runs 5000000 --bin --abi --combined-json=abi,bin,bin-runtime,srcmap,srcmap-runtime,ast,metadata,storage-layout --overwrite -o build deposit_contract.sol tests/deposit_contract.t.sol
	@/bin/echo -n '{"abi": ' > deposit_contract.json
	@cat build/DepositContract.abi >> deposit_contract.json
	@/bin/echo -n ', "bytecode": "0x' >> deposit_contract.json
	@cat build/DepositContract.bin >> deposit_contract.json
	@/bin/echo -n '"}' >> deposit_contract.json

export DAPP_SKIP_BUILD:=1
export DAPP_SRC:=.
export DAPP_JSON:=build/combined.json

test:
	dapp test -v --fuzz-runs 5
