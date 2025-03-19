# Testnet Faucet Design Document

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

The StakingAssetHandler will add an address to the validator set, when called by the owner.

The discord bot should be augmented to allow someone to pass it a merkle proof of the archive tree, and only then be added to the validator set.

## Timeline

Outline the timeline for the project. E.g.

- Core contract dev : 1-2 days
  - build fee asset handler
  - build staking asset handler
  - tests
- discord bot dev : 1-2 days
- run upgrade : <0.5 days

Total: 3-5 days

## Introduction

We are not concerned about the DOS risk of someone holding a large amount of fee asset and flooding the network with transactions: the node and p2p layer should be able to handle this; controlling the production of fee asset needs only to prevent infinite minting (and thus a DOS against the users of the network).

We _are_ concerned about the DOS risk of someone adding a large number of bad validators to the set; we want to limit the rate at which validators can be added to the set, and make some reasonable effort to ensure they have access to an active aztec node.

## Interface

### End users and app developers

For users who want fee asset, they will be able to just:

```bash
cast call $FEE_ASSET_HANDLER "mint(address)" $MY_ADDRESS
```

This will drip an amount of fee asset to their address.

They can then use the `bridge-erc20` utility on the aztec CLI

### Validators

For users who want to be a validator, they will first:

```
curl -s -X POST -H 'Content-Type: application/json' -d \
'{"jsonrpc":"2.0","method":"node_getL2Tips","params":[],"id":67}' \
"http://localhost:8080" | jq \
".result.proven.number"
```

That will give something like `21314`

Then they can get a membership path

```
curl -s -X POST -H 'Content-Type: application/json' -d \
'{"jsonrpc":"2.0","method":"node_getArchiveSiblingPath","params":[21314, 21314],"id":67}' \
"http://localhost:8080" | jq ".result"
```

Which will return a big encoded string.

Then, over in discord, they can:

```bash
/add-validator <their address> <block number> <membership path>
```

And this will result in their address getting added to the set.

**Note:** Using the proven chain allows us to add validators even if the pending chain is stalled.

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

Suppose that we expect the handler to be live for a maximum of 5 years.

Then we have a maximum of 5 \* 365 \* 24 \* 60 \* 60 \* 633 ~= 1e11 mints.

Thus, the maximum mint amount is (2^256 - 1) / 1e11 ~= 1e66.

But we'll err on the side of caution and use 1e42.

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
	function setRollup(address _rollup) external;
	function setDepositAmount(uint256 _amount) external;
	function setMinMintInterval(uint256 _interval) external;
}

contract StakingAssetHandler is IStakingAssetHandler, Ownable {
	IMintableERC20 public immutable STAKING_ASSET;

	uint256 public depositAmount;
	uint256 public lastMintTimestamp;
	uint256 public minMintInterval;
	IStakingCore public rollup;

	constructor(address _owner, address _stakingAsset, address _rollup, uint256 _depositAmount, uint256 _minMintInterval) Ownable(_owner) {
		STAKING_ASSET = IMintableERC20(_stakingAsset);
		depositAmount = _depositAmount;
		rollup = IStakingCore(_rollup);
		minMintInterval = _minMintInterval;
	}

	function addValidator(address _attester, address _proposer) external override onlyOwner {
		require(block.timestamp - lastMintTimestamp >= minMintInterval, "Min mint interval not met");
		lastMintTimestamp = block.timestamp;
		STAKING_ASSET.mint(address(this), depositAmount);
		rollup.deposit(_attester, _proposer, owner(), depositAmount);
	}

	function setRollup(address _rollup) external override onlyOwner {
		rollup = IStakingCore(_rollup);
	}

	function setDepositAmount(uint256 _amount) external override onlyOwner {
		depositAmount = _amount;
	}

	function setMinMintInterval(uint256 _interval) external override onlyOwner {
		minMintInterval = _interval;
	}

}
```

The owner of the handler will be a different EOA, since it will be held by the discord bot.

#### Upgrades

The handler will need to be upgraded to the new rollup address when a new rollup is made canonical.

This will be done by manually by the person on the Aztec Labs team managing the discord bot.

### Discord Bot

The `/add-validator` command needs to be augmented to accept a block number and an archive merkle proof.

When this command is invoked, it should:

1. Ensure the user has not added `X` validators already (using a mapping based on the user's discord ID)
2. Query L1 for the proven tip of the chain
3. Ensure that proven tip's block number matches the block number provided by the user
4. Verify the merkle proof
5. Mint staking assets for itself
6. Add the user's address to the validator set, specifying the discord bot's address as the withdrawer
7. Grant a new "validator" role in discord to the user and bump the user's validator count by 1
8. Confirm to the user that they were added successfully

#### Risks

This doesn't ensure that the user's node is properly gossiping. There should be documentation asking the user to check that they see a non-zero peer count in their node's logs.

#### Alternative design

It may have been possible to not have the user provide a membership path, and instead just supply a validator address, and then have our node inspect the p2p network. That would have required augmenting our ENRs to include validator addresses, and more logic to search ENRs for an address. Plus it wouldn't have ensure that the user's node was synced.

Separately, we could have just allowed this to remain a purely manual process, and required logs/challenges to be sent back and forth between a potential validator and someone at Aztec Labs.

That sounds error prone and doesn't sound like a good use of anyone's time, especially when there could be tens to hundreds of validators going through this process.

### Sequencer Client

The sequencer must be updated in its block building logic to ensure that it does not exceed the mana limit for a block as specified on L1.

For now, it can simply query the rollup for `getManaLimit` before building each block; at mainnet, we will be able to move this call to startup, since the rollup will be immutable.

In addition, it must have a new environment variable "MAX_BLOCK_MANA"; when building a block it should stop at the minimum of the contract-specified mana target and the environment variable.

### P2P

The mempools will need to be updated to not be unbounded in size.

Simplest solution in the immediate term is to have the mempool reject any transactions that would cause the mempool to grow beyond some fixed size, set via an environment variable.

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
- e2e test that sequencer client respects the `MAX_BLOCK_MANA` environment variable
- e2e test that the sequencer client respects the contract-specified mana target
- Manual testing of adding a validator using the new flow on discord
- Verify that a validator added via discord may be removed as expected
- Verify that adding a validator grants a "validator" role in discord
- Verify that the discord bot enforces a configurable limit of validators per user

## Documentation Plan

Discord will need to be updated to tell users how to mint/bridge fee asset.

Discord will also need to be updated to provide documentation on how to use the `/add-validator` command

## Disclaimer

The information set out herein is for discussion purposes only and does not represent any binding indication or commitment by Aztec Labs and its employees to take any action whatsoever, including relating to the structure and/or any potential operation of the Aztec protocol or the protocol roadmap. In particular: (i) nothing in these projects, requests, or comments is intended to create any contractual or other form of legal relationship with Aztec Labs or third parties who engage with this AztecProtocol GitHub account (including, without limitation, by responding to a conversation or submitting comments) (ii) by engaging with any conversation or request, the relevant persons are consenting to Aztec Labs’ use and publication of such engagement and related information on an open-source basis (and agree that Aztec Labs will not treat such engagement and related information as confidential), and (iii) Aztec Labs is not under any duty to consider any or all engagements, and that consideration of such engagements and any decision to award grants or other rewards for any such engagement is entirely at Aztec Labs’ sole discretion. Please do not rely on any information on this account for any purpose - the development, release, and timing of any products, features, or functionality remains subject to change and is currently entirely hypothetical. Nothing on this account should be treated as an offer to sell any security or any other asset by Aztec Labs or its affiliates, and you should not rely on any content or comments for advice of any kind, including legal, investment, financial, tax, or other professional advice.
