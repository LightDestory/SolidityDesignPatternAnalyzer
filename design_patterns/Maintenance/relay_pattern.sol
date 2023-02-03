// SPDX-License-Identifier: MIT
pragma solidity ^0.8.0;

// Import ownership pattern design
import "../Authorization/ownership_pattern.sol";

contract Relay is Ownable {
    // Initialize the relay with current version of the logic contract
    constructor(address initAddr) {
        currentVersion = initAddr;
    }

    // Make use of the ownership pattern to restrict access to the upgrade function
    function updateContract(address newVersion) public onlyOwner {
        // If the condition is verified, the new version is set as the current version
        currentVersion = newVersion;
    }

    // Fallback function
    fallback() external {
        (bool success, ) = currentVersion.delegatecall(msg.data);
        require(success);
    }

    address public currentVersion;
}
