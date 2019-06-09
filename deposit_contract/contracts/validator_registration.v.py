MIN_DEPOSIT_AMOUNT: constant(uint256) = 1000000000  # Gwei
DEPOSIT_CONTRACT_TREE_DEPTH: constant(uint256) = 32
PUBKEY_LENGTH: constant(uint256) = 48  # bytes
WITHDRAWAL_CREDENTIALS_LENGTH: constant(uint256) = 32  # bytes
AMOUNT_LENGTH: constant(uint256) = 8  # bytes
SIGNATURE_LENGTH: constant(uint256) = 96  # bytes

Deposit: event({
    pubkey: bytes[48],
    withdrawal_credentials: bytes[32],
    amount: bytes[8],
    signature: bytes[96],
})

branch: bytes32[DEPOSIT_CONTRACT_TREE_DEPTH]
deposit_count: uint256

# Compute hashes in empty sparse Merkle tree
zero_hashes: bytes32[DEPOSIT_CONTRACT_TREE_DEPTH]
@public
def __init__():
    for i in range(DEPOSIT_CONTRACT_TREE_DEPTH - 1):
        self.zero_hashes[i + 1] = sha256(concat(self.zero_hashes[i], self.zero_hashes[i]))


@public
@constant
def to_little_endian_64(value: uint256) -> bytes[8]:
    # Reversing bytes using bitwise uint256 manipulations
    # (array accesses of bytes[] are not currently supported in Vyper)
    y: uint256 = 0
    x: uint256 = value
    for _ in range(8):
        y = shift(y, 8)
        y = y + bitwise_and(x, 255)
        x = shift(x, -8)
    return slice(convert(y, bytes32), start=24, len=8)


@public
@constant
def get_deposit_root() -> bytes32:
    node: bytes32 = 0x0000000000000000000000000000000000000000000000000000000000000000
    size: uint256 = self.deposit_count
    for height in range(DEPOSIT_CONTRACT_TREE_DEPTH):
        if bitwise_and(size, 1) == 1:  # More gas efficient than `size % 2 == 1`
            node = sha256(concat(self.branch[height], node))
        else:
            node = sha256(concat(node, self.zero_hashes[height]))
        size /= 2
    return node


@public
@constant
def get_deposit_count() -> bytes[8]:
    return self.to_little_endian_64(self.deposit_count)


@payable
@public
def deposit(pubkey: bytes[PUBKEY_LENGTH],
            withdrawal_credentials: bytes[WITHDRAWAL_CREDENTIALS_LENGTH],
            signature: bytes[SIGNATURE_LENGTH]):
    # Avoid overflowing the Merkle tree
    assert self.deposit_count < 2**DEPOSIT_CONTRACT_TREE_DEPTH - 1

    # Validate deposit data
    deposit_amount: uint256 = msg.value / as_wei_value(1, "gwei")
    assert deposit_amount >= MIN_DEPOSIT_AMOUNT
    assert len(pubkey) == PUBKEY_LENGTH
    assert len(withdrawal_credentials) == WITHDRAWAL_CREDENTIALS_LENGTH
    assert len(signature) == SIGNATURE_LENGTH

    # Compute `DepositData` root
    amount: bytes[8] = self.to_little_endian_64(deposit_amount)
    zero_bytes32: bytes32
    pubkey_root: bytes32 = sha256(concat(pubkey, slice(zero_bytes32, start=0, len=64 - PUBKEY_LENGTH)))
    signature_root: bytes32 = sha256(concat(
        sha256(slice(signature, start=0, len=64)),
        sha256(concat(slice(signature, start=64, len=SIGNATURE_LENGTH - 64), zero_bytes32)),
    ))
    node: bytes32 = sha256(concat(
        sha256(concat(pubkey_root, withdrawal_credentials)),
        sha256(concat(amount, slice(zero_bytes32, start=0, len=32 - AMOUNT_LENGTH), signature_root)),
    ))

    # Add `DepositData` root to Merkle tree (update a single `branch` node)
    self.deposit_count += 1
    size: uint256 = self.deposit_count
    for height in range(DEPOSIT_CONTRACT_TREE_DEPTH):
        if bitwise_and(size, 1) == 1:  # More gas efficient than `size % 2 == 1`
            self.branch[height] = node
            break
        node = sha256(concat(self.branch[height], node))
        size /= 2

    # Emit `Deposit` log
    log.Deposit(pubkey, withdrawal_credentials, amount, signature)
