
|                      |                                                                        |
| -------------------- | ---------------------------------------------------------------------- |
| Issue                | [Spartan](https://github.com/AztecProtocol/aztec-packages/issues/7482) |
| Owners               | @aminsammara                                     |
| Approvers            | @joeandrews @ludamad @PhilWindle @LHerskind   |
| Target Approval Date | 2024-07-24                                                             |

## Executive Summary

Sequencer & Prover Testnet (S&P Testnet) is a series of intermediate network launches, each release scaling the network in the number of validators, throughput and features. The goal is to release each of these networks leading to a final release which will be the Public Testnet network. 

We will perform a total of 2 network upgrades to i) test the governance upgrade mechanism and ii) deploy the actual Testnet network after demonstrating Sepolia and blobDA work on a private live network. Both upgrades will be “state wipes” i.e. the upgraded networks will start from genesis state. 

We will run 1TPS for only 10 epochs while running the 3rd network deployed in S&P Testnet. If we fail, we try again in the 4th network launch. 

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
| Storage | PCIe Gen 4 x2, 4 TB of disk space | PCIe Gen 4 x2, 4 TB of disk space     |
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
| Whitelisted Validators | Aztec Labs will run 4 validators, full list here |
| Network | 1tx per block, 36s blocks, 32 block epochs |

**Gating Requirements**

* Prior to public release, Aztec Labs can internally run a stable network with 48 validators, 16 committee size, at least 0.02 TPS and proving on for at least a period of 90 hours. 
* Prior to public release, Aztec Labs to publish node guide and setup instructions. 
* After public release, the deployed network in Phase 1 can survive 120 hours without a fatal crash. 


### Phase 2

For the second deployment, we will increase the size of the validator set to 128 and throughput to 0.1 TPS (~3/4txs per block). Committee size stays the same. For a duration of 10 epochs, we will increase network throughput to about 1TPS.

The goals here are to test: 
1) The network can handle a variable tx load i.e. going from 0.1 TPS -> 1 TPS and back. 
2) How many provers can prove at 1TPS and what are the time/hardware requirements to do so. 

| Feature | Description |
| -----|-----|
| Committee Size | 16 |
| Validator Set | 128 |
| Whitelisted Validators | Aztec Labs will run 4 validators, full list here |
| Network | 0.1TPS, 36s blocks, 32 block epochs |

**Gating Requirements** 

* Prior to public release, Aztec Labs can internally run a stable network with 128 validators, 16 committee size, at least 0.1TPS with proving on for at least a period of 90 hours. 
* Prior to public release, Aztec Labs to publish node guide and setup instructions. 
* After public release, the deployed network in Phase 2 can survive 120 hours without a fatal crash. 
* 1 TPS is NOT a gating requirement. If the network crashes due to 1TPS, valuable learnings 🤷🏼‍♂️

### Phase 3

For the third deployment, we will perform the first governance upgrade. The upgrade will deploy a new Rollup with an efficient computation of the committee i.e. [Pleistarchus](#https://github.com/AztecProtocol/aztec-packages/issues/7978) of size 16. Validators will need to i) nominate proposals for voting by the Governance and ii) vote to execute the proposal. 


| Feature | Description |
| -----|-----|
| Committee Size | 16 |
| Validator Set | 128 |
| Whitelisted Validators | Aztec Labs will run 4 validators, full list here |
| Network | 0.1TPS, 36s blocks, 32 block epochs |

**Gating Requiremnets**

* [Pleistarchus](#https://github.com/AztecProtocol/aztec-packages/issues/7978)
* Prior to public release, Aztec Labs can internally run a stable network with 128 validators, 16 committee size, at least 0.1TPS with proving on and successfully complete the governance upgrade. 
* Prior to public release, Aztec Labs to share node guide and setup instructions including how to deploy the GovernanceProposer payload. 
* After public release, Aztec Labs will deploy the proposal to be voted on to the L1 and initiate a proposal nomination period. 
* After public release, participating validators successfully vote to execute the upgrade and move to the new Rollup. 

### Phase 4

This is the final deployment BEFORE Public Testnet begins. The objective here is to deploy a private network that “upgrades” into a permissionless Public Testnet. 

This deployment should land on Sepolia and we should be using blob DA. This is non-negotiable as we cannot launch Public Testnet without Sepolia or without blob DA.

| Feature | Description |
| -----|-----|
| Committee Size | 16 |
| Validator Set | 128 |
| Whitelisted Validators | Aztec Labs will run 4 validators, full list here |
| Network | 0.1TPS, 36s blocks, 32 block epochs |

**Gating Requirements**
* Validators stake sepETH to join the validator set.
* [Sepolia L1](#https://github.com/AztecProtocol/aztec-packages/issues/9456)
* [Blob DA](#https://github.com/AztecProtocol/aztec-packages/issues/8955)
* [L1 Reorgs](#https://github.com/AztecProtocol/aztec-packages/issues/8793)
* Prior to public release, Aztec Labs can internally run a stable network on Sepolia, with blob DA, 128 validators, 16 committee size, at least 0.1 TPS with proving on for at least a period of 90 hours. 
* Priot to public release, Aztec Labs to share node guide and setup instructions. 
* After public release, network is running without crash for at least 2 weeks.
* Infrastructure partners complete testing on Sepolia. 

