pragma solidity ^0.6.0;

// This interface is designed to be compatible with the Vyper version.
interface IDepositContract {
    event DepositEvent(
        bytes pubkey,
        bytes withdrawal_credentials,
        bytes amount,
        bytes signature,
        bytes index
    );

    function deposit(
        bytes calldata pubkey,
        bytes calldata withdrawal_credentials,
        bytes calldata signature,
        bytes32 deposit_data_root
    ) external payable;
}

/*
 * This is a rewrite of the Vyper Eth2.0 deposit contract in Solidity.
 * It tries to stay as close as possible to the original source code and
 * hence it may look a bit unintuitive to a reader well versed in Solidity.
 */
contract DepositContract is IDepositContract {
    uint constant GWEI = 1e9;

    uint constant MIN_DEPOSIT_AMOUNT = 1000000000; // Gwei
    uint constant DEPOSIT_CONTRACT_TREE_DEPTH = 32;
    uint constant MAX_DEPOSIT_COUNT = 4294967295; // 2**DEPOSIT_CONTRACT_TREE_DEPTH - 1
    uint constant PUBKEY_LENGTH = 48; // bytes
    uint constant WITHDRAWAL_CREDENTIALS_LENGTH = 32; // bytes
    uint constant SIGNATURE_LENGTH = 96; // bytes
    uint constant AMOUNT_LENGTH = 8; // bytes

    bytes32[DEPOSIT_CONTRACT_TREE_DEPTH] branch;
    uint256 deposit_count;

    // TODO: add constructor

    // TODO: add get_deposit_root

    // TODO: add get_deposit_count

    function deposit(
        bytes calldata pubkey,
        bytes calldata withdrawal_credentials,
        bytes calldata signature,
        bytes32 deposit_data_root
    ) override external payable {
        // Avoid overflowing the Merkle tree (and prevent edge case in computing `self.branch`)
        require(deposit_count < MAX_DEPOSIT_COUNT);

        // Check deposit amount
        uint deposit_amount = msg.value / GWEI;
        require(deposit_amount >= MIN_DEPOSIT_AMOUNT);

        // Length checks for safety
        require(pubkey.length == PUBKEY_LENGTH);
        require(withdrawal_credentials.length == WITHDRAWAL_CREDENTIALS_LENGTH);
        require(signature.length == SIGNATURE_LENGTH);

        // FIXME: these are not the Vyper code, but should verify they are not needed
        // assert(deposit_amount <= 2^64-1);
        // assert(deposit_count <= 2^64-1);

        // Emit `DepositEvent` log
        bytes memory amount = to_little_endian_64(uint64(deposit_amount));
        emit DepositEvent(
            pubkey,
            withdrawal_credentials,
            amount,
            signature,
            to_little_endian_64(uint64(deposit_count))
        );

        // Compute deposit data root (`DepositData` hash tree root)
        // These are helpers and are implicitly initialised to zero.
        bytes16 zero_bytes16;
        bytes24 zero_bytes24;
        bytes32 zero_bytes32;
        bytes32 pubkey_root = sha256(abi.encodePacked(pubkey, zero_bytes16));
        bytes32 signature_root = sha256(abi.encodePacked(
            sha256(abi.encodePacked(bytes(signature[:64]))),
            sha256(abi.encodePacked(bytes(signature[64:]), zero_bytes32))
        ));
        bytes32 node = sha256(abi.encodePacked(
            sha256(abi.encodePacked(pubkey_root, withdrawal_credentials)),
            sha256(abi.encodePacked(amount, zero_bytes24, signature_root))
        ));
        // Verify computed and expected deposit data roots match
        require(node == deposit_data_root);

        // Add deposit data root to Merkle tree (update a single `branch` node)
        deposit_count += 1;
        uint size = deposit_count;
        for (uint height = 0; height < DEPOSIT_CONTRACT_TREE_DEPTH; height++) {
            if ((size & 1) == 1) {
                branch[height] = node;
                break;
            }
            node = sha256(abi.encodePacked(branch[height], node));
            size /= 2;
        }
    }

    function to_little_endian_64(uint64 value) internal pure returns (bytes memory ret) {
        // Unrolled the loop here.
        ret = new bytes(8);
        ret[0] = bytes1(uint8(value & 0xff));
        ret[1] = bytes1(uint8((value >> 8) & 0xff));
        ret[2] = bytes1(uint8((value >> 16) & 0xff));
        ret[3] = bytes1(uint8((value >> 24) & 0xff));
        ret[4] = bytes1(uint8((value >> 32) & 0xff));
        ret[5] = bytes1(uint8((value >> 40) & 0xff));
        ret[6] = bytes1(uint8((value >> 48) & 0xff));
        ret[7] = bytes1(uint8((value >> 56) & 0xff));
    }
}
