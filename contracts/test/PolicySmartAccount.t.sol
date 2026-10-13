// SPDX-License-Identifier: MIT
pragma solidity ^0.8.28;
import "../src/PolicySmartAccount.sol";

interface Vm {
    function prank(address) external;
    function expectRevert(bytes4) external;
}

contract PolicySmartAccountTest {
    Vm constant vm = Vm(address(uint160(uint256(keccak256("hevm cheat code")))));
    MockUSDC a;
    MockUSDC b;
    MockDex dex;
    PolicySmartAccount account;
    address agent = address(2);
    address recipient = address(3);

    function setUp() public {
        a = new MockUSDC("USDC");
        b = new MockUSDC("WETH");
        dex = new MockDex(a, b);
        account = new PolicySmartAccount(address(this), agent, a, b, 100e6);
        account.setTarget(address(dex), true);
        account.setTarget(recipient, true);
        a.mint(address(account), 1000e6);
        b.mint(address(dex), 1000e6);
    }

    function testPermittedSwap() public {
        vm.prank(agent);
        account.swap(bytes32(uint256(1)), address(dex), address(a), 30e6, 30e6);
        require(b.balanceOf(address(account)) == 30e6);
        require(a.allowance(address(account), address(dex)) == 0);
    }

    function testBypassDailyLimit() public {
        vm.prank(agent);
        account.transfer(bytes32(uint256(1)), recipient, 30e6);
        vm.expectRevert(PolicySmartAccount.LimitExceeded.selector);
        vm.prank(agent);
        account.transfer(bytes32(uint256(2)), recipient, 80e6);
    }

    function testAgentCannotChangeLimit() public {
        vm.expectRevert(PolicySmartAccount.Unauthorized.selector);
        vm.prank(agent);
        account.setDailyLimit(999e6);
    }

    function testAgentCannotWhitelist() public {
        vm.expectRevert(PolicySmartAccount.Unauthorized.selector);
        vm.prank(agent);
        account.setTarget(address(8), true);
    }

    function testPaused() public {
        account.setPaused(true);
        vm.expectRevert(PolicySmartAccount.Paused.selector);
        vm.prank(agent);
        account.transfer(bytes32(uint256(1)), recipient, 1);
    }

    function testRevoked() public {
        account.setAgent(address(0));
        vm.expectRevert(PolicySmartAccount.Unauthorized.selector);
        vm.prank(agent);
        account.transfer(bytes32(uint256(1)), recipient, 1);
    }

    function testUnknownTarget() public {
        vm.expectRevert(PolicySmartAccount.Forbidden.selector);
        vm.prank(agent);
        account.transfer(bytes32(uint256(1)), address(8), 1);
    }

    function testReplay() public {
        vm.prank(agent);
        account.transfer(bytes32(uint256(1)), recipient, 1);
        vm.expectRevert(PolicySmartAccount.Replay.selector);
        vm.prank(agent);
        account.transfer(bytes32(uint256(1)), recipient, 1);
    }

    function testAgentCannotChangeAgent() public {
        vm.expectRevert(PolicySmartAccount.Unauthorized.selector);
        vm.prank(agent);
        account.setAgent(recipient);
    }

    function testAgentCannotUnpause() public {
        account.setPaused(true);
        vm.expectRevert(PolicySmartAccount.Unauthorized.selector);
        vm.prank(agent);
        account.setPaused(false);
    }

    function testExcessiveSlippage() public {
        vm.expectRevert(PolicySmartAccount.Forbidden.selector);
        vm.prank(agent);
        account.swap(bytes32(uint256(1)), address(dex), address(a), 30e6, 20e6);
    }

    function testUnauthorizedAsset() public {
        vm.expectRevert(PolicySmartAccount.Forbidden.selector);
        vm.prank(agent);
        account.swap(bytes32(uint256(1)), address(dex), address(99), 30e6, 30e6);
    }

    function testExactDailyLimit() public {
        vm.prank(agent);
        account.transfer(bytes32(uint256(1)), recipient, 100e6);
        require(a.balanceOf(recipient) == 100e6);
    }

    function testFuzzOverLimit(uint96 amount) public {
        if (amount <= 100e6) return;
        vm.expectRevert(PolicySmartAccount.LimitExceeded.selector);
        vm.prank(agent);
        account.transfer(bytes32(uint256(1)), recipient, amount);
    }
}
