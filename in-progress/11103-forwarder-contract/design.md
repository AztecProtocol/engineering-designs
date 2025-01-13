# Forwarder Contract

|                      |                                                                                    |
| -------------------- | ---------------------------------------------------------------------------------- |
| Issue                | [Forwarder Contract](https://github.com/AztecProtocol/aztec-packages/issues/11103) |
| Owners               | @just-mitch                                                                        |
| Approvers            | @LHerskind @PhilWindle @spalladino @spypsy                                         |
| Target Approval Date | 2025-01-15                                                                         |

## Executive Summary

Add a forwarder contract that allows the sequencer client to take multiple actions in the same L1 transaction.

Adjust the sequencer client to batch its actions into a single L1 transaction.

## Introduction

Within the same L1 transaction, one cannot make blob transactions and regular transactions from the same address.

However, aztec node operators must be able to do things like:

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

Note: this requires all the actions to succeed, so the sender must be sure that, e.g. a failed governance vote will not prevent the L2 block from being proposed.

Note: this implementation is not technically part of the protocol, and as such will live in `l1-contracts/src/periphery`.

### Refactoring L1 Publisher

L1 publisher will be broken into two classes:

- within `@aztec/sequencer-client`, there will be a `L1TxManager`
- within `@aztec/prover-node`, there will be a `L1TxPublisher`

Under the hood, both of these will use the `L1TxUtils` to create and send L1 transactions.

The publisher had also had responsibilities as a "getter" of different information on L1. This will be refactored into classes specific to the individual contracts that are being queried, e.g. `yarn-project/ethereum/src/contracts/rollup.ts` has a `Rollup` class that is responsible for getting information from the rollup contract.

### ProverNode `L1TxPublisher`

The `ProverNode` will have a `L1TxPublisher` that has the functions within `l1-publisher.ts` that are related to the prover node, and have the same interface/semantics as the current `L1Publisher`. As an aside, this means `@aztec/prover-node` should no longer have a dependency on the `@aztec/sequencer-client` package.

In essence, this class is an API for L1 transactions for the prover node, and a simple wrapper around the `L1TxUtils` class.

### SequencerClient `L1TxManager`

The `SequencerClient` will have a `L1TxManager` that has many of the same functions currently within the `l1-publisher.ts`, but will have different semantics.

The `L1TxManager` will have:

- `queuedRequests: L1TxRequest[]`
- knowledge of the sequencer's forwarder contract

It will have an interface of:

```typescript
interface L1TxManager {
  addRequest(request: L1TxRequest): void;
  sendRequests(): Promise<TransactionReceipt | undefined>;
}
```

The `Sequencer` uses its `L1TxManager.addRequest()` to push requests to the `queuedRequests` list whenever it wants to:

- propose an l2 block
- cast a governance proposal vote
- cast a slashing vote
- claim an epoch proof quote

At end of every iteration of the Sequencer's work loop, it will await a call to `L1TxManager.sendRequests()`, which will send the queued requests to the forwarder contract, and flush the `queuedRequests` list.

### Cancellation/Resend

A complication is that ethereum nodes make replacement of blob transactions expensive, and cancelation impossible, as they operate under the assumption that rollups seldom/never need to replace/cancel blob transactions.

See [geth's blob pool](https://github.com/ethereum/go-ethereum/blob/581e2140f22566655aa8fb2d1e9a6c4a740d3be1/core/txpool/blobpool/blobpool.go) for details/constraints.

This is not true for Aztec's decentralized sequencer set with strict L1 timeliness requirements on L2 blocks.

So a concern is the following scenario:

- proposer A submits a tx with nonce 1 (with a blob) that is not priced aggressively enough
- Tx1 sits in the blob pool, but is not included in an L1 block
- proposer A tries to submit another transaction, but needs to know to use Tx2
- Tx1 needs to be replaced with a higher fee, but it will revert if the network is in a different L2 slot and the bundle contained a proposal

This is addressed by:

- Upgrading viem to at least v2.15.0 to use their nonceManager to be aware of pending nonces
- Aggressive pricing of blob transactions
- The L1TxUtils will be able to speed up Tx1 (even if it reverts), which should unblock Tx2

### Setup

There will be an optional environment variable `sequencer.custForwarderContractAddress` that can be used to specify a custom forwarder contract address.

If this is not set, the sequencer will deploy the Aztec Labs implementation of the forwarder contract, using the Universal Deterministic Deployer, supplying the sequencer's address as the deployment salt, and the sequencer's address as the owner.

### Gas

Once the L2 block body is removed from calldata, the "static" arguments to call the propose function should be under 1KB.

Operating at 10TPS, this would mean an overhead of under 3 gas per L2 transaction.

Unfortunately, the current design to support forced inclusion requires a hash for each transaction in the proposal args.

This means that the overhead per L2 transaction will be ~35 gas, which is still under 50 gas, but a significant portion of the overall target of 500 gas per L2 transaction.

### Future work

For more robust cancellation, the sequencer client could maintain a pool of available EOAs, each of which are "owners"/"authorized senders" on its forwarder contract, and use one until it gets stuck, then switch to the next one: presumably by the time the sequencer client gets to the original EOA, the blob pool will have been cleared.

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
- [x] Sequencer
- [ ] AVM
- [ ] Public Kernel Circuits
- [ ] Rollup Circuits
- [x] L1 Contracts
- [x] Prover
- [ ] Economics
- [ ] P2P Network
- [ ] DevOps

## Test Plan

The primary test is [cluster governance upgrade](https://github.com/AztecProtocol/aztec-packages/issues/9638), ensuring that block production does not stall (as it currently does).

## Documentation Plan

No plans to document this as yet: the node operator guide effectively does not exist.

## Disclaimer

The information set out herein is for discussion purposes only and does not represent any binding indication or commitment by Aztec Labs and its employees to take any action whatsoever, including relating to the structure and/or any potential operation of the Aztec protocol or the protocol roadmap. In particular: (i) nothing in these projects, requests, or comments is intended to create any contractual or other form of legal relationship with Aztec Labs or third parties who engage with this AztecProtocol GitHub account (including, without limitation, by responding to a conversation or submitting comments) (ii) by engaging with any conversation or request, the relevant persons are consenting to Aztec Labs’ use and publication of such engagement and related information on an open-source basis (and agree that Aztec Labs will not treat such engagement and related information as confidential), and (iii) Aztec Labs is not under any duty to consider any or all engagements, and that consideration of such engagements and any decision to award grants or other rewards for any such engagement is entirely at Aztec Labs’ sole discretion. Please do not rely on any information on this account for any purpose - the development, release, and timing of any products, features, or functionality remains subject to change and is currently entirely hypothetical. Nothing on this account should be treated as an offer to sell any security or any other asset by Aztec Labs or its affiliates, and you should not rely on any content or comments for advice of any kind, including legal, investment, financial, tax, or other professional advice.
