// SPDX-License-Identifier: MIT
pragma solidity ^0.8.0;

contract Ownable {
    // Owner of the contract
    address private _owner;
    // Event to be emitted when ownership is transferred
    event OwnershipTransferred(
        address indexed previousOwner,
        address indexed newOwner
    );

    // Constructor to set the initial owner of the contract
    constructor() {
        _owner = msg.sender;
        emit OwnershipTransferred(address(0), _owner);
    }

    // Get the address of the owner
    function owner() public view returns (address) {
        return _owner;
    }

    // Modifier to check if the caller is the owner
    modifier onlyOwner() {
        require(_owner == msg.sender, "Ownable: caller is not the owner");
        _;
    }

    // Method to renounce ownership
    function renounceOwnership() public virtual onlyOwner {
        emit OwnershipTransferred(_owner, address(0));
        _owner = address(0);
    }

    // Method to transfer ownership
    function transferOwnership(address newOwner) public virtual onlyOwner {
        require(
            newOwner != address(0),
            "Ownable: new owner is the zero address"
        );
        emit OwnershipTransferred(_owner, newOwner);
        _owner = newOwner;
    }
}
