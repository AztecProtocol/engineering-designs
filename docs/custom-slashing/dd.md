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

We want to expand this `SlashFactory` to allow nodes to programmatically create and vote for payloads to slash specific validators for specific amounts for specific "verifiable offences".

Specifically, we will automatically slash in the following cases:

1. (liveness) A block was proven, so slash all validators that did not attest to it.
2. (data availability and finality) An epoch was not proven and either i. the data is unavailable, or ii. the data is available and the epoch was valid, so slash each validator that was in the epoch's committee.
3. (safety) A validator proposed a block that was invalid, so slash the validator.

Last, we will add an override, which may be set by the node operator, which will configure the node to vote for a particular payload no matter what; this affords offline coordination to effect a slash.

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
- [x] The node MUST NOT trigger a slash unless it is certain that the validator was "faulty" (in its opinion).
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

The core function in the `SlashFactory` will look like:

```solidity
  function createSlashPayload(
    address[] memory _validators,
    uint256[] memory _amounts,
    uint256[] memory _offences
  ) external override(ISlashFactory) returns (IPayload) {
    require(
      _validators.length == _amounts.length,
      ISlashFactory.SlashPayloadAmountsLengthMismatch(_validators.length, _amounts.length)
    );
    require(
      _validators.length == _offences.length,
      ISlashFactory.SlashPayloadOffencesLengthMismatch(_validators.length, _offences.length)
    );

    (address predictedAddress, bool isDeployed) =
      getAddressAndIsDeployed(_validators, _amounts, _offences);

    if (isDeployed) {
      return IPayload(predictedAddress);
    }

    // Use a salt so that validators don't create many payloads for the same slash.
    bytes32 salt = keccak256(abi.encodePacked(_validators, _amounts, _offences));

    // Don't need to pass _offences as they are not used in the payload.
    SlashPayload payload = new SlashPayload{salt: salt}(_validators, VALIDATOR_SELECTION, _amounts);

    emit SlashPayloadCreated(address(payload), _validators, _amounts, _offences);
    return IPayload(address(payload));
  }
```

For now, the `offences` field will effectively be an enum, with the following possible values:

- 0: unknown
- 1: proven block not attested to
- 2: unproven valid epoch
- 3: invalid block proposed

The use of `uint256` for offences rather than an explicit enum allows for future flexibility, e.g. adding more offences and interpreting them off-chain, or, by using `uint256` rather than `uint8`, using a hash/commitment to some external data/proof.

Creating the payload via the `SlashFactory` will emit an event with the payload address, and the validator addresses/amounts/offences.

Aztec nodes will listen for these events, and then check if the validator committed the alleged offence. If so, they will vote/signal for the payload on L1.

## Node Changes

Most of the work is in the node.

### SlasherClient

The SlasherClient will remain the interface that the SequencerPublisher uses to adjust the transaction it sends to the forwarder contract. That is, the SequencerPublisher will continue to call `SlasherClient.getSlashPayload` to get the address of the payload to signal/vote for.

Its internal operations will be different, though.

It will instantiate "Watchers", which will have the following responsibilities:

- emit WANT_TO_SLASH events with the arguments to `createSlashPayload`
- expose a function which takes a validator address, amount, and offence and returns whether it agrees with the slash

The SlasherClient has the following responsibilities:

- listen for WANT_TO_SLASH events and create a payload from the arguments
- listen for the payload to be created and insert it into a priority queue
- return the payload with the highest priority when `getSlashPayload` is called

### Payload priority

Validators will need to have a way to order the various slashing events they observe.

Each time a new payload is observed on L1, the node will:

1. Sum the amounts of new slash proposals, so we have a `totalSlashAmount` for each payload.
2. Filter the payloads to only include those that the Watchers agree with.
3. Insert the payload with metadata into a priority queue
4. Sort the payloads by `totalSlashAmount`, largest to smallest.

Whenever `getSlashPayload` is called, the node will:

1. Check if there is an override payload. If so, signal/vote for it.
2. Filter out payloads from the queue that are older than a configurable TTL.
3. Return the first payload in the queue.

### Proven block not attested to

The first slashing event to be implemented will be for the case where a validator did not attest to a proven block.

This will be done by an `InactivityWatcher`, which will:

- listen for L2 blocks `chain-proven` events emitted from the `L2BlockStream`
- for each slot, call `Sentinel.processSlot` to get a map of validators and whether they voted
- emit a `WANT_TO_SLASH` event for each validator that missed more than `SLASH_INACTIVITY_CREATE_TARGET` slots, slashing them for the amount specified in `SLASH_INACTIVITY_CREATE_PENALTY`

When asked, it will agree to slash any validator that missed more than `SLASH_INACTIVITY_SIGNAL_TARGET` slots.

### A validator proposed an invalid block

This requires that full nodes have the ability to re-execute blocks.

Further, when executing a block, we will store invalid blocks in a cache, and emit an `invalid-block` event.

A `InvalidBlockWatcher` will take an executor as an argument, subscribe to the `invalid-block` event, and then emit a `WANT_TO_SLASH` event naming the proposer of the invalid block, slashing them for the amount specified in `SLASH_INVALID_BLOCK_PENALTY`.

When asked, it will agree to slash any validator that proposed an invalid block which it sees in its cache of invalid blocks.

### A valid epoch was not proven

This requires that full nodes have the ability to re-execute blocks.

A `ValidEpochUnprovenWatcher` will listen to `chain-pruned` events emitted by the `L2BlockStream`, and emit a `WANT_TO_SLASH` event for all validators that were in the epoch that was pruned IF there were no `invalid-block` events emitted for that epoch, slashing them for the amount specified in `SLASH_PRUNE_PENALTY`.

When asked, it will agree to slash any validator that was in an epoch that was pruned and there were no `invalid-block` events emitted for that epoch.

### New configuration

- `SLASH_PAYLOAD_TTL`: the maximum age of a payload to signal/vote for
- `SLASH_OVERRIDE_PAYLOAD`: the address of a payload to signal/vote for no matter what
- `SLASH_PRUNE_ENABLED`: whether to create a payload for epoch pruning
- `SLASH_PRUNE_PENALTY`: the amount to slash each validator that was in an epoch that was pruned
- `SLASH_INACTIVITY_CREATE_TARGET`: the percentage of attestations missed required to create a payload
- `SLASH_INACTIVITY_SIGNAL_TARGET`: the percentage of attestations missed required to signal/vote for the payload
- `SLASH_INACTIVITY_CREATE_PENALTY`: the amount to slash each validator that is inactive
- `SLASH_INVALID_BLOCK_ENABLED`: whether to signal/vote for a payload for invalid blocks
- `SLASH_INVALID_BLOCK_PENALTY`: the amount to slash each validator that proposed an invalid block

## Full Node Re-execution

There are two primary points in time where a full node would want to re-execute blocks:

1. When a block is proposed on the p2p network and is gathering attestations.
2. When a block been proposed to the L1 and is part of the pending chain.

To slash all malicious validators, we only need to support the first case; we need to adjust the validator client to re-execute, even if the node is not in the committee for the block, and retain a cache of invalid blocks.

To avoid slashing honest validators who built on a bad block which they blindly accepted/synced from the previous committee/L1, we need to support the second case.

### A generic `BlockBuilder`

We will build a new `BlockBuilder` class which is a component of the `AztecNode`.

Its interface will be:

```typescript
interface GlobalContext {
  chainId: Fr;
  version: Fr;
  blockNumber: Fr;
  slotNumber: Fr;
  timestamp: Fr;
  coinbase: EthAddress;
  feeRecipient: AztecAddress;
  gasFees: GasFees;
}

interface BuiltBlockResult {
  block: L2Block;
  publicGas: Gas;
  publicProcessorDuration: number;
  numMsgs: number;
  numTxs: number;
  numFailedTxs: number;
  blockBuildingTimer: Timer;
  usedTxs: Tx[];
}

interface ExecutionOptions {}

interface BlockBuilder {
  gatherTransactions(txHashes: TxHash[]): Promise<Tx[]>;
  executeTransactions(
    txs: Tx[],
    globals: GlobalContext,
    options: ExecutionOptions
  ): Promise<BuiltBlockResult>;
}
```

`executeTransactions` will execute transactions against the current world state and archiver.

The caller then may compare the results against whatever they expect (e.g. the state roots a peer sent, or that they downloaded from L1).

We will then update the archiver to optionally take a `BlockBuilder` as an argument, and use this to validate blocks coming in on L1.

Further, the Sequencer and Validator clients will accept a `BlockBuilder` as an argument, which they will use to build/re-execute blocks.

Thus we have:

1. Block comes in on p2p
   1. validator is on committee
      1. block is good, broadcast attestation
      2. block is bad, add to invalid block cache
   2. validator is not on committee
      1. block is good, do nothing
      2. block is bad, add to invalid block cache
2. Block comes in on L1
   1. block is good, add to state
   2. block is bad, add to invalid block cache

## Notes

The amount to slash should be high for testnet (e.g. the minimum stake amount). We can use a different amount for mainnet.

The threshold of number of validators (M/N) that need to signal/vote for the SlashFactory payload will be the same as the number of validators that need to signal/vote for any other slashing payload, i.e. this ratio is fixed at set per rollup.

This requires that M/N validators are listening to the same SlashFactory contract, and participating in the protocol.

If we do not have M/N validators participating, someone will need to make a "propose with lock" on the governance to deploy a new rollup instance. If that is not palatable, we could update the staking lib to allow the governance (not just the slasher) to slash validators; then someone could "propose with lock" to slash whatever validators governance decides.

In the future, we could also allow the slasher itself or governance to change who the slasher is.

## Timeline

Outline the timeline for the project. E.g.

- L1 contracts : 1 day
- Refactor SlasherClient : 2 days
- Implement ProvenBlockNotAttestedWatcher : 1-2 days
- Implement Rexecute on Full Node : 2 days
- Implement InvalidBlockWatcher : 1-2 days
- Implement ValidEpochUnprovenWatcher : 1-2 days
- Review/Polish : 2 days

Total: 10-12 days

The intent is to first merge functionality to slash inactive validators, then do the broader refactor needed for the later two cases.

## Disclaimer

The information set out herein is for discussion purposes only and does not represent any binding indication or commitment by Aztec Labs and its employees to take any action whatsoever, including relating to the structure and/or any potential operation of the Aztec protocol or the protocol roadmap. In particular: (i) nothing in these projects, requests, or comments is intended to create any contractual or other form of legal relationship with Aztec Labs or third parties who engage with this AztecProtocol GitHub account (including, without limitation, by responding to a conversation or submitting comments) (ii) by engaging with any conversation or request, the relevant persons are consenting to Aztec Labs’ use and publication of such engagement and related information on an open-source basis (and agree that Aztec Labs will not treat such engagement and related information as confidential), and (iii) Aztec Labs is not under any duty to consider any or all engagements, and that consideration of such engagements and any decision to award grants or other rewards for any such engagement is entirely at Aztec Labs’ sole discretion. Please do not rely on any information on this account for any purpose - the development, release, and timing of any products, features, or functionality remains subject to change and is currently entirely hypothetical. Nothing on this account should be treated as an offer to sell any security or any other asset by Aztec Labs or its affiliates, and you should not rely on any content or comments for advice of any kind, including legal, investment, financial, tax, or other professional advice.
