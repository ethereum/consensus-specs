all: compile

clean:
	@rm -f DepositContract.abi DepositContract.bin IDepositContract.abi IDepositContract.bin deposit_contract.json

compile: clean
	@solc --metadata-literal --bin --abi --overwrite -o . deposit_contract.sol
	@echo -n '{"abi": ' > deposit_contract.json
	@cat DepositContract.abi >> deposit_contract.json
	@echo -n ', "bytecode": "0x' >> deposit_contract.json
	@cat DepositContract.bin >> deposit_contract.json
	@echo -n '"}' >> deposit_contract.json
