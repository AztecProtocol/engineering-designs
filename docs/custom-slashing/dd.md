# Custom Slashing Design Document

- Owner: @just-mitch
- Approvers:
  - @LHerskind
  - @Maddiaa0
- Target DD Approval Date: 2025-05-09
- Target Project Delivery Date: 2025-05-16

## Executive Summary

The `StakingLib` designates a "slasher" address which is able to slash arbitrary validators for arbitrary amounts.

The contract used as the slasher is currently `Slasher`, which takes directives from a `SlashingProposer`.

The `SlashingProposer` is an instance of `EmpireBase`, which operates in "rounds" of `N` L2 slots, during which at least `M` proposers must vote for a specific contract address "payload" to be executed.

The payload just calls "slash", with the list of validators to slash, and the amount to slash each.

So the L1 contracts currently allow arbitrary slashing as long as the motion has support from `M/N` validators.

In practice, however, there are only mechanisms built to create and vote for payloads to slash all validators in an epoch if the epoch is never proven, namely an out-of-protocol `SlashFactory` contract, and corresponding logic on the node to utilize it.

We want to expand this `SlashFactory` to allow for "custom slashing", which would allow the node to programmatically create or vote for payloads to slash specific validators for specific amounts for specific offences.

In addition, we will add corresponding logic to the node to utilize the new `SlashFactory` to slash validators for inactivity.

Last, we will add an override, which may be set by the node operator, which will configure the node to vote for a particular payload no matter what.

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
- [x] The amount to be slashed MAY be configurable without deploying a new factory contract.
- [ ] The threshold of number of validators (M/N) that need to signal/vote for the CustomSlashFactory payload MAY be configurable without deploying a new contract or a governance action.

## L1 Changes

We make no changes to the `Slasher` contract, or any other "in-protocol" contracts.

Refactor the `SlashFactory` to accept an array of validator addresses, amounts, and offences. I.e.

```solidity
interface ISlashFactory {


  event SlashPayloadCreated(
    address payloadAddress, address[] validators, uint256[] amounts, uint256[] offences
  );

  function createSlashPayload(
    address[] memory _validators,
    uint256[] memory _amounts,
    uint256[] memory _offences
  ) external returns (IPayload);
}
```

For now, the `offences` field will effectively be an enum, with the following possible values:

- 0: unknown
- 1: epoch pruned
- 2: inactivity

The use of `uint256` for offences rather than an explicit enum allows for future flexibility, e.g. adding more offences and interpreting them off-chain, or, by using `uint256` rather than `uint8`, using a hash/commitment to some external data/proof.

Creating the payload via the `SlashFactory` will emit an event with the payload address, and the validator addresses/amounts/offences.

Aztec nodes will listen for these events, and then check if the validator committed the alleged offence. If so, they will vote/signal for the payload on L1.

## Node Changes

The SlasherClient will remain the interface that the SequencerPublisher uses to adjust the transaction it sends to the forwarder contract.

Internally, though, the SlasherClient will monitor two conditions:

- an epoch was not proven, so slash all validators (this exists today)
- a validator has missed X% (e.g. 90%) of attestations according to the Sentinel, so slash that validator (this is new)
- an override payload is set

Validators will need to have a way to order the various slashing events they observe.

The Aztec client will use the following heuristics to determine which payload to signal/vote for:

1. If there is an override payload, signal/vote for it.
2. Check if the payload is older than a configurable TTL. If so, discard it.
3. Sum the amounts of remaining slash proposals, so we have a `totalSlashAmount` for each payload.
4. Sort the payloads by `totalSlashAmount`, largest to smallest.
5. Pick the top payload that the validator agrees with (i.e. all the named validators committed the named offences), and signal/vote for it.

This process should be done each time:

- a new payload is created, as determined by watching the `SlashFactory` contract events
- the proposer has an opportunity to signal/vote

### Slashing for epoch pruning

We will need to modify the logic around slashing for epoch pruning. Instead of specifying a particular epoch, we just specify all the validators within the epoch.

### Slashing for inactivity

Regarding the slash for "inactivity", nodes will vote to slash any validator that has missed Y% (e.g. 50%) of attestations according to the Sentinel; there are two percentages to be configured:

- the percentage of attestations missed required to create a payload
- the percentage of attestations missed required to signal/vote for the payload

Node operators will configure their node to listen to a specific SlashFactory contract (as they do today) and specify the percentage of attestations missed required to create a payload.

This will be done via CLI arguments or environment variables.

### New configuration

- `SLASH_OVERRIDE_PAYLOAD`: the address of a payload to signal/vote for no matter what
- `SLASH_PAYLOAD_TTL`: the maximum age of a payload to signal/vote for
- `SLASH_PRUNE_CREATE`: whether to create a payload for epoch pruning
- `SLASH_PRUNE_PENALTY`: the amount to slash each validator that was in an epoch that was pruned
- `SLASH_PRUNE_SIGNAL`: whether to signal/vote for a payload for epoch pruning
- `SLASH_INACTIVITY_CREATE_TARGET`: the percentage of attestations missed required to create a payload
- `SLASH_INACTIVITY_CREATE_PENALTY`: the amount to slash each validator that is inactive
- `SLASH_INACTIVITY_SIGNAL_TARGET`: the percentage of attestations missed required to signal/vote for the payload

## Notes

The amount to slash should be high for testnet (e.g. the minimum stake amount). We can use a different amount for mainnet.

The threshold of number of validators (M/N) that need to signal/vote for the SlashFactory payload will be the same as the number of validators that need to signal/vote for any other slashing payload, i.e. this ratio is fixed at set per rollup.

This requires that M/N validators are listening to the same SlashFactory contract, and participating in the protocol.

If we do not have M/N validators participating, someone will need to make a "propose with lock" on the governance to deploy a new rollup instance. If that is not palatable, we could update the staking lib to allow the governance (not just the slasher) to slash validators; then someone could "propose with lock" to slash whatever validators governance decides.

In the future, we could also allow the slasher itself or governance to change who the slasher is.

## Timeline

Outline the timeline for the project. E.g.

- L1 contracts : 1 day
- Refactor SlasherClient : 1 day
- Review/Polish : 1-2 days

Total: 3-4 days

## Disclaimer

The information set out herein is for discussion purposes only and does not represent any binding indication or commitment by Aztec Labs and its employees to take any action whatsoever, including relating to the structure and/or any potential operation of the Aztec protocol or the protocol roadmap. In particular: (i) nothing in these projects, requests, or comments is intended to create any contractual or other form of legal relationship with Aztec Labs or third parties who engage with this AztecProtocol GitHub account (including, without limitation, by responding to a conversation or submitting comments) (ii) by engaging with any conversation or request, the relevant persons are consenting to Aztec Labs’ use and publication of such engagement and related information on an open-source basis (and agree that Aztec Labs will not treat such engagement and related information as confidential), and (iii) Aztec Labs is not under any duty to consider any or all engagements, and that consideration of such engagements and any decision to award grants or other rewards for any such engagement is entirely at Aztec Labs’ sole discretion. Please do not rely on any information on this account for any purpose - the development, release, and timing of any products, features, or functionality remains subject to change and is currently entirely hypothetical. Nothing on this account should be treated as an offer to sell any security or any other asset by Aztec Labs or its affiliates, and you should not rely on any content or comments for advice of any kind, including legal, investment, financial, tax, or other professional advice.
