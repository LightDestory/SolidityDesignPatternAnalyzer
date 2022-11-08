// SPDX-License-Identifier: MIT
pragma solidity ^0.8.0;

// Commit-reveal pattern
contract CommitReveal {
    // Commit structure
    struct Commit {string choice; string secret; string status;}
    // Commit mapping
    mapping(address => mapping(bytes32 => Commit)) public userCommits;
    event LogCommit(bytes32, address);
    event LogReveal(bytes32, address, string, string);
    // Commit function to initiate a commit
    function commit(bytes32 _commit) public returns (bool success) {
        Commit storage userCommit = userCommits[msg.sender][_commit];
        if (bytes(userCommit.status).length != 0) {
            return false; // commit has been used before
        }
        userCommit.status = "c"; // comitted
        emit LogCommit(_commit, msg.sender);
        return true;
    }
    function reveal(string calldata _choice, string calldata _secret, bytes32 _commit) public returns (bool success) {
        Commit storage userCommit = userCommits[msg.sender][_commit];
        bytes memory bytesStatus = bytes(userCommit.status);
        if (bytesStatus.length == 0) {
            return false; // choice not committed before
        } else if (bytesStatus[0] == "r") {
            return false; // choice already revealed
        }
        if (_commit != keccak256(abi.encodePacked(_choice, _secret))) {
            return false; // hash does not match commit
        }
        userCommit.choice = _choice;
        userCommit.secret = _secret;
        userCommit.status = "r"; // revealed
        emit LogReveal(_commit, msg.sender, _choice, _secret);
        return true;
    }
    function traceCommit(address _address, bytes32 _commit) public view
        returns (string memory choice, string memory secret, string memory status) {
        Commit storage userCommit = userCommits[_address][_commit];
        // Check if commit is revealed
        require(bytes(userCommit.status)[0] == "r");
        return (userCommit.choice, userCommit.secret, userCommit.status);
    }
}
