# Custom Slashing Design Document

- Owner: @just-mitch
- Approvers:
  - @LHerskind
  - @Maddiaa0
- Target DD Approval Date: 2025-05-09
- Target Project Delivery Date: 2025-05-16

## Executive Summary

The L1 contracts currently only "allow" slashing all validators in an epoch if the epoch is never proven.

We want to provide a mechanism for slashing specific validators for not participating in consensus.

## Requirements

The requirements with filled checkboxes are met by the design below.

- [x] There MUST be ready-made L1 contract(s) that can be used to slash specific validators for not participating in consensus.
- [x] The Aztec Labs node client software ("the node") MUST automatically slash validators for not participating in consensus.
- [x] It SHOULD be possible to slash more than one validator at a time.
- [x] Coordinating the slash SHOULD NOT require any coordination between the validators beyond the existing voting/signalling mechanism; each validator SHOULD be able to inspect L1 and its state to determine:
  - If it agrees with the slash
  - How/where to vote/signal on L1
- [x] Node operators SHOULD be able to configure their node to specify thresholds for what they consider "not participating".
- [x] The "offence" that triggers the slash MAY be specified on L1.
- [ ] The amount to be slashed MAY be configurable without deploying a new contract.
- [ ] The threshold of number of validators (M/N) that need to signal/vote for the CustomSlashFactory payload MAY be configurable without deploying a new contract or a governance action.

## Overview

Rename the existing `SlashFactory` contract to `EpochSlashFactory` to denote that it slashes all validators in an epoch. Make a new `CustomSlashFactory` contract which creates a payload to slash a provided list of validators for an explicit offence. The amounts to be slashed for each offence will be provided in the constructor of the `CustomSlashFactory` contract. There will only be one explicit offence right now: "missing attestations". Creating the payload via the `CustomSlashFactory` will emit an event with the payload address, and the validator addresses.

Aztec nodes will listen for these events, and then check if the validator is bad committed the alleged offence. If so, they will vote/signal for the payload on L1.

## Details

The SlasherClient will remain the interface that the SequencerPublisher uses to adjust the transaction it sends to the forwarder contract.

Internally, though, the SlasherClient will monitor two conditions:

- an epoch was not proven, so slash all validators via the `EpochSlashFactory` contract (i.e. the current state, rename the L1 contract from `SlashFactory`)
- a validator has missed X% (e.g. 90%) of attestations according to the Sentinel, so slash that validator via the `CustomSlashFactory` contract (this is new)

Validators will need to have a way to order the various slashing events they observe.

Their first priority is to slash payloads from the `EpochSlashFactory`, sorted oldest to newest.

Their second priority is to slash payloads from the `CustomSlashFactory` for the "missing attestations" offence, sorted oldest to newest, but folding together payloads until one is found that they disagree with.

They will vote to slash any validator that has missed Y% (e.g. 50%) of attestations according to the Sentinel; there are two percentages to be configured:

- the percentage of attestations missed required to create a payload
- the percentage of attestations missed required to signal/vote for the payload

Node operators will configure their node to listen to the specific CustomSlashFactory contract and specify the percentage of attestations missed required to create a payload.

This will be done via CLI arguments or environment variables.

## Notes

The amount to slash should be high for testnet (e.g. the minimum stake amount). We can use a different amount for mainnet.

The threshold of number of validators (M/N) that need to signal/vote for the CustomSlashFactory payload will be the same as the number of validators that need to signal/vote for the EpochSlashFactory payload.

This requires that M/N validators are listening to the same CustomSlashFactory contract, and participating in the protocol.

If we do not have M/N validators participating, we will need to make a "propose with lock" on the governance to deploy a new rollup instance. If that is not palatable, we could update the staking lib to allow the governance (not just the slasher) to slash validators; then we could "propose with lock" to slash whatever validators governance decides.

## Timeline

Outline the timeline for the project. E.g.

- L1 contracts : 1 day
- Refactor SlasherClient : 1 day
- Review/Polish : 1-2 days

Total: 3-4 days

## Disclaimer

The information set out herein is for discussion purposes only and does not represent any binding indication or commitment by Aztec Labs and its employees to take any action whatsoever, including relating to the structure and/or any potential operation of the Aztec protocol or the protocol roadmap. In particular: (i) nothing in these projects, requests, or comments is intended to create any contractual or other form of legal relationship with Aztec Labs or third parties who engage with this AztecProtocol GitHub account (including, without limitation, by responding to a conversation or submitting comments) (ii) by engaging with any conversation or request, the relevant persons are consenting to Aztec Labs’ use and publication of such engagement and related information on an open-source basis (and agree that Aztec Labs will not treat such engagement and related information as confidential), and (iii) Aztec Labs is not under any duty to consider any or all engagements, and that consideration of such engagements and any decision to award grants or other rewards for any such engagement is entirely at Aztec Labs’ sole discretion. Please do not rely on any information on this account for any purpose - the development, release, and timing of any products, features, or functionality remains subject to change and is currently entirely hypothetical. Nothing on this account should be treated as an offer to sell any security or any other asset by Aztec Labs or its affiliates, and you should not rely on any content or comments for advice of any kind, including legal, investment, financial, tax, or other professional advice.
