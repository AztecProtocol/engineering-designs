
|                      |                                   |
| -------------------- | --------------------------------- |
| Issue                | [title](github.com/link/to/issue) |
| Owners               | @aminsammara                              |
| Approvers            | @LHerskind @just-mitch @JoeAndrews @sean                      |
| Target Approval Date | 2024-11-07                        |


## Executive Summary

This design introduces Proof Of Governance (PoG) for slashing. The rationale behind using PoG is that the use of offchain evidence for voting allows nice properties including:

1) Precision in slashing. Honest node operators should not be slashed.
2) TxObjects / Proofs are not available onchain so some offenses require the use of the P2P layer to detect wrongdoing.

## Introduction

Why do we slash?

We need to make sure the chain is always (eventually) finalizing new blocks. The conditions required for the chain to finalize new blocks are:
1) Sequencers are making valid block proposals
2) More than 2/3 of the committee is attesting on valid block proposals.
3) Provers can obtain timely proof data for txs included in the epoch.
4) Provers post proofs to the L1 on time.

Any action by an actor in violation of the above conditions should get slashed. 

In PoG, validators vote to slash any dishonest validators. To initiate a slashing proposal, a validator gossips a slashing proposal to other validators. To reduce coordination costs, we equip the validator client software with the capability to automatically respond to votes to slash dishonest validators based on onchain or offchain (i.e. p2p) evidence.

Any validator can initiate a proposal to slash any other validator(s). A proposal to slash must include the offense, epoch/slot information and the validators to be slashed.  

Validators vote by signing the slashing proposal and gossiping back the signed message over the p2p. Anyone can submit a slashing proposal that has garnered enough signatures to the L1 for execution. 

Based on the offense in question, the rollup contract establishes max slashable stakes. The rollup contract also checks some pre-requisites based on the offense. For example, a proposal to slash because of an invalid state transition slash cannot pass if the epoch has been proven. 

This is more subjective than purely onchain slashing but it enables precision that is not possible with purely onchain slashing. We can adopt Ethereum's principle of "honest validators should not be slashed" at the expense of increased coordination cost.



## Interface

Validators are the users of the PoG slashing mechanism. Full nodes can contribute data to validators but they should not be able to influence a slashing proposal. 

## Implementation

Define the slashing proposal sent to L1 to be the following payload:

```solidity
struct SlashingProposal({
  validatorSignature; // BLS signature
  aggregatedPublicKey; // Agg public key of validators who signed the proposal
  offense; // there is a pre-defined list of slashable behaviours
  validatorsToSlash; Optional address[] of validators to be slashed.
  epochNumber; Optional epoch in question
  slotNumbers; Optional uint256[] of slots in question
  calldata; Optional The calldata passed along with the invalid block proposal function call
  calldataProof; Optional The merkle root to the contract storage
  proverAddress; Optional prover address who failed to submit a proof
)}
```
The TS implementation of this but should be similar. The validators who receive a slashing proposal via the p2p must be able to decipher what data is needed to decide how to vote. If they don't have the data, they must request it from peers then determine. 


### PoG Slashable Offences

These are actions that we can and will slash using PoG.

**1. Committee signs off on an invalid state root**

Some validators implement a `ALWAYS_EXECUTE` flag where they execute every block regardless of whether they're in the committee or not. After every block proposal, these "Executing Validators" will retrieve the list of `TxHash` from L1 and attempt to re-execute all transactions in the block. 

In the happy path, the executing validators are able to obtain the `TxObjects` and proofs required to do so. If the resulting state root does not match what was published to L1, it reads the list of all committee members who signed on the invalid block. 

The executing validator prepares a payload containing:
1) The offense in question: Invalid state root
2) The slot number of the invalid block.
3) The list of committee members who signed off on the invalid block.

and gossips through to the validator set. 

Validators who receive this proposal first also read the L1 for the list of `TxHash` posted along the block in question. If it does not match what's in the slashing proposal, it discards the slashing proposal. 

If it does, they request all `TxEffects` and proofs from the p2p. As a last resort, they request from the validator who initiated the slashing proposal. They also read the state root posted to L1. 

If they're able to retreive all the required data to rexecute the block contents, and find an invalid state root they sign the slashing proposal and gossip the signed proposal via the p2p. 

The executing validator who initialized the slashing proposal must aggregate signatures and post to L1 for verification once >50% of the stake has signed the proposal. 

On the L1, the contract verifies that: 
1) The epoch has indeed re-orged.
2) The committee members named in the slashing proposal have signed the specific block in question. [INPUT NEEDED: How expensive is this?]

If the above checks pass, the named committee members are slashed. 

[IMAGE PLACEHOLDER]

**What should the validators do if they can't obtain the necessary data to re-execute the invalid state root?** 

The above scenario describes the "happy path" where a stupid committee coordinates an attack and shares the data with the rest of the validator set. In a sophisticated attack, the committee will plot to withhold the data. 

The question boils down to: Do we punish data withholding attacks given that they cannot be verified by the L1? 

The answer is -> Yes! A majority stake voting incorrectly on a data withholding attack is an even stronger violation of our honest-committee assumption. 

Therefore the executing validators who can't download all `TxObject` and proof data for any given block should initiate a data withholding slashing proposal, which works in exactly the same way as the invalid state root slashing proposal.


**2. ETH Congestion**

Provers may not be able to post proofs if the L1 is congested or is experiencing an inactivity leak. Instead of automatic slashing of the prover bond, the validator set can vote to "unslash" the provers. 

The prover's bond sits in escrow (or a separate contract) for 4 weeks. During which time the prover can plead their case and convince the validators to vote to unslash them. 

Since "Ethereum was congested" is a subjective statement, two ways we could implement this:

1) Make $t$ larger, giving the prover enough time to convince the validators to manually update their software to vote to unslash the prover.
2) Add an environment variable `max_eth_base_fee` that clients agree to implement. If `base_gas_fee > max_gas_fee` at the proof submission deadline time, then validators automatically accept votes to unslash prover.

They are largely equivalent except that the second requires less coordination.

### Hard to slash offences

We would like to slash the following actions but this would require vast changes to the p2p and/or would still be susceptible to attacks. Still including them here for brevity but these offenses are not slashable in the implementation.  

**1. Sequencers don't accept EpochProofQuotes**

If no EpochProofQuote is accepted within $C=13$ slots and the epoch reorgs, validators check for whether sequencers could have accepted an actionable EpochProofQuote during their turn. 

An actionable quote is one where:
i) The timestamp of receiving it was before the $C=13$th slot of the epoch. 
ii) The epoch information is correct. 
iii) The prover had the required bond in escrow. 
iv) The `basisPointFee` was within the allowable range. 

Validators check for whether they saw such an actionable `EpochProofQuote`. If they did, they initiate a proposal to slash all committee members that could've accepted the quote but did not. 

Why is this hard to implement?
- We're designing S&P coordination to be out-of-protocol. The above assumes provers send quotes via the p2p.
- Provers currently can send quotes even without having the necessary bond. For the validators to check historical balances, they must run L1 full nodes.
- Provers could send the quotes to a partition of the network, excluding the proposers who can activate the quote. This leads to timing games. 

**2. Inactivity Leak**

Upon entering Based Fallback mode, validators can slash the committee members which have not submitted blocks during their slots. Since entering Based Fallback mode requires $T_{/text{fallback, enter}$ time of no activity on the Pending Chain, validators initiate a proposal to slash the committees during that time period. 

Why is this hard to implement? 
- A malicious committee could abuse the Resp/Req module to send attestations to a partition of the network but not the current proposers. While the validators will then gossip the attestations back to the proposer, they may not make it back on time. Again timing games. 

We could implement an attestation deadline that takes into account time required to propagate the attestations from validators to proposers but this needs further studying.


### Changes to existing architecture

The main changes are to the L1 contracts, p2p and the validator clients. 

**Changes to the Validator Client**
1) We introduce a new validtor "mode" called Executing Validator which executes all transactions all the time, even when they are not selected for a committee. 
2) Validators must deduce what data they need to request from L1 and from other nodes when they receive a slashing proposal via the p2p.
3) Validators must decide whether to sign a slashing proposal or ignore it based on their view of the L1 and the p2p layer.
4) Validators should be able to send to L1 a slashing proposal for verification. 

**Changes to the P2P**
1) A new `Gossipable` type slashing proposal object.

**Changes to the L1 Contracts**
1) The L1 contracts must accept a slashing proposal object and verify whether certain conditions have been met.
2) The L1 contracts must be able to slash staked validators within a window commensurate with the validator exit delay. 


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
