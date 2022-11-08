// SPDX-License-Identifier: MIT
pragma solidity ^0.8.0;

// Import ownership pattern
import "../Authorization/ownership_pattern.sol";

contract Mortal is Ownable {
  // Make use of the ownership modifier
  function destroy() public onlyOwner { 
    // If the owner calls this function, the funds are sent to the owner and the contract is destroyed
    selfdestruct(payable(owner())); 
  }
  function destroyWithoutModifier() public {
    // If the owner calls this function, the funds are sent to the owner and the contract is destroyed
     if (msg.sender == owner())
        selfdestruct(payable(owner())); 
  }
}



