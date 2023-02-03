// SPDX-License-Identifier: MIT
pragma solidity ^0.8.0;

contract MemoryArrayBuilding {

    struct Item {
        string name;
        string category;
        address owner;
        uint32 zipcode;
        uint32 price;
    }
    // Array of structs stored in storage
    Item[] public items;
    // Mapping address to uint
    mapping(address => uint) public ownerItemCount;
    // Get list of items by owner
    function getItemIDsByOwner(address _owner) public view returns (uint[] memory) {
        uint[] memory result = new uint[](ownerItemCount[_owner]);
        uint counter = 0;
        for (uint i = 0; i < items.length; i++) {
            if (items[i].owner == _owner) {
                result[counter] = i;
                counter++;
            }
        }
        return result;
    }
}
