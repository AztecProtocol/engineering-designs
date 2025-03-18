# Testnet Faucet Design Document

- Owner: @just-mitch
- Approvers:
  - @aminsammara
  - @rahul-kothari
  - @LHerskind
  - @signorecello
- [PRD](https://github.com/AztecProtocol/engineering-designs/blob/b2e744c2ae9f5552e404024edd1a9e20f5e3ea28/docs/faucets/prd.md)
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
'{"jsonrpc":"2.0","method":"node_getBlockHeader","params":[],"id":67}' \
"http://localhost:8080" | jq \
".result.lastArchive.nextAvailableLeafIndex"
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

## Implementation

### Fee Asset

For the fee asset, we will create a new contract `FeeAssetHandler`

```solidity
interface IFeeAssetHandler {
	function mint(address _recipient) external;
	function setMintAmount(uint256 _amount) external;
	function transferOwnershipOfFeeAsset(address _newOwner) external;
}

contract FeeAssetHandler is IFeeAssetHandler, Ownable {
	IFeeAsset immutable FeeAsset;
	uint256 mintAmount;

	constructor(address _owner, address _feeAsset, uint256 _mintAmount) Ownable(_owner) {
		FeeAsset = IFeeAsset(_feeAsset);
		mintAmount = _mintAmount;
	}

	function mint(address _recipient) external {
		FeeAsset.mint(_recipient, mintAmount);
	}

	function setMintAmount(uint256 _amount) external onlyOwner {
	    mintAmount = _amount;
	}

	function transferOwnershipOfFeeAsset(address _newOwner) external onlyOwner {
		FeeAsset.transferOwnership(_newOwner);
	}
}
```

We will manually deploy this contract. The owner will be the same as the current owner of the FeeAsset.

Considering the FeeAsset is already deployed on Sepolia, the owner will just need to transfer ownership of the FeeAsset to this handler.

The handler's deployed address will need to be made known in discord.

#### Choosing the mint amount

As mentioned above, we only need to prevent infinite minting (i.e. over 2^256).

We can calculate the maximum mint amount based on the expected L1 block production rate, the expected L1 gas cost of a mint, and the amount of time we expect the handler to be live.

Assume the cost to mint is 5K gas.

Then if a block were completely full of `mint` transactions, the maximum number of mints would be 38M / 5K = 7600.

This means that we could be maximally minting 7600 / 12 = 633 times per second.

Suppose that we expect the handler to be live for a maximum of 5 years.

Then we have a maximum of 5 _ 365 _ 24 _ 60 _ 60 \* 633 ~= 1e11 mints.

Thus, the maximum mint amount is (2^256 - 1) / 1e11 ~= 1e66.

But we'll err on the side of caution and use 1e42.

#### Alternative Design

The primary alternative would be to make a frontend UI that connects to a backend that has the account that is the owner of the token, then maintain a map on the backend to rate-limit different IP addresses, or have users sign up, etc.

The benefit is that if we went with the signup route, we could advertise to those users.

The downside is that that is significantly more infrastructure, and it doesn't necessarily improve the safety/control of the system.

### Staking Asset

The discord bot needs an RPC for an aztec node. One may be found at the bottom of the page [here](https://console.cloud.google.com/kubernetes/statefulset/us-west1-a/aztec-gke-public/ignition-testnet/ignition-testnet-aztec-network-full-node/details?hl=en&inv=1&invt=AbsUPg&project=testnet-440309) under the "endpoints" of "exposing services".

With this, the `/add-validator` command needs to be augmented to accept a block number and an archive membership path.

When this command is invoked, it should:

1. Ensure the user does not have a "validator" already
2. Query its aztec node for the specified block number
3. Ensure that the timestamp associated with the block is from within the last 5 minutes
4. Produce the membership path for the specified block
5. Ensure it matches the path provided by the user
6. Mint staking assets for itself
7. Add the user's address to the validator set, specifying itself as the withdrawer
8. Apply a new "validator" badge in discord to aid with sybil resistance (see below)
9. Confirm to the user that they were added successfully

#### Risks

This doesn't ensure that the user's node is properly gossiping. There should be documentation asking the user to check that they see a non-zero peer count in their node's logs.

#### Alternative design

It may have been possible to not have the user provide a membership path, and instead just supply a validator address, and then have our node inspect the p2p network. That would have required augmenting our ENRs to include validator addresses, and more logic to search ENRs for an address. Plus it wouldn't have ensure that the user's node was synced.

Separately, we could have just allowed this to remain a purely manual process, and required logs/challenges to be sent back and forth between a potential validator and someone at Aztec Labs.

That sounds error prone and doesn't sound like a good use of anyone's time, especially when there could be tens to hundreds of validators going through this process.

## Requirement Fulfillment

- [x] FUNC-01: single cast command
- [x] FUNC-02: part of the `FeeAssetHandler` interface
- [/] FUNC-03: current implementation requires 2 commands of the user
- [x] QUAL-01: withdrawer is set by discord bot
- [x] QUAL-02: user will need to create infinite discord accounts
- [x] PERF-01: should be under 24 seconds
- [x] PERF-02: should be under 24 seconds

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
- e2e test that the `bridge-erc20` utility works
- Manual testing of adding a validator using the new flow on discord
- Verify that a validator added via discord may be removed as expected
- Verify that adding a validator grants a badge which prevents creation of another validator

## Documentation Plan

Discord will need to be updated to tell users how to mint/bridge fee asset.

Discord will also need to be updated to provide documentation on how to use the `/add-validator` command

## Disclaimer

The information set out herein is for discussion purposes only and does not represent any binding indication or commitment by Aztec Labs and its employees to take any action whatsoever, including relating to the structure and/or any potential operation of the Aztec protocol or the protocol roadmap. In particular: (i) nothing in these projects, requests, or comments is intended to create any contractual or other form of legal relationship with Aztec Labs or third parties who engage with this AztecProtocol GitHub account (including, without limitation, by responding to a conversation or submitting comments) (ii) by engaging with any conversation or request, the relevant persons are consenting to Aztec Labs’ use and publication of such engagement and related information on an open-source basis (and agree that Aztec Labs will not treat such engagement and related information as confidential), and (iii) Aztec Labs is not under any duty to consider any or all engagements, and that consideration of such engagements and any decision to award grants or other rewards for any such engagement is entirely at Aztec Labs’ sole discretion. Please do not rely on any information on this account for any purpose - the development, release, and timing of any products, features, or functionality remains subject to change and is currently entirely hypothetical. Nothing on this account should be treated as an offer to sell any security or any other asset by Aztec Labs or its affiliates, and you should not rely on any content or comments for advice of any kind, including legal, investment, financial, tax, or other professional advice.
