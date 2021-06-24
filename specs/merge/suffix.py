ExecutionState = Any


def get_pow_block(hash: Bytes32) -> PowBlock:
    return PowBlock(block_hash=hash, is_valid=True, is_processed=True,
                    total_difficulty=uint256(0), difficulty=uint256(0))


def get_execution_state(execution_state_root: Bytes32) -> ExecutionState:
    pass


def get_pow_chain_head() -> PowBlock:
    pass


class NoopExecutionEngine(ExecutionEngine):
    def on_payload(self, execution_payload: ExecutionPayload) -> bool:
        return True

    def set_head(self, block_hash: Hash32) -> bool:
        return True

    def finalize_block(self, block_hash: Hash32) -> bool:
        return True

    def assemble_block(self, block_hash: Hash32, timestamp: uint64, random: Bytes32) -> ExecutionPayload:
        raise NotImplementedError("no default block production")


EXECUTION_ENGINE = NoopExecutionEngine()
