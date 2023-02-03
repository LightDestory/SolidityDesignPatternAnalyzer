// SPDX-License-Identifier: MIT
pragma solidity ^0.8.0;

// Import ownership pattern design
import "../Authorization/ownership_pattern.sol";

contract Register is Ownable {
    // Make use of the ownership pattern to restrict access to the upgrade function
    function updateContract(address newVersion)
        public
        onlyOwner
        returns (bool)
    {
        // If both conditions are verified, the new version is set as the current version
        if (newVersion != currentVersion) {
            previousVersions.push(currentVersion);
            currentVersion = newVersion;
            return true;
        }
        return false;
    }

    // Fallback function
    fallback() external {
        (bool success, ) = currentVersion.delegatecall(msg.data);
        require(success);
    }

    address public currentVersion;
    address[] previousVersions;
}
