// SPDX-License-Identifier: MIT
pragma solidity ^0.8.0;

// Import ownership pattern design
import "../Authorization/ownership_pattern.sol";

contract EmergencyStop is Ownable {
    // define the state variable
    bool private contractStopped = false;
    // Modifier to halt operations in case of emergency
    modifier haltInEmergency() {
        if (!contractStopped) _;
    }
    // Modifier for emergency enabled operations
    modifier enableInEmergency() {
        if (contractStopped) _;
    }

    // Toggles the emergency state
    function toggleContractStopped() public onlyOwner {
        contractStopped = !contractStopped;
    }

    // Example function to demonstrate the emergency stop pattern
    function deposit() public payable haltInEmergency {
        // some code
    }

    // Example function to demonstrate the emergency stop pattern
    function withdraw() public view enableInEmergency {
        // some code
    }
}
