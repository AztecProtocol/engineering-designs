
|                      |                                                                        |
| -------------------- | ---------------------------------------------------------------------- |
| Issue                |  |
| Owners               | @aminsammara                                     |
| Approvers            | @joeandrews @ludamad @PhilWindle @LHerskind   |
| Target Approval Date | 2024-11-11                                                             |

## Executive Summary

The Sequencer & Prover Testnet (S&P Testnet) is structured as a progressive series of network launches, designed to scale the number of validators, network throughput, and protocol complexity with each release. The approach is to launch intermediate networks, rigorously test them internally, and advance to the next stage only if the network demonstrates stable performance for an established period. By moving through these phases deliberately, we aim to ensure a reliable testnet foundation while maintaining flexibility to address technical challenges as they arise.


### Goals
**Stability in Each Phase:** Each deployment is intended to operate stably over multiple days before moving forward. Each deployment advances network capacity or governance functionality, allowing us to evaluate new features in controlled conditions, gain insights, and refine configurations.

**Incremental Success:** We prioritize creating a positive, adaptable release schedule by avoiding rigid deadlines. This encourages each team to collaborate at their best pace, reducing technical debt and enhancing the quality of each milestone without pressure from missed timelines.

**Structured Coordination:** All teams will participate in a coordinated release cycle that aligns engineering, commercial, and S&P testnet participants. Deployment readiness is evaluated each Monday following internal stress tests, with potential releases set for Tuesday, allowing ample preparation and communication.

## Why Sequencer & Prover Testnet

The goal is to launch a fully permissionless Public Testnet, enabling users, sequencers, provers, and developers to interact with the Aztec network under conditions that, as much as possible, mirror real-world usage. S&P Testnet is a controlled testing environment that serves to derisk the Public Testnet network. 

S&P Testnet derisks the following:

1. The network can run at 1TPS throughput.
2. Committee size of 128 with +3000 validators does not impact block production.
3. Network can coordinate and execute client updates (or just "soft forks") with minimal interruption to block produciton.
4. Network can propose, vote on and execute a governance upgrade to hard fork the Rollup.
5. External provers, besides Aztec Labs, can fully prove the network at the 1TPS rate.
6. Ecosystem partners can onboard and test their apps on an execution environment that has feature parity with Public Testnet.

Since S&P Testnet is a real-world environment, Public Testnet is de-risked if the networks that are launched during S&P Testnet confirm the above hypotheses. S&P Testnet will progress into Public Testnet only once all the above has been accomplished. 

## Release Schedule

Aztec Labs follows a systematic release process to ensure each testnet deployment meets stability and performance criteria before public release:

**Internal Deployment (Thursday, 3 PM UTC):** Each week, Aztec Labs internally deploys a network that mirrors the intended public release. This environment is rigorously tested over the weekend. The internal network must remain operational and stable through the weekend. Any failures prompt further internal iterations instead of a public release.

**Evaluation (Monday, 2:30 PM UTC):** During the Alpha standup, the team assesses the internal deployment’s performance. If the network meets stability criteria, we commit to launching it publicly.

**Participant Communication (Monday, 6 PM UTC):** S&P Testnet participants are updated on the status of the public deployment. If no release is planned, participants are notified of the next steps.

**Public Deployment (Tuesday, 3 PM UTC):** If the internal deployment is successful, Aztec Labs releases the network to the public. Otherwise, the process resets, with another internal deployment scheduled for Thursday.


## Information for Participants

Please make sure to submit one fresh Ethereum address for every validator node you want to run during S&P Testnet. We are still thoroughly testing client software so in the case of undocumented code or network outages, please ping [Amin](#discordapp.com/users/65773032211231539) for any questions. 

Refer to the node guide here for setup instructions. 


**What are Gating Requirements?**

For each deployment, there are a set of requirements to i) deploy the network and ii) consider it a success and therefore move on to the next deployment. If a deployment fails to meet gating requiremnets, we will either not deploy anything or re-deploy the same network depending on the specific circumstances. 

## Deployments

### Phase 1

In Phase 1, Aztec Network can produce blocks and advance the Final Chain with a validator set of 48 at a throughput of up to 0.02 TPS. 

| Feature | Description |
| -----|-----|
| Max Committee Size | 16 |
| Validator Set | 48 |
| Network | 1tx per block, 36s blocks, 32 block epochs |

**Gating Requirements**

* Prior to public release, Aztec Labs can internally run a stable network with 48 validators, 16 committee size, at least 0.02 TPS and proving on for at least a period of 90 hours. 
* Prior to public release, Aztec Labs to publish node guide and setup instructions. 
* After public release, the deployed network in Phase 1 can survive 120 hours without a fatal crash. 


### Phase 2

In Phase 2, Aztec Network has a validator set of size 128 and supports throughput of upto 0.1 TPS (~3/4txs per block). The network can also coordinate and survive client upgrades /soft forks as well hard forks. 

> To pass Phase 2, we will perform a soft fork standalone first. Then perform a governance upgrade that deploys a new Rollup contract. 

The goals here are to test: 
1) The network can handle an increased throughput sporting a larger validator set
2) A soft fork: sequencers and provers can update client software and resync with minimal network disruption.
3) A hard fork: sequencers can coordinate to vote on governance proposals. 

| Feature | Description |
| -----|-----|
| Max Committee Size | 16 |
| Validator Set | 128 |
| Network | 0.1TPS, 36s blocks, 32 block epochs |

**Gating Requirements** 

* Prior to public release, Aztec Labs can internally run a stable network with 128 validators, 16 committee size, at least 0.1TPS with proving on for at least a period of 90 hours. 
* Prior to public release, Aztec Labs to publish node guide and setup instructions. 
* After public release, the deployed network in Phase 2 can survive 120 hours without a fatal crash.
* The client software update is successful, nodes are able to resync and continue building the Finalized Chain. 
* Governance upgrade is successfully executed, and validators move to the new Rollup.

### Phase 3

In Phase 3, the network features a full feature execution environment and attained full feature parity with Public Testnet. 

When this network passes the gating requirements, it is deployed as a new DevNet release. 

| Feature | Description |
| -----|-----|
| Committee Size | 16 |
| Validator Set | 128 |
| Network | 0.1TPS, 36s blocks, 32 block epochs, |

**Gating Requirements**
* [Minimal Staking](#https://github.com/AztecProtocol/aztec-packages/issues/10023)
* [Minimal Slashing](#https://github.com/AztecProtocol/aztec-packages/issues/10025)
* [Sepolia L1](#https://github.com/AztecProtocol/aztec-packages/issues/9456)
* [Blob DA](#https://github.com/AztecProtocol/aztec-packages/issues/8955)
* [L1 Reorgs](#https://github.com/AztecProtocol/aztec-packages/issues/8793)
* A subset of P0s from the [Testnet Milestone](#https://github.com/AztecProtocol/aztec-packages/milestone/42)
* Prior to public release, Aztec Labs can internally run a stable network with the above features, 128 validators, 16 committee size, at least 0.1 TPS with proving on for at least a period of 90 hours. 
* Priot to public release, Aztec Labs to share node guide and setup instructions. 
* After public release, network is running without crash for at least 1 week.
* Infrastructure partners are able to be onboarded to the DevNet version of this network.

### Phase 4

This is the final stage in S&P Testnet. The network has achieved full feature execution environment AND the highest throughput and validator set requirements. 

Phase 4 networks have the same feature set as Phase 3, but have proven stable when producing blocks at 1 TPS, 128 max committee size and at least 300 validators in the set. 

| Feature | Description |
| -----|-----|
| Committee Size | 128 |
| Validator Set | +300 |
| Network | 1TPS, 36s blocks, 32 block epochs |

**Gating Requirements**
* Prior to public release, Aztec Labs can internally run a stable network with the same feature set as in Phase 3 but with 128 max committee size, 1TPS with proving on. Assume validator set size is at least 300.
* After public release, network is running without crashing for at least 1 week. 

