// SPDX-License-Identifier: MIT
pragma solidity ^0.8.0;

// Import ownership pattern design
import "../Authorization/ownership_pattern.sol";

// A simple contract to demonstrate the satellite pattern
contract sumSatellite {
    function sum(uint256 a, uint256 b) public pure returns (uint256) {
        return a + b;
    }
}

// Core contract
contract Core is Ownable {
    // Make use of the ownership pattern to restrict access to the upgrade function
    function updateSatellite(address newVersion) public onlyOwner {
        // If the condition is verified, the new version is set as the current version
        sumSatelliteAddr = newVersion;
        sumModule = sumSatellite(sumSatelliteAddr);
    }

    // Make use of the satellite
    function sum(uint256 a, uint256 b) public view returns (uint256) {
        return sumModule.sum(a, b);
    }

    address sumSatelliteAddr;
    sumSatellite sumModule;
}
