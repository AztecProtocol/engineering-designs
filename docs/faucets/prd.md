# Testnet Faucet Project Requirements Document

- Owner: @just-mitch
- Approvers:
  - @aminsammara
  - @rahul-kothari
  - @LHerskind
  - @signorecello
- Target PRD Approval Date: 2025-03-19
- Target Project Delivery Date: 2025-03-28

## Key words

The key words "MUST", "MUST NOT", "REQUIRED", "SHALL", "SHALL NOT", "SHOULD", "SHOULD NOT", "RECOMMENDED", "MAY", and "OPTIONAL" in this document are to be interpreted as described in [RFC 2119](https://datatracker.ietf.org/doc/html/rfc2119).

## Background

As part of running a testing network (test-net), we (Aztec Labs) wish for external actors to:

- participate in the validator set
- send transactions as users would.

This is to ensure that we get feedback on the stability and ease of operating a network such as ours, and to allow people to try it out.

Since we require a stake to become a validator and fees to pay for transactions, we need to distribute tokens to people.

Currently, we use 2 tokens:

1. the fee paying asset, which can be minted by anyone
2. the staking asset, which can be minted by its owner only

This allows us to separate transaction throughput control from control of the validator set.

Control of this kind is necessary in testnet because there is no economic value in the assets, thus validators have nothing at stake, and users would be free to DOS the network by flooding it with bogus transactions.

By controlling the fee asset, we can:

- prevent infinite minting, and thus a DOS against the potential users of the network

> [!info]
> Rate limiting the fee paying asset to control network congestion is not necessary or desirable, as we already have a mana limit mechanism for block construction. It is better to have users obtain a lot (but not infinite) of the fee asset, and thus use a lot of mana, so that they can perform transactions.

By controlling the validator set, we can:

- try to ensure that would-be validators are actually running synced nodes
- set their withdrawer to an address that we control, to immediately kick if needed

**Presently**:

- anyone can mint whatever fee asset they want
  - we are one infinite mint from chaos
- **we** need to **actively** mint funds and add to the validator set.

## Key Terms

- Fee Asset: ERC20 that can be bridged to "Fee Juice"
- Staking Asset: ERC20 that must be staked to become a validator

## Key assumptions and dependencies

1. The network can handle large influx of transactions
   - Phil's explorations seems to validate that this is sane
2. The network cannot defend itself, we need tight control over validators to kick misbehavior
   - We expect that this will change rapidly as the network matures

## Desired User Flow(s)

### The End User

Active Alice wants to try out what the Aztec network has to offer. She wants to do transfers, try NFT's and try out private DeFi.

Alice is happy as long as:

- it is quick and easy to get hold of assets to cover her transaction fees

### The Developer

Dave the developer want to try out what the Aztec network has to offer. He wish to build some cool new DeFi protocol, a fancy mechanism for escrows or just something with privacy.

David is happy as long as:

- it is quick and easy to get hold of assets to cover his deployment fees

### The Validator

Validating Vlad wants to run a validator.

Vlad is happy as long as:

- he can easily start a node
- easily get staking asset to run a validator on the node

## Requirements

### Functional Requirements (what the system does)

#### FUNC-01

Users MUST be able to run a 1-liner to get a fixed amount of fee asset on L1.

Why: Else no one will be able to use the chain
Where: Fallout from Alice's and Dave's user story

#### FUNC-02

It MUST be possible to update amount of fee assets that users receive.

Why: We acknowledge that the amount we initially give out may be too high or too low, and we need to be able to adjust it.
Where: Anticipation of supply/demand shocks and potential DoS scenarios

#### FUNC-03

Well-behaved nodes MUST use the lower value between the contract-specified mana target and their environment variable when building blocks.

Why: Otherwise nodes could build blocks that would fail on L1
Where: Observed deficiency in the current implementation

#### FUNC-04

It MUST be possible to update the mana target of the rollup.

Why: Allows us to update the mana target of the rollup in response to changing conditions
Where: Anticipation of supply/demand shocks and potential DoS scenarios

#### FUNC-05

Users MUST be able to submit an L1 address and complete a verification challenge for admission to the validator set. Producing the verification response SHOULD be a one-liner for anyone with a fully synced Aztec node.

Why: Ensures at least a basic level of sybil resistance
Where: Experience of validators joining the set

#### FUNC-06

We (Aztec Labs) MUST be able to add a user to the validator set outside of the faucet process.

Why: We want to be able to add users to the validator set for testing purposes.
Where: Experience of validators joining the set

#### FUNC-07

We (Aztec Labs) SHOULD be able to control the rate at which validators are added to the set.

Why: to avoid mass validator joins.
Where: Anticipation of people joining the set en masse when it is announced.

### Non-Functional Requirements (qualities the system has)

#### QUAL-01

The fee asset minting process SHOULD be permissionless.

Why: We want to make it easy for anyone to try out the network.
Where: Take Alice's story above, and assume she doesn't want to talk to anyone at Aztec Labs to get her assets.

#### QUAL-02

It MUST be easy for us (Aztec Labs) to remove a validator from the set that is not performing their job well.

Why: Ensure the health of the network.
Where: Experience of validators joining the set.

#### QUAL-03

It SHOULD NOT be trivial for people to create an arbitrary number of validators.

Why: to maintain a diverse, performant validator set.
Where: Anticipation of DOS attacks

### Performance Requirements

#### PERF-01

Users requesting fee asset SHOULD NOT need to wait more than 1 minute.

Why: This is one of the first actions users trying out the network should perform. It should be snappy.
Where: Experience of users bailing on anything mildly inconvenient.

#### PERF-02

Would-be validators SHOULD NOT need to wait more than 30 minutes to get added to the validator set (not necessarily the committee). The process SHOULD require under 5 minutes of active participation - ideally allowing validators to initiate the request and later return to find their node participating in the set.

Why: There may still be some manual intervention to add validators to the set, but it should still be time-bound and quick.
Where: Experience adding external validators to the set.

## Tradeoff Analysis

We recommend designs that are easy to implement and give us some protection, rather than convoluted designs that are bulletproof, considering this is for testnet only.

## Disclaimer

The information set out herein is for discussion purposes only and does not represent any binding indication or commitment by Aztec Labs and its employees to take any action whatsoever, including relating to the structure and/or any potential operation of the Aztec protocol or the protocol roadmap. In particular: (i) nothing in these projects, requests, or comments is intended to create any contractual or other form of legal relationship with Aztec Labs or third parties who engage with this AztecProtocol GitHub account (including, without limitation, by responding to a conversation or submitting comments) (ii) by engaging with any conversation or request, the relevant persons are consenting to Aztec Labs’ use and publication of such engagement and related information on an open-source basis (and agree that Aztec Labs will not treat such engagement and related information as confidential), and (iii) Aztec Labs is not under any duty to consider any or all engagements, and that consideration of such engagements and any decision to award grants or other rewards for any such engagement is entirely at Aztec Labs’ sole discretion. Please do not rely on any information on this account for any purpose - the development, release, and timing of any products, features, or functionality remains subject to change and is currently entirely hypothetical. Nothing on this account should be treated as an offer to sell any security or any other asset by Aztec Labs or its affiliates, and you should not rely on any content or comments for advice of any kind, including legal, investment, financial, tax, or other professional advice.
