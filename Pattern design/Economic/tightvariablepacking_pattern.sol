// SPDX-License-Identifier: MIT
pragma solidity ^0.8.0;

contract StructPackingExample {
    // This struct will be packed into 32 bytes
    struct CheapStruct {
        uint8 a;
        uint8 b;
        uint8 c;
        uint8 d;
        bytes1 e;
        bytes1 f;
        bytes1 g;
        bytes1 h;
    }
    // Storage variable of the struct
    CheapStruct example;
    // Initializing and saving a struct
    function addCheapStruct() public {
        CheapStruct memory someStruct = CheapStruct(1,2,3,4,"a","b","c","d");
        example = someStruct;
    }
}
