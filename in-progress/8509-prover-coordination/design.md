# Prover Coordination

|                      |                                                             |
| -------------------- | ----------------------------------------------------------- |
| Issue                | https://github.com/AztecProtocol/aztec-packages/issues/8509 |
| Owners               | @just-mitch                                                 |
| Approvers            | @aminsammara @LHerskind @spalladino                         |
| Target Approval Date | 2024-09-18                                                  |


## Executive Summary

Presently, there is no coordination between proposers or provers. A coordination mechanism is necessary to ensure that:

1. Proposers are able to obtain proofs for epochs, considering they will likely not have proving infrastructure.
2. Provers are not obliged to "race" each other to submit proofs, as this would be a waste of resources.

The protocol only "cares" about the proofs being submitted, but in practice, the node will need to coordinate the submission of proofs in a timely, efficient manner.

The aztec node will provide an interface for proving marketplaces to submit quotes for proving an epoch.

The pricing on the quotes will be specified in basis points, which reflect the percentage of the total TST rewards contained in the epoch that the prover will receive if a proof of the epoch is submitted in time. See [the design for proof timeliness for additional details on the L1 interface](https://github.com/AztecProtocol/engineering-designs/pull/22).

The quotes will be _binding_: proposers will be able to submit a quote to the rollup contract which will stake a bond which the prover had previously deposited in escrow without additional coordination with the prover.

Provers will be able to submit their proofs of an epoch to the rollup contract without additional coordination with the proposer.

The _structure_ of the quote is enshrined.

The _coordination_ of how a quote is obtained by a proposer is not enshrined.

We propose an optional topic p2p network will be used for this coordination.

We expect the community to develop alternatives for proposers to obtain quotes from provers, e.g. private relays, and proposers will be free to find quotes from any source.

## Interface

Proving marketplaces will run full nodes, which will follow the pending chain. The node will expose a json-rpc endpoint for `submitEpochProofQuote`, with the following signature:

```typescript
interface ProverCoordination {
  submitEpochProofQuote(epoch: number, basisPointFee: number): Promise<void>;
}
```

This will be exposed via the cli as `aztec prover-coordination submit-epoch-proof-quote --epoch 123 --basis-point-fee 1000`.

Under the hood, the node will submit the following message to `/aztec/epoch-proof-quotes/0.1.0` 


```solidity
struct EpochProofQuote {
    Signature signature;
    uint256 epochToProve;
    uint256 validUntilSlot;
    uint256 bondAmount;
    address rollup;
    uint32 basisPointFee;
}
```

The `signature` will be produced using the L1 private key defined in the environment variable `PROVER_PUBLISHER_PRIVATE_KEY` to sign the message `keccak256(abi.encode(epochToProve, validUntilSlot, bondAmount, rollup, basisPointFee))`.

The Proposer will be able to submit this Quote to `claimEpochProofRight` on the rollup contract. See [the design for proof timeliness](https://github.com/AztecProtocol/engineering-designs/pull/22) for more info.

As an overview, L1 contracts will verify:
- The current epoch is in the proof claim phase
- There is not already a claim/proof for this epoch
- The quote has been signed by a prover with an available bond
- The current proposer (from the perspective of the rollup) matches `msg.sender`
- The epoch on the quote is the one the rollup contract is expecting (i.e. the oldest unproven epoch)

If all conditions are met, the rollup contract stores the quote, and the address of the proposer.

When the prover submits the proof, the rollup contract will pay out TST rewards to the proposer after paying the prover the basis point fee contained in the quote. It will also unstake the bond within the escrow contract.

### Concerns and Mitigations

#### Public quotes

Provers may not be comfortable submitting their quotes on the public p2p network, as this is effectively a first price auction, which is not ideal for the prover as it may drive down the price of their quotes. This is mitigated by the fact that this coordination mechanism is optional; a prover can stand up their own API and provide quotes to proposers directly.

Performing a second price, or sealed bid auction is not deemed necessary at this time.

#### Quotes without bonds

A prover might submit a quote but not actually have the funds to post a bond. This is mitigated by using a custom escrow that requires the prover to deposit the bond before submitting a quote. The escrow will have a delayed withdrawal process, so a proposer can query the escrow contract, then be confident that the funds will be there when they `claimEpochProofRight`.

## Implementation

### `EpochProofQuote`

EpochProofQuote needs an implementation in `circuit-types`, and needs to implement `Gossipable`. 

### In memory `EpochProofQuotePool`

We will need a pool of `EpochProofQuote` objects.

Its initial interface will be:
```typescript
interface EpochProofQuotePool {
  addQuote(quote: EpochProofQuote): void;
  getQuotes(epoch: number): EpochProofQuote[] | undefined;
}
```

We will implement a `InMemoryEpochProofQuotePool` that stores quotes in memory: durable storage is not deemed necessary at this time.

The implementation will only return quotes that are still valid.

### Extension to P2P Client

The `P2P` interface will be extended with 
```typescript
interface P2P {
  //...

  sendEpochProofQuote(quote: EpochProofQuote): Promise<void>;
  getEpochProofQuotes(epoch: number): Promise<EpochProofQuote[]>;
}
```

The  `P2PClient` will be extended with 
```typescript
class P2PClient {
  //...

  public async sendEpochProofQuote(quote: EpochProofQuote): Promise<void> {
    const ready = await this.isReady();
    if (!ready) {
      throw new Error('P2P client not ready');
    }
    await this.epochProofQuotePool.addQuote(quote);
    // we get `propagate` "for free" by implementing `Gossipable` on `EpochProofQuote`
    this.p2pService.propagate(quote);
  }
}
```

### Extension to `LibP2PService`

A new "route" needs to be added for the topic used by `EpochProofQuote` messages within `handleNewGossipMessage`.

It will call `processEpochProofQuoteFromPeer`, which will add the quote to the `EpochProofQuotePool` if it is still valid.

### ProofQuoteGovernor

The prover node will need to submit quotes to the p2p network in response to an epoch ending.

There will be a configurable controller that specifies under what conditions the prover will submit a quote.

This will sit on the main `work` loop of the prover node.

Its initial interface will be:

```typescript
interface ProofQuoteGovernor {
  ensureBond(amount: number): Promise<void>;
  produceEpochProofQuote(epoch: number): Promise<EpochProofQuote | undefined>;
}
```

When the prover node starts up, it will call `ensureBond` to ensure it has the required bond amount in escrow.

The prover node will detect that an epoch has ended, and if `produceEpochProofQuote` returns a quote (not undefined), it will submit a quote to the p2p network.

The default implementation of the governor will be to always produce a quote, and its basis point fee will be set in the environment variable `PROVER_BASIS_POINT_FEE`.

Separately, it needs a watcher on L1 to detect if its quote has been selected.

To this end, the `L1Publisher` will be extended with a new method:
```typescript
interface L1Publisher {
  getEpochProofClaim(): Promise<EpochProofClaim>;
}
```

The Prover node will call this method once per L2 slot to check if its quote has been selected.

If so, it will start building the proof and submit it to the rollup contract.

### Augment Proposer Logic

With the completion of [#8576 proposers submit proof claims](https://github.com/AztecProtocol/aztec-packages/issues/8576), proposers will be able to submit proof claims to the rollup contract using quotes they produced themselves. 

As noted in that issue, a separate implementation will be needed to allow proposers to submit proof claims using quotes they received from provers.

The tentative interfaces for this are:

```typescript
interface EpochProofQuoteSource {
  getEpochProofQuotes(epoch: number): Promise<EpochProofQuote[]>;
}

interface EpochProofQuoteAggregator {
  setSources(sources: EpochProofQuoteSource[]): void;
  getQuote(epoch: number): Promise<EpochProofQuote | undefined>;
}
```

Thus, `P2P` is a `EpochProofQuoteSource`, and the `EpochProofQuoteAggregator` will be used by the proposer to obtain quotes from the p2p network.


## Future Work

### Stricter ProofQuoteGovernor

The `ProofQuoteGovernor` should be updated to only produce a quote if it is convinced it has all the data required to produce a proof.

### Peer Scoring

If a peer propagates a quote that is not valid, we will penalize their peer score.



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
- [ ] Prover
- [x] Economics
- [x] P2P Network
- [ ] DevOps

## Test Plan

**TODO**

Outline what unit and e2e tests will be written. Describe the logic they cover and any mock objects used.

## Documentation Plan

Provers need documentation 


## Rejection Reason

If the design is rejected, include a brief explanation of why.

## Abandonment Reason

If the design is abandoned mid-implementation, include a brief explanation of why.

## Implementation Deviations

If the design is implemented, include a brief explanation of deviations to the original design.

## Disclaimer

The information set out herein is for discussion purposes only and does not represent any binding indication or commitment by Aztec Labs and its employees to take any action whatsoever, including relating to the structure and/or any potential operation of the Aztec protocol or the protocol roadmap. In particular: (i) nothing in these projects, requests, or comments is intended to create any contractual or other form of legal relationship with Aztec Labs or third parties who engage with this AztecProtocol GitHub account (including, without limitation, by responding to a conversation or submitting comments) (ii) by engaging with any conversation or request, the relevant persons are consenting to Aztec Labs’ use and publication of such engagement and related information on an open-source basis (and agree that Aztec Labs will not treat such engagement and related information as confidential), and (iii) Aztec Labs is not under any duty to consider any or all engagements, and that consideration of such engagements and any decision to award grants or other rewards for any such engagement is entirely at Aztec Labs’ sole discretion. Please do not rely on any information on this account for any purpose - the development, release, and timing of any products, features, or functionality remains subject to change and is currently entirely hypothetical. Nothing on this account should be treated as an offer to sell any security or any other asset by Aztec Labs or its affiliates, and you should not rely on any content or comments for advice of any kind, including legal, investment, financial, tax, or other professional advice.
