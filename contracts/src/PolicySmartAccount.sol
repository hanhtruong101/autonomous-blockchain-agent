// SPDX-License-Identifier: MIT
pragma solidity ^0.8.28;
import "./MockDex.sol";

/// @notice Educational defense in depth: restricted operations, daily budget and replay protection.
contract PolicySmartAccount {
    error Unauthorized();
    error Paused();
    error LimitExceeded();
    error Forbidden();
    error Replay();
    address public immutable owner;
    address public agent;
    MockUSDC public immutable usdc;
    MockUSDC public immutable weth;
    uint256 public dailyLimit;
    bool public paused;
    mapping(address => bool) public allowedTargets;
    mapping(uint256 => uint256) public spent;
    mapping(bytes32 => bool) public executed;
    event Executed(bytes32 indexed id, address indexed target, address asset, uint256 amount);
    event AgentChanged(address indexed agent);
    event PauseChanged(bool paused);
    event LimitChanged(uint256 limit);
    event TargetChanged(address indexed target, bool allowed);
    modifier onlyOwner() {
        if (msg.sender != owner) revert Unauthorized();
        _;
    }

    constructor(address owner_, address agent_, MockUSDC a, MockUSDC b, uint256 limit) {
        require(block.chainid == 31337 && owner_ != address(0));
        owner = owner_;
        agent = agent_;
        usdc = a;
        weth = b;
        dailyLimit = limit;
    }

    function setAgent(address value) external onlyOwner {
        agent = value;
        emit AgentChanged(value);
    }

    function setPaused(bool value) external onlyOwner {
        paused = value;
        emit PauseChanged(value);
    }

    function setDailyLimit(uint256 value) external onlyOwner {
        dailyLimit = value;
        emit LimitChanged(value);
    }

    function setTarget(address target, bool value) external onlyOwner {
        allowedTargets[target] = value;
        emit TargetChanged(target, value);
    }

    function _consume(bytes32 id, address target, uint256 amount) internal {
        if (msg.sender != agent || agent == address(0)) revert Unauthorized();
        if (paused) revert Paused();
        if (!allowedTargets[target] || amount == 0) revert Forbidden();
        if (executed[id]) revert Replay();
        uint256 day = block.timestamp / 1 days;
        if (amount > dailyLimit || spent[day] > dailyLimit - amount) revert LimitExceeded();
        spent[day] += amount;
        executed[id] = true;
    }

    function swap(bytes32 id, address dex, address asset, uint256 amount, uint256 minimum) external {
        if (asset != address(usdc) && asset != address(weth)) revert Forbidden();
        if (minimum < (amount * 9900 + 9999) / 10000) revert Forbidden();
        _consume(id, dex, amount);
        MockUSDC token = MockUSDC(asset);
        uint256 beforeBalance = (asset == address(usdc) ? weth : usdc).balanceOf(address(this));
        require(token.approve(dex, amount));
        MockDex(dex).swap(asset, amount, minimum, address(this));
        require(token.approve(dex, 0));
        require((asset == address(usdc) ? weth : usdc).balanceOf(address(this)) >= beforeBalance + minimum);
        emit Executed(id, dex, asset, amount);
    }

    function transfer(bytes32 id, address recipient, uint256 amount) external {
        _consume(id, recipient, amount);
        require(usdc.transfer(recipient, amount));
        emit Executed(id, recipient, address(usdc), amount);
    }
    receive() external payable {}
}
