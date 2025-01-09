# Forwarder Contract

|                      |                                                                                    |
| -------------------- | ---------------------------------------------------------------------------------- |
| Issue                | [Forwarder Contract](https://github.com/AztecProtocol/aztec-packages/issues/11103) |
| Owners               | @just-mitch                                                                        |
| Approvers            | @LHerskind @PhilWindle                                                             |
| Target Approval Date | 2025-01-20                                                                         |

## Executive Summary

Add a forwarder contract that allows the sequencer client to take multiple actions in the same L1 transaction.

Adjust the sequencer client to batch its actions into a single L1 transaction.

## Introduction

Within the same L1 transaction, we cannot make blob transactions and regular transactions from the same address.

We must be able to do that though, since we want to be able to do things like:

- propose and l2 block
- vote in the governance proposer contract
- claim an epoch proof quote
  all in the same L1 block.

### Goals

- Allow the sequencer client to take multiple actions in the same L1 transaction
- No changes to governance/staking
- Under 50 gas overhead per L2 transaction when operating at 10TPS

### Non-goals

- Support multiple actions for the prover node

## Interface

Node operators will need to deploy a forwarder contract.

When an attester deposits into the staking contract, the forwarder contract of the node operator will be specified as the proposer.

The Aztec Labs sequencer client implementation will need to be updated to use the forwarder contract; this involves refactoring `yarn-project/sequencer-client/src/publisher/l1-publisher.ts`.

## Implementation

### Forwarder Contract

It is straightforward.

```solidity
import {Address} from "@oz/utils/Address.sol";
import {Ownable} from "@oz/access/Ownable.sol";

contract Forwarder is Ownable {
  using Address for address;

  constructor(address __owner) Ownable(__owner) {}

  function forward(address[] calldata _to, bytes[] calldata _data) external onlyOwner {
    require(_to.length == _data.length);
    for (uint256 i = 0; i < _to.length; i++) {
      _to[i].functionCall(_data[i]);
    }
  }
}
```

### Refactoring L1 Publisher

L1 publisher will be broken into two classes:

- within `@aztec/sequencer-client`, there will be a `L1TxManager`
- within `@aztec/prover-node`, there will be a `L1TxPublisher`

Under the hood, both of these will use the `L1TxUtils` to create and send L1 transactions.

### ProverNode `L1TxPublisher`

The `ProverNode` will have a `L1TxPublisher` that has the functions within `l1-publisher.ts` that are related to the prover node, and have the same interface/semantics as the current `L1Publisher`. As an aside, this means `@aztec/prover-node` should no longer have a dependency on the `@aztec/sequencer-client` package.

In essence, this class is an API for L1 transactions for the prover node, and a simple wrapper around the `L1TxUtils` class.

### SequencerClient `L1TxManager`

The `SequencerClient` will have a `L1TxManager` that has many of the same functions currently within the `l1-publisher.ts`, but will have different semantics.

The `L1TxManager` will have:

- `queuedRequests: L1TxRequest[]`
- a work loop
- knowledge of the sequencer's forwarder contract
- knowledge of L1 slot boundaries
- knowledge of successful L1 transactions per L2 slot

The `Sequencer` uses its `L1TxManager` to make calls to:

- propose an l2 block
- cast a governance proposal vote
- cast a slashing vote
- claim an epoch proof quote

These requests will be added to the `queuedRequests` list.

The work loop will wait for a configurable amount of time (e.g. 6 seconds) into each L1 slot.

If there are any queued requests, it will send them to the forwarder contract, and flush the `queuedRequests` list.

### Gas

Once the L2 block body is removed from calldata, the "static" arguments to call the propose function should be under 1KB.

Operating at 10TPS, this would mean an overhead of under 3 gas per L2 transaction.

Unfortunately, the current design to support forced inclusion requires a hash for each transaction in the proposal args.

This means that the overhead per L2 transaction will be ~35 gas, which is still under 50 gas, but a significant portion of the overall target of 500 gas per L2 transaction.

### Alternative solutions

The original problem was voting at the same time as proposing an L2 block.

The sequencer client could have done the voting in its first L1 slot available, and delayed production of the L2 block until the next L1 slot.

This is unacceptable since the L2 blocks should eventually be published in the _first_ L1 slot available, to give the greatest chance of getting the L2 block included within our L2 slot.

Alternatively, the EmpireBase contract could have an additional address specified by validators, specifying a separate address that would be used for governance voting.

This seemed more complex, and has a similar problem when considering the flow where a proposer tries to claim an epoch proof quote instead of building a block (because there were no transactions at the start of the slot), but then a transaction became available, and they tried to build/propose an L2 block in the same slot; delays or other queueing in the sequencer client would be required regardless.

## Change Set

Fill in bullets for each area that will be affected by this change.

- [ ] Cryptography
- [ ] Noir
- [ ] Aztec.js
- [ ] PXE
- [ ] Aztec.nr
- [ ] Enshrined L2 Contracts
- [ ] Private Kernel Circuits
- [ ] Sequencer
- [ ] AVM
- [ ] Public Kernel Circuits
- [ ] Rollup Circuits
- [ ] L1 Contracts
- [ ] Prover
- [ ] Economics
- [ ] P2P Network
- [ ] DevOps

## Test Plan

Outline what unit and e2e tests will be written. Describe the logic they cover and any mock objects used.

## Documentation Plan

Identify changes or additions to the user documentation or protocol spec.

## Rejection Reason

If the design is rejected, include a brief explanation of why.

## Abandonment Reason

If the design is abandoned mid-implementation, include a brief explanation of why.

## Implementation Deviations

If the design is implemented, include a brief explanation of deviations to the original design.

## Disclaimer

The information set out herein is for discussion purposes only and does not represent any binding indication or commitment by Aztec Labs and its employees to take any action whatsoever, including relating to the structure and/or any potential operation of the Aztec protocol or the protocol roadmap. In particular: (i) nothing in these projects, requests, or comments is intended to create any contractual or other form of legal relationship with Aztec Labs or third parties who engage with this AztecProtocol GitHub account (including, without limitation, by responding to a conversation or submitting comments) (ii) by engaging with any conversation or request, the relevant persons are consenting to Aztec Labs’ use and publication of such engagement and related information on an open-source basis (and agree that Aztec Labs will not treat such engagement and related information as confidential), and (iii) Aztec Labs is not under any duty to consider any or all engagements, and that consideration of such engagements and any decision to award grants or other rewards for any such engagement is entirely at Aztec Labs’ sole discretion. Please do not rely on any information on this account for any purpose - the development, release, and timing of any products, features, or functionality remains subject to change and is currently entirely hypothetical. Nothing on this account should be treated as an offer to sell any security or any other asset by Aztec Labs or its affiliates, and you should not rely on any content or comments for advice of any kind, including legal, investment, financial, tax, or other professional advice.
