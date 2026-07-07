// SPDX-License-Identifier: MIT
pragma solidity ^0.8.19;

/// @title TrustSphereAudit — immutable audit trail for forensic verdicts
/// @notice Each analyzed evidence file gets its SHA-256 hash + verdict anchored
///         on-chain so the analysis record can be proven untampered later.
contract TrustSphereAudit {
    struct Record {
        string verdict;     // "Authentic" | "Fake" | "Inconclusive"
        uint256 timestamp;  // analysis time (unix, supplied by backend)
        uint256 blockTime;  // block.timestamp when anchored
        address submitter;
        bool exists;
    }

    address public owner;
    mapping(bytes32 => Record) private records;

    event VerdictStored(
        bytes32 indexed fileHashId,
        string fileHash,
        string verdict,
        uint256 timestamp,
        address submitter
    );

    constructor() {
        owner = msg.sender;
    }

    function storeVerdict(
        string calldata fileHash,
        string calldata verdict,
        uint256 timestamp
    ) external {
        bytes32 id = keccak256(abi.encodePacked(fileHash));
        records[id] = Record(verdict, timestamp, block.timestamp, msg.sender, true);
        emit VerdictStored(id, fileHash, verdict, timestamp, msg.sender);
    }

    function getVerdict(string calldata fileHash)
        external
        view
        returns (
            string memory verdict,
            uint256 timestamp,
            uint256 blockTime,
            address submitter
        )
    {
        Record storage r = records[keccak256(abi.encodePacked(fileHash))];
        return (r.verdict, r.timestamp, r.blockTime, r.submitter);
    }
}
