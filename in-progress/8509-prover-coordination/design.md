# Prover Coordination

|                      |                                                             |
| -------------------- | ----------------------------------------------------------- |
| Issue                | https://github.com/AztecProtocol/aztec-packages/issues/8509 |
| Owners               | @just-mitch                                                 |
| Approvers            | @aminsammara @LHerskind @spalladino                         |
| Target Approval Date | 2024-09-18                                                  |


## Executive Summary

The aztec node will provide an interface for proving marketplaces to submit quotes for proving an epoch.

A proposer will be able to respond to a quote with a signed message, which a prover can submit to L1, along with a prover commitment bond. The prover can subsequently submit the proof to L1, releasing the bond.

This coordination will take place "out of protocol", via an optional p2p topic, with the slight exception/leak that the rollup contract will permit the prover to submit bonds/proofs in a proposer's stead.

## Introduction

Presently, there is no coordination between proposers or provers. A coordination mechanism is necessary to ensure that:

1. Proposers are able to obtain proofs for epochs, considering they will likely not have proving infrastructure.
2. Provers are not obliged to "race" each other to submit proofs, as this would be a waste of resources.

The protocol only "cares" about the proofs being submitted, but in practice, the node will need to coordinate the submission of proofs in a timely, efficient manner.

## Interface

Proving marketplaces will run full nodes, which will follow the pending chain. The node will expose a json-rpc endpoint for `submitEpochProofBid`, with the following signature:

```typescript
interface ProverCoordination {
  submitEpochProofBid(epoch: number, basisPointFee: number): Promise<void>;
}
```

This will be exposed via the cli as `aztec prover-coordination submit-epoch-proof-bid --epoch 123 --basis-point-fee 1000`.

Under the hood, the node will submit the following message to `/aztec/proof-quotes/make/0.1.0` 


```solidity
struct Quote {
  address prover;
  uint256 epoch;
  uint32 basisPointFee;
  Signature signature;
}
```

The `signature` will be produced using the L1 private key defined in the environment variable `PROVER_PUBLISHER_PRIVATE_KEY` to sign the message `keccak256(abi.encode(prover, epoch, basisPointFee))`.,

Proposers will counter-sign the quote by submitting a message to `/aztec/proof-quotes/take/0.1.0` with the following same `Quote` struct, but with the `signature` produced using the L1 private key defined in the environment variable `VALIDATOR_PRIVATE_KEY`.

The prover will be able to submit this Quote to `claimProofRight` on the rollup contract. The rollup contract will verify that:
- The epoch is in the proof claim phase
- There is not already a claim/proof for this epoch
- The quote has been signed by the proposer for the current slot
- The `prover` matches `msg.sender`
- The epoch matches the previous epoch (i.e. the one to be proven)
- The prover successfully transmits the bond (in TST) to the rollup contract

If all conditions are met, the rollup contract stores the quote, and the address of the proposer.

When the prover submits the proof, the rollup contract will pay out TST rewards to the proposer after paying the prover the basis point fee contained in the quote. It will also release the bond to the prover.

## Implementation

**TODO**

Delve into the specifics of the design. Include diagrams, code snippets, API descriptions, and database schema changes as necessary. Highlight any significant changes to the existing architecture or interfaces.

Discuss any alternative or rejected solutions.

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

**TODO**

Identify changes or additions to the user documentation or protocol spec.


## Rejection Reason

If the design is rejected, include a brief explanation of why.

## Abandonment Reason

If the design is abandoned mid-implementation, include a brief explanation of why.

## Implementation Deviations

If the design is implemented, include a brief explanation of deviations to the original design.

## Disclaimer

The information set out herein is for discussion purposes only and does not represent any binding indication or commitment by Aztec Labs and its employees to take any action whatsoever, including relating to the structure and/or any potential operation of the Aztec protocol or the protocol roadmap. In particular: (i) nothing in these projects, requests, or comments is intended to create any contractual or other form of legal relationship with Aztec Labs or third parties who engage with this AztecProtocol GitHub account (including, without limitation, by responding to a conversation or submitting comments) (ii) by engaging with any conversation or request, the relevant persons are consenting to Aztec Labs’ use and publication of such engagement and related information on an open-source basis (and agree that Aztec Labs will not treat such engagement and related information as confidential), and (iii) Aztec Labs is not under any duty to consider any or all engagements, and that consideration of such engagements and any decision to award grants or other rewards for any such engagement is entirely at Aztec Labs’ sole discretion. Please do not rely on any information on this account for any purpose - the development, release, and timing of any products, features, or functionality remains subject to change and is currently entirely hypothetical. Nothing on this account should be treated as an offer to sell any security or any other asset by Aztec Labs or its affiliates, and you should not rely on any content or comments for advice of any kind, including legal, investment, financial, tax, or other professional advice.
