// SPDX-License-Identifier: MIT
pragma solidity ^0.8.0;

contract Deprecatable {
  // Initialize the contract with a deprecation date
  constructor(uint _lifetime) { 
    expires = block.timestamp + _lifetime;
  }
  // Check if the contract is still valid
  function expired() public view returns (bool) { 
    return block.timestamp > expires ? true : false;
  }
  // Modifier to perform when the contract is still valid
  modifier willDeprecate() { 
    if (!expired()) {_;}
  }
  // Modifier to perform when the contract is no longer valid
  modifier whenDeprecated() { 
    if (expired()) {_;}
  }
  uint expires;
}
