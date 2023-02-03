// SPDX-License-Identifier: MIT
pragma solidity ^0.8.0;

// Mutex pattern
contract Mutex {
    // Mutex state
    bool locked = false;
    
    modifier noReentrancy() {
        require(!locked);
        locked = true;
        _;
        locked = false;
    }
}
