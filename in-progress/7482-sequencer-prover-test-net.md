# Sequencer/Prover TestNet

|                      |                                                                                         |
| -------------------- | --------------------------------------------------------------------------------------- |
| Issue                | [Sequencer/Prover TestNet](https://github.com/AztecProtocol/aztec-packages/issues/7482) |
| Owners               | @just-mitch @LHerskind @Maddiaa0                                                        |
| Approvers            | @joeandrews @charlielye @iAmMichaelConnor @spalladino @PhilWindle                       |
| Target Approval Date | 2024-07-24                                                                              |

## Executive Summary

This is a design and implementation plan for a minimally viable Sequencer/Prover TestNet (SPTN).

The requirements we have designed against are as follows:

- have a "pending chain" with state updates at least every 30s
- have a design that can support 10 TPS
- have a quantifiable guarantee on the "pending chain" at the time a block is added such that:
  - app developers and users can rely on the pending chain state for UX
  - "proposers" can build ahead on the "pending chain"
- preserve pseudo-anonymity of "proposers"
- be able to select/rotate the set of "proposers"
- have a mechanism to incentivize "proposers" to participate in the "pending chain"
- have a mechanism to punish "proposers" for misbehaving
- do not depend on the "pending chain" for liveness
- do not require a hard fork to take advantage of most software updates
- have a design that can support forced inclusions in the future
- have a CI/CD framework to easily deploy the network in different configurations for modeling, stress and regression tests
- demonstrate an operational network with all the above requirements satisfied on/before 2024-09-16

Note that there is no integration with the execution environment required: the blocks submitted to the TestNet my be meaningless/empty.

## Introduction

There is a belief held in Aztec Labs that users will demand an experience with state updates at least every 30 seconds; our current network does not support this demand: each block must be proven before it can be added to the chain.

This design as drawn from recent thoughts on how we might support such a UX while maintaining a decentralized sequencer set, and we introduce several novel ideas that will allow us to build a minimally viable network within a compressed timeline.

We recognize that there may be aspects of this design that we may wish to change in the future, but we believe that:

1. The design is viable.
2. The design can be implemented in the prescribed timeline.
3. The design is flexible enough to support future changes.
4. Collecting feedback as soon as possible from real users within the above constraints is the best way to iterate on the design.

### Definitions

**Validator**
A node that is participating in consensus by producing blocks and attesting to blocks

**Slot**
Time is divided into fixed length slots. Within each slot, exactly one validator is selected to propose a block. A slot might be empty if no block is proposed. Sometimes the validator selected to propose is called proposer or sequencer

**Epoch**
A fixed-length sequence of slots

**Committee**
A list of validators to propose/attest blocks for an epoch. The committee is stable throughout the epoch. Attesters are active throughout the entire duration, and one proposer per slot is active.

**Attestation**
A vote on the head on the chain.

### Multiple Chains

We will explicitly support multiple chains. Specifically, there are 4 to acknowledge:

- "Pending Chain" - Blocks of transactions will be published at least every 30 seconds. None of the data on this chain need be on L1.
- "Assured Chain" - Reflects blocks published to L1, but not yet been proven.
- "Proven Chain" - Reflects blocks that have had their state diffs and proof published and verified on L1.
- "Finalized Chain" - Reflects blocks in the "Proven Chain" that have been finalized on L1 (Casper).

The Finalized Chain is a prefix of the Proven Chain, which is a prefix of the Assured Chain, which is a prefix of the Pending Chain.

Note: we do not need to "do" anything for the Finalized Chain, but it is relevant to users.

E.g., a front-end with low-value transactions may display the Pending Chain, but a DEX bridge might wait to release funds until the transaction is in the Finalized Chain.

### Committee and Timeliness

The committee will generally be responsible for building all chains (except the Finalized Chain).

If for some reason the committee is unable to build chains within a specified time, the network will preserve liveness by allowing anyone to build on the Proven Chain.

We refer to this as falling back to "based sequencing". 

In such a circumstance, the Pending and Assured Chains will be truncated to the last block in the Proven Chain.

### Pending Chain Consensus

Apart from the "based sequencing" case, in order to add a block to the Pending Chain, the proposer must submit proof that the committee has reached consensus on the block.

We will use CometBFT to facilitate this consensus.

### Top-Level Governance

We will have a "top-level" governance ("TLG") contract on L1. This TLG contract will be the minter of the AZT token on L1.

We will deploy a suite of contracts to L1 (a "deployment"), which corresponds to the SPTN.

A proposal will be sent to the TLG requesting that it fund the SPTN, which will be voted on by AZT holders.

### SPTN Governance

The SPTN will have its own governance contract.

This will specify an L1 account that is able to add or remove sequencers. In this respect, the sequencer selection algorithm is a flavor of "proof of governance" (PoG).

Initially, this account will be a contract owned Aztec Labs.

Sequencers will be required to stake AZT within the SPTN governance contract.

### Possible MainNet Governance

The deployment for MainNet could be governed by the TLG instead of a contract owned by Aztec Labs.

Any user with sufficient AZT can make proposals to the TLG to add or remove sequencers within MainNet.

Candidates for sequencers will be required to stake AZT.

Voting power on proposals will to the TLG be based on the amount of AZT held on L1.

### Sequencer Set Size

A flavor of the [scalability trilemma](https://eth2book.info/capella/part2/incentives/staking/#stake-size) is that we must balance among:
- the number of sequencers
- the time it takes to reach consensus
- the cost of reaching consensus

We have chosen to optimize for low cost and fast consensus. The exact number of sequencers will be determined via stress tests, modeling, and feedback from the community.

### Why PoG and not PoS?

For an L2 with a decentralized sequencer set, we believe that PoG is superior to PoS for the following reasons:

1. PoG reduces complexity (simpler sequencer selection, slashing, pricing, proving coordination, etc.)
2. Reduced complexity means lower costs for users
3. PoG can meet our decentralization goals
4. If we support upgrades, we can always switch to PoS in the future 
5. If we support upgrades, we can always switch to PoG in the future
   - so why not start with PoG, since governance already has implicit control over the sequencer set via upgrades?

See [this talk](https://www.youtube.com/watch?v=toPd1vgHjVE) for more on PoG.

### PoG Incentives and Slashing

Different deployments can have different incentives and punishments.

For the SPTN, we will create a simple incentives contract within the deployment:
- Whenever a block is added to the Assured Chain, the proposer will receive a reward.
- Whenever a block is added to the Proven Chain, the proposer will receive a reward.

We will need to add timeout parameters to allow other committee members to build on the Assured/Proven Chain if the proposer is unresponsive.

If a block is added to the Assured Chain that is not in the Proven Chain (or any other bad outcome occurs), a proposal can be made to aggressively slash (e.g. 100%) and kick a large portion (e.g. 100%) of the committee. Note that this can stand in for a large "prover bond".

The ability to have the community vote on slashing/kicking affords flexibility; perhaps the blame can be placed on a single committee member, or perhaps extenuating circumstances can be considered.

Another area where flexible slashing over a relatively small committee is useful is in the case of pricing transactions. We can allow proposers to name their own `fee_per_da/l2_gas` based on prevailing market rates; if a proposer consistently overprices transactions, the community can vote to slash/kick them, but **allowing the proposer set their own price greatly reduces the complexity of our in-protocol fee market**.

#### Quantifiable Guarantees

For example, if we went with a committee of size 37, and demanded that committee members stake $1M, suppose have a watcher that automatically proposes to slash/kick the committee. If the float of AZT is $1B, the committee would only control 3.7% of the float. Suppose that we only require a 15% participation in the vote to slash/kick, and a 60% majority to pass. Suppose that all committee members vote against the proposal, and we have 963 other AZT holders only vote 15% of the time, and of those that do vote, 90% vote to slash/kick. 

The probability that an arbitrary AZT holder:
- votes to slash/kick is .15 * .9 * (1 - .037) = .13
- votes against slash/kick is .15 * .1 * (1 - .037) + .037 = .0514
- doesn't vote is .85 * (1 - .037) = .81855

Monte carlo simulations show that the probability that the committee is slashed/kicked in this scenario is 99.6%, so the effective bond is 37 * $1M * .996 = $36.996M.

The actual parameters required to ensure a high value bond at MainNet will require observation of the network in practice; this is just an illustrative example.

### The Proven Chain

In order to add a block to the Proven Chain, the block submitter must submit a proof that the block is valid; how they obtain this proof is up to them. We will provide a design for a prover marketplace in the future.

As a side note, we believe that it will be easier to coordinate proving among a small PoG committee than among a large PoS committee, adding further benefits to users in the form of faster, cheaper updates to the Proven Chain.

## Interface

Who are your users, and how do they interact with this? What is the top-level interface?

## Implementation

Delve into the specifics of the design. Include diagrams, code snippets, API descriptions, and database schema changes as necessary. Highlight any significant changes to the existing architecture or interfaces.

Discuss any alternative or rejected solutions.

## Change Set

Fill in bullets for each area that will be affected by this change.

- [x] L1 Contracts
- [ ] Enshrined L2 Contracts
- [ ] Private Kernel Circuits
- [ ] Public Kernel Circuits
- [x] Rollup Circuits
- [ ] Aztec.nr
- [ ] Noir
- [ ] AVM
- [x] Sequencer
- [ ] Fees
- [x] P2P Network
- [ ] Cryptography
- [x] DevOps

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
