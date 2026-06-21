# Testnet Faucet Design Document

> [!Warning]
> This page have been revised, older versions that had received approval:
>
> 1. [11ff0c4](https://github.com/AztecProtocol/engineering-designs/commit/11ff0c45015027554f13d37f2df85e84090a55a4)

- Owner: @just-mitch
- Approvers:
  - @aminsammara
  - @rahul-kothari
  - @LHerskind
  - @PhilWindle
  - @signorecello
- [PRD](https://github.com/AztecProtocol/engineering-designs/blob/11ff0c45015027554f13d37f2df85e84090a55a4/docs/faucets/prd.md)
- Target DD Approval Date: 2025-03-20
- Target Project Delivery Date: 2025-03-28

## Executive Summary

Update the fee asset and staking asset to have "minter" roles.

Deploy new "handler" contracts that have the minter role on their respective assets.

The FeeAssetHandler will mint a fixed amount to any caller.

The StakingAssetHandler will add an address to the validator set, given sufficient capacity of when called by an owner.

## Timeline

Outline the timeline for the project. E.g.

- Core contract dev : 1-2 days
  - build fee asset handler
  - build staking asset handler
  - tests
- run upgrade : <0.5 days

Total: 3 days

## Introduction

We are not concerned about the DOS risk of someone holding a large amount of fee asset and flooding the network with transactions: the node and p2p layer should be able to handle this; controlling the production of fee asset needs only to prevent infinite minting (and thus a DOS against the users of the network).

Said differently, if users are able to obtain _any_ amount of fee asset, the node and p2p layer must already be able to handle the following attacks:

- User accrues a large amount of fee asset, then creates a large number of valid transations.
- User creates a large number of transactions, which individually are valid, but invalidate each other.

Considering the node must be able to handle these attacks, we choose to be loose about the rate at which users can mint fee asset.

Beyond all of that, there is already an inherent sybil resistance to someone flooding the network: each transaction requires a valid client-side proof, which requires non-trivial computational resources.

We _are_ concerned about the DOS risk of someone adding a large number of bad validators to the set; we want to limit the rate at which validators can be added to the set, but make no effort to ensure they have access to an active aztec node.

## Interface

### End users and app developers

For users who want fee asset, they will be able to just:

```bash
cast call $FEE_ASSET_HANDLER "mint(address)" $MY_ADDRESS
```

This will drip an amount of fee asset to their address.

They can then use the `bridge-erc20` utility on the aztec CLI

### Validators

For users who want to be a validator, they can use the aztec CLI to add a validator (with forwarder).

```
aztec-cli add-l1-validator
```

## Implementation

### TestERC20

Both the fee and staking assets will be instances of `TestERC20`.

We'll remove the `ownerOrFreeForAll` modifier from the `mint` function, and instead add a `minters` mapping.

```solidity
contract TestERC20 is ERC20, IMintableERC20, Ownable {

  mapping(address => bool) public minters;

  modifier onlyMinter() {
    require(minters[msg.sender] || msg.sender == owner(), "Not authorized to mint");
    _;
  }

	constructor(string memory _name, string memory _symbol, address _owner)
    ERC20(_name, _symbol)
    Ownable(_owner)
  {
    minters[_owner] = true;
  }

  function addMinter(address _minter) external onlyMinter {
    require(_minter != address(0), "Invalid address");
    minters[_minter] = true;
  }

	function removeMinter(address _minter) external onlyMinter {
    require(_minter != owner(), "Cannot remove owner as minter");
    minters[_minter] = false;
  }

  function mint(address _recipient, uint256 _amount) external onlyMinter {
    _mint(_recipient, _amount);
  }
}
```

### Fee Asset

When the fee asset is deployed, the owner will be an EOA, held by Aztec Labs.

### Fee Asset Handler

For the fee asset, we will create a new contract `FeeAssetHandler`

```solidity
interface IFeeAssetHandler {
	function mint(address _recipient) external;
	function setMintAmount(uint256 _amount) external;
}

contract FeeAssetHandler is IFeeAssetHandler, Ownable {
	IMintableERC20 public immutable FEE_ASSET;
	uint256 public mintAmount;

	constructor(address _owner, address _feeAsset, uint256 _mintAmount) Ownable(_owner) {
		FEE_ASSET = IMintableERC20(_feeAsset);
		mintAmount = _mintAmount;
	}

	function mint(address _recipient) external override {
		FEE_ASSET.mint(_recipient, mintAmount);
	}

	function setMintAmount(uint256 _amount) external override onlyOwner {
    mintAmount = _amount;
	}
}
```

We will manually deploy this contract. The owner will be the same as the current owner of the FeeAsset.

The handler's deployed address will need to be made known in discord and other public channels/docs.

#### Choosing the mint amount

As mentioned above, we only need to prevent infinite minting (i.e. over 2^256).

We can calculate the maximum mint amount based on the expected L1 block production rate, the expected L1 gas cost of a mint, and the amount of time we expect the handler to be live.

Assume the cost to mint is 5K gas.

Then if a block were completely full of `mint` transactions, the maximum number of mints would be 38M / 5K = 7600.

This means that we could be maximally minting 7600 / 12 = 633 times per second.

Separately, the current amount of mana required for a public transfer is around 1e5 mana.

If we suppose that the base fee is 100 fee asset per mana, then a public transfer will cost 1e7 fee asset.

Suppose that a contract deployment costs 100x as much as a public transfer, so 1e9 fee asset.

And suppose we want to allow a user to perform 1000 contract deployments with a single mint.

Then they will need 1e12 fee asset in a single mint.

If we mint at 633 mints per second, then the max possible rate of increase of fee asset is 1e12 \* 633 ~= 6e14 fee asset per second.

So in order to hit an overflow, we would need 2^256 / 6e14 ~= 2e62 seconds, or about 6e54 years.

We'll keep an eye on the base fee in the network and bump the mint amount if we were too conservative.

#### Alternative Design

The primary alternative would be to make a frontend UI that connects to a backend that has the account that is the owner of the token, then maintain a map on the backend to rate-limit different IP addresses, or have users sign up, etc.

The benefit is that if we went with the signup route, we could advertise to those users.

The downside is that that is significantly more infrastructure, and it doesn't necessarily improve the safety/control of the system.

### Staking Asset

The staking asset will be deployed with the same owner as the fee asset. In addition, a `StakingAssetHandler` will be deployed, which will have the minter role on the staking asset.

### Staking Asset Handler

```solidity
interface IStakingAssetHandler {
	function addValidator(address _attester, address _proposer) external;
	function setDepositsPerMint(uint256 _maxDepositsPerMint) external;
	function setWithdrawer(address _withdrawer) external;
}

contract StakingAssetHandler is IStakingAssetHandler, Ownable {
	IMintableERC20 public immutable STAKING_ASSET;

	mapping(address => bool) public canAddValidator;

	uint256 public depositAmount;
	uint256 public lastMintTimestamp;
	uint256 public minMintInterval;
	uint256 public maxDepositsPerMint;
	IStakingCore public rollup;
	address public withdrawer;

	modifier onlyCanAddValidator() {
		require(canAddValidator[msg.sender], "Not authorized to add validator");
		_;
	}

	constructor(
		address _owner,
		address _stakingAsset,
		address _rollup,
		address _withdrawer,
		uint256 _depositAmount,
		uint256 _minMintInterval,
		uint256 _maxDepositsPerMint,
		address[] _canAddValidator
	) Ownable(_owner) {
		STAKING_ASSET = IMintableERC20(_stakingAsset);
		depositAmount = _depositAmount;
		rollup = IStakingCore(_rollup);
		withdrawer = _withdrawer;
		minMintInterval = _minMintInterval;
		maxDepositsPerMint = _maxDepositsPerMint;
		for (uint256 i = 0; i < _canAddValidator.length; i++) {
			canAddValidator[_canAddValidator[i]] = true;
		}
		canAddValidator[owner()] = true;
	}

	function addValidator(address _attester, address _proposer) external override onlyCanAddValidator {
		bool needsMint = STAKING_ASSET.balanceOf(address(this)) < depositAmount;
		bool canMint = block.timestamp - lastMintTimestamp >= minMintInterval;
		require(!needsMint || canMint, "Minter is in cooldown");

		if (needsMint) {
			lastMintTimestamp = block.timestamp;
			STAKING_ASSET.mint(address(this), depositAmount * maxDepositsPerMint);
		}

		STAKING_ASSET.approve(address(rollup), depositAmount);
		rollup.deposit(_attester, _proposer, withdrawer, depositAmount);
	}

	function setMinMintInterval(uint256 _interval) external override onlyOwner {
		minMintInterval = _interval;
	}

	function setMaxDepositsPerMint(uint256 _maxDepositsPerMint) external override onlyOwner {
		maxDepositsPerMint = _maxDepositsPerMint;
	}

	function setWithdrawer(address _withdrawer) external override onlyOwner {
		withdrawer = _withdrawer;
	}
}
```

The owner of the handler will be the same as the owner of the staking asset.
A separate EOA will be created for the bot, which will have the `canAddValidator` role.

#### Upgrades

The handler will jump to the new rollup address when a new rollup is made canonical and added to the registry.

#### Risks

This doesn't ensure that the user's node is properly gossiping.
So we only limit the number of validators that can be added to the network, not maximizing the number of nodes that are actually running.

#### Alternative design

An alternative design is available in [11ff0c4](https://github.com/AztecProtocol/engineering-designs/commit/11ff0c45015027554f13d37f2df85e84090a55a4).

### Sequencer Client

The sequencer must be updated in its block building logic to ensure that it does not exceed the mana limit for a block as specified on L1.

This is out of scope for this design.

### P2P

The mempools will need to be updated to not be unbounded in size.

This is out of scope for this design.

### Rollup

The `ITestRollup` interface must be updated to include a new function `setManaTarget`.

This function will be callable by the owner of the rollup, and will update the mana target for the rollup.

### New deployment

The fee/staking assets are already deployed on Sepolia.

We will need to do a new deployment of the L1 contracts as part of our next upgrade (i.e. a new registry contract).

## Requirement Fulfillment

- [x] FUNC-01: single cast command
- [x] FUNC-02: part of the `FeeAssetHandler` interface
- [x] FUNC-03: part of the sequencer client changes
- [x] FUNC-04: part of the `ITestRollup` interface
- [x] FUNC-05: part of discord and staking asset changes
- [x] FUNC-06: Labs will have an EOA that is `minter` on the staking asset.
- [x] FUNC-07: part of the `StakingAssetHandler` interface
- [x] QUAL-01: anyone can mint fee asset through the `FeeAssetHandler`
- [/] QUAL-02: we can easily remove anyone added through the `StakingAssetHandler`; all bets are off for validators added otherwise.
- [x] QUAL-03: requiring a synced node and validator role/counts in discord should provide a reasonable level of sybil resistance
- [x] PERF-01: should be under 24 seconds
- [x] PERF-02: running the commands should take under 5 minutes. interacting with the bot should be under 24 seconds.

## Change Set

Fill in bullets for each area that will be affected by this change.

- [ ] Cryptography
- [ ] Noir
- [ ] Aztec.js
- [ ] PXE
- [ ] Aztec.nr
- [ ] Enshrined L2 Contracts
- [ ] Sequencer
- [ ] AVM
- [ ] Public Kernel Circuits
- [ ] Rollup Circuits
- [x] L1 Contracts
  - Only the periphery
- [ ] Prover
- [ ] Economics
- [ ] P2P Network
- [ ] DevOps

## Test Plan

- Forge tests with 100% coverage on the `FeeAssetHandler`
- Forge tests with 100% coverage on the `StakingAssetHandler`
- e2e test that the `bridge-erc20` utility works
- Manual testing of adding a validator using the new flow on discord
- Verify that a validator added via discord may be removed as expected
- Verify that adding a validator grants a "validator" role in discord
- Verify that the discord bot enforces a configurable limit of validators per user

## Documentation Plan

Discord will need to be updated to tell users how to mint/bridge fee asset.

Discord will also need to be updated to provide documentation on how to use the `/add-validator` command

## Disclaimer

The information set out herein is for discussion purposes only and does not represent any binding indication or commitment by Aztec Labs and its employees to take any action whatsoever, including relating to the structure and/or any potential operation of the Aztec protocol or the protocol roadmap. In particular: (i) nothing in these projects, requests, or comments is intended to create any contractual or other form of legal relationship with Aztec Labs or third parties who engage with this AztecProtocol GitHub account (including, without limitation, by responding to a conversation or submitting comments) (ii) by engaging with any conversation or request, the relevant persons are consenting to Aztec Labs’ use and publication of such engagement and related information on an open-source basis (and agree that Aztec Labs will not treat such engagement and related information as confidential), and (iii) Aztec Labs is not under any duty to consider any or all engagements, and that consideration of such engagements and any decision to award grants or other rewards for any such engagement is entirely at Aztec Labs’ sole discretion. Please do not rely on any information on this account for any purpose - the development, release, and timing of any products, features, or functionality remains subject to change and is currently entirely hypothetical. Nothing on this account should be treated as an offer to sell any security or any other asset by Aztec Labs or its affiliates, and you should not rely on any content or comments for advice of any kind, including legal, investment, financial, tax, or other professional advice.
