// SPDX-License-Identifier: MIT
pragma solidity ^0.8.0;

contract Storage {
    // mapping to store the data with autogetter
    mapping(bytes32 => uint256) public uintStorage;
    mapping(bytes32 => address) public addressStorage;

    // ... // other mappings for other types
    function setUintStorage(bytes32 key, uint256 value) public {
        uintStorage[key] = value;
    }

    function setaddressStorage(bytes32 key, address value) public {
        addressStorage[key] = value;
    }
}

contract Logic {
    Storage _storage;

    // Initialize the contract with the address of the storage contract
    constructor(address storageAddress) {
        _storage = Storage(storageAddress);
    }

    // Testing
    function test() public returns (uint256) {
        bytes32 key = keccak256("capybara");
        _storage.setUintStorage(key, 911);
        return _storage.uintStorage(key);
    }
}

contract Proxy is Logic {
    // The proxy contract initializes the logic contract with the address of the storage contract
    constructor(address storageAddress) Logic(storageAddress) {}
}
