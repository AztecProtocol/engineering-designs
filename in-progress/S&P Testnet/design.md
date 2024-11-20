
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



## Release schedule

Every Thursday 3pm UTC Aztec Labs will internally deploy a network **identical** to what we want to publicly release the following week. This network must survive the weekend until Alpha standup on Monday 2:30pm UTC. 

If the network does not go down, then on Monday during Alpha standup, we commit to publicly deploying the network on Tuesday 3pm UTC. If the network goes down during the weekend, we commit to NOT deploying publicly that week. Instead we deploy privately again on Thursday and repeat the process the following Monday.

Every Monday 6pm UTC we will commnicate with S&P Testnet participants whether we're going ahead with launching a new network the following day on Tuesday 3pm UTC. 

### Information for Participants

Please make sure to submit one fresh Ethereum address for every validator node you want to run during S&P Testnet. We are still thoroughly testing client software so in the case of undocumented code or network outages, please ping [Amin](#discordapp.com/users/65773032211231539) for any questions. 

Refer to the node guide here for setup instructions. 

**Recommended hardware requirements**


 | 🖥️      |  Minimum      |   Recommended|
|---------|---------------|----------------|
| CPU     | 16 cores      | 32 cores       |
| Bandwidth | +250 mbps      | +500 mbps       |
| Storage | PCIe Gen 4, 2 TB of disk space | PCIe Gen 4 x2, 4 TB of disk space     |
| RAM     | DDR4 or better. 32GB of memory       | DDR4 or better. 64GB of memory         |

***What are Gating Requirements?**

For each deployment, there are a set of requirements to i) deploy the network and ii) consider it a success and therefore move on to the next deployment. If a deployment fails to meet gating requiremnets, we will either not deploy anything or re-deploy the same network depending on the specific circumstances. 

## Deployments

### Phase 1

The goal of the first deployment is to produce a stable network with 48 validators coordinating with provers to advance the Proven Chain. In addition to participating provers, Aztec Labs will run a prover node and submit bids to prove the network. 

| Feature | Description |
| -----|-----|
| Committee Size | 16 |
| Validator Set | 48 |
| Whitelisted Validators | Aztec Labs will run 4 validators |
| Network | 1tx per block, 36s blocks, 32 block epochs |

**Gating Requirements**

* Prior to public release, Aztec Labs can internally run a stable network with 48 validators, 16 committee size, at least 0.02 TPS and proving on for at least a period of 90 hours. 
* Prior to public release, Aztec Labs to publish node guide and setup instructions. 
* After public release, the deployed network in Phase 1 can survive 120 hours without a fatal crash. 


### Phase 2

For the second deployment, we will increase the size of the validator set to 128 and throughput to 0.1 TPS (~3/4txs per block), while committee size stays the same. First governance upgrade will run in Phase 2. 

The goals here are to test: 
1) The network can handle an increased throughput sporting a larger validator set
2) Sequencers can coordinate to vote on governance proposals. 

| Feature | Description |
| -----|-----|
| Committee Size | 16 |
| Validator Set | 128 |
| Whitelisted Validators | Aztec Labs will run 4 validators|
| Network | 0.1TPS, 36s blocks, 32 block epochs |

**Gating Requirements** 

* Prior to public release, Aztec Labs can internally run a stable network with 128 validators, 16 committee size, at least 0.1TPS with proving on for at least a period of 90 hours. 
* Prior to public release, Aztec Labs to publish node guide and setup instructions. 
* After public release, the deployed network in Phase 2 can survive 120 hours without a fatal crash.
* Governance upgrade is successfully executed, and validators move to the new Rollup. 

### Phase 3

This is the final deployment before the Public Testnet launch, aimed at deploying a private network with full feature parity to the Public Testnet. 

When the Gating Requirements have been met, we will commence Public Testnet. 

| Feature | Description |
| -----|-----|
| Committee Size | 16 |
| Validator Set | 128 |
| Whitelisted Validators | Aztec Labs will run 4 validators|
| Network | 0.1TPS, 36s blocks, 32 block epochs |

**Gating Requirements**
* [Minimal Staking](#https://github.com/AztecProtocol/aztec-packages/issues/10023)
* [Minimal Slashing](#https://github.com/AztecProtocol/aztec-packages/issues/10025)
* [Sepolia L1](#https://github.com/AztecProtocol/aztec-packages/issues/9456)
* [Blob DA](#https://github.com/AztecProtocol/aztec-packages/issues/8955)
* [L1 Reorgs](#https://github.com/AztecProtocol/aztec-packages/issues/8793)
* A subset of P0s from the [Testnet Milestone](#https://github.com/AztecProtocol/aztec-packages/milestone/42)
* Prior to public release, Aztec Labs can internally run a stable network on Sepolia, with blob DA, 128 validators, 16 committee size, at least 0.1 TPS with proving on for at least a period of 90 hours. 
* Priot to public release, Aztec Labs to share node guide and setup instructions. 
* After public release, network is running without crash for at least 2 weeks.
* Infrastructure partners complete testing on Sepolia. 

