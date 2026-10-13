// SPDX-License-Identifier: MIT
pragma solidity ^0.8.28;
import "./MockUSDC.sol";

/// @notice Fixed 1:1 exchange between six-decimal fake assets.
contract MockDex {
    MockUSDC public immutable usdc;
    MockUSDC public immutable weth;

    constructor(MockUSDC a, MockUSDC b) {
        require(block.chainid == 31337);
        usdc = a;
        weth = b;
    }

    function swap(address asset, uint256 amount, uint256 minimum, address recipient) external returns (uint256) {
        require(asset == address(usdc) || asset == address(weth), "asset");
        require(amount >= minimum, "slippage");
        MockUSDC input = MockUSDC(asset);
        MockUSDC output = asset == address(usdc) ? weth : usdc;
        require(input.transferFrom(msg.sender, address(this), amount));
        require(output.transfer(recipient, amount));
        return amount;
    }
}
