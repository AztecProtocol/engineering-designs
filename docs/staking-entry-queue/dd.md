# [Project Name] Design Document

- Owner: @just-mitch
- Approvers:
  - @LHerskind
  - @Maddiaa0
  - @aminsammara
- Target DD Approval Date: 2025-06-10
- Target Project Delivery Date: 2025-06-15

## Executive Summary

Requirement: Mitigate the risk of a large influx of byzantine stakers which could threaten the stability/security of the network.

We accomplish this by introducing a staking entry queue.

That is, when a staker deposits into the aztec network, they are added to a queue on L1.

## Timeline

Outline the timeline for the project. E.g.

- Build L1 queue: 1 day
- Update typescript: 1 day
- Review/polish: 1 day

Total: 3 days

## Introduction

It is not good for it to be possible for a large number of validators to (near) instantly start participating in block production.

This can result in, for example, where a significant portion of the validator set is malicious or faulty.

This is a particular concern at the outset of a network where it is possible for a large influx to occur in the absence of any flow control mechanism.

This can be problematic for the following reasons:

- It is possible that the nodes are improperly configured (accidentally or otherwise), and are not actually able to participate in block production
- It is possible that the p2p network will not form a well connected mesh, hindering throughput

It is better to allow a more gradual transition, rather than shock the system.

On the other hand, we do not want to allow anyone to start validating until there is a sufficiently large validator set size.

## Interface

Users are the would-be and current validators of the aztec network.

Currently, users are able to go directly to rollup instances, and call

```solidity
  function deposit(address _attester, address _withdrawer, bool _onCanonical) external;
```

This interface will remain _unchanged_, but the semantics will be that they are now "enqueued".

Users _will_ need to call `flushEntryQueue` though to move into the active state of validating.

```solidity
  function flushEntryQueue() external;
```

## Implementation

When would-be validators call `deposit`, they will enter a queue maintained by the rollup instance.

Validators in the queue do not participate in block production, and will not be sampled during committee selection.

We will restrict it such that `flushEntryQueue` may only be called once per epoch.

When _anyone_ calls `flushEntryQueue` in a given epoch `e`, the rollup will call `getEntryQueueFlushSize` to determine how many validators may be dequeued.

## getEntryQueueFlushSize

If the number of validators in the rollup is 0, and the number of validators in the queue is less than `bootstrapValidatorSetSize`,
then `getEntryQueueFlushSize` will return 0.

If the number of validators in the rollup is 0, and the number of validators in the queue is greater than or equal to `bootstrapValidatorSetSize`,
then `getEntryQueueFlushSize` will return `bootstrapFlushSize`.

If the number of validators in the rollup is greater than 0 and less than `bootstrapValidatorSetSize`, then `getEntryQueueFlushSize` will return `bootstrapFlushSize`.

If the number of validators in the rollup is greater than or equal to `bootstrapValidatorSetSize`, then `getEntryQueueFlushSize` will return Max( `normalFlushSizeMin`, `activeAttesterCount` / `normalFlushSizeQuotient`).

Thus, values for the following must be set:

```solidity
struct StakingQueueConfig {
  uint256 bootstrapValidatorSetSize;
  uint256 bootstrapFlushSize;
  uint256 normalFlushSizeMin;
  uint256 normalFlushSizeQuotient;
}
```

NOTE: We will NEVER flush more than `MAX_QUEUE_FLUSH_SIZE` validators, which will be hardcoded to `150`: it is applied as a Max at the end of every calculation.
This is to prevent a situation where flushing the queue would exceed the block gas limit.

As such, the implementation of `getEntryQueueFlushSize` looks as follows:

```solidity
    uint256 activeAttesterCount = getAttesterCountAtTime(Timestamp.wrap(block.timestamp));
    uint256 queueSize = store.entryQueue.length();

    // Only if there is bootstrap values configured will we look into boostrap or growth phases.
    if (config.bootstrapValidatorSetSize > 0) {
      // If bootstrap:
      if (activeAttesterCount == 0 && queueSize < config.bootstrapValidatorSetSize) {
        return 0;
      }

      // If growth:
      if (activeAttesterCount < config.bootstrapValidatorSetSize) {
        return Math.min(config.bootstrapFlushSize, StakingQueueLib.MAX_QUEUE_FLUSH_SIZE);
      }
    }

    return Math.min(
      Math.max(activeAttesterCount / config.normalFlushSizeQuotient, config.normalFlushSizeMin),
      StakingQueueLib.MAX_QUEUE_FLUSH_SIZE
    );
```

## flushEntryQueue

Accepts a `uint256 _maxAddableValidators`, and will dequeue up to that many, and deposit them into the GSE. The only trick here is that if the deposit into GSE fails due to out-of-gas, the entire transaction needs to revert.

```solidity
    uint256 queueLength = store.entryQueue.length();
    uint256 numToDequeue = Math.min(_maxAddableValidators, queueLength);
    store.stakingAsset.approve(address(store.gse), amount * numToDequeue);
    for (uint256 i = 0; i < numToDequeue; i++) {
      DepositArgs memory args = store.entryQueue.dequeue();
      (bool success, bytes memory data) = address(store.gse).call(
        abi.encodeWithSelector(
          IStakingCore.deposit.selector, args.attester, args.withdrawer, args.onCanonical
        )
      );
      if (success) {
        emit IStakingCore.Deposit(args.attester, args.withdrawer, amount);
      } else {
        // If the deposit fails, we generally ignore it, since we need to continue dequeuing to prevent DoS.
        // However, if the data is empty, we can assume that the deposit failed due to out of gas, since
        // we are only calling trusted contracts as part of gse.deposit.
        // When this happens, we need to revert the whole transaction, else it is possible to
        // empty the queue without making any deposits: e.g. the deposit always runs OOG, but
        // we have enough gas to refund/dequeue.
        require(data.length > 0, Errors.Staking__DepositOutOfGas());
        store.stakingAsset.transfer(args.withdrawer, amount);
        emit IStakingCore.FailedDeposit(args.attester, args.withdrawer);
      }
    }
    store.stakingAsset.approve(address(store.gse), 0);
  }
```

---

### Alternative designs

#### Force draining the queue during setup epoch

We could have had it such that when calling `setupEpoch` the caller must drain the queue. This would prevent any build up in the queue, but increase the operation costs for the protocol. Current design shifts more up-front costs (and complexity) to the user.

#### Single shared queue for all rollup instances

Rather than having the queue specific to each rollup instance, we could have had a global queue that was shared. This, however, would have removed the ability for different rollups to "tune" their parameters for entry and exit, and introduced another dependency on a "shared" contract that would be the only thing allowed to deposit into the rollup.

#### A logical queue via validator state

We could have added more information in the state associated with each validator when the deposit. Instead of inserting each validator into a queue, we could have created more states that would need to be checked when selecting the validators to form the committee for an epoch.

It was deemed better to have users pay an "up front" cost once to join the set than a "continual tax".

## Change Set

Fill in bullets for each area that will be affected by this change.

- [ ] Cryptography
- [ ] Noir
- [ ] Aztec.js
- [ ] PXE
- [ ] Aztec.nr
- [ ] Enshrined L2 Contracts
- [ ] Sequencer
- [ ] AVM
- [ ] Public Kernel Circuits
- [ ] Rollup Circuits
- [x] L1 Contracts
- [ ] Prover
- [ ] Economics
- [ ] P2P Network
- [ ] DevOps

## Test Plan

- All current flows work after injecting calls to drain the queue.
- Ensure that the queue cannot be bricked
- Ensure that the queue cannot dequeue at a rate faster than anticipated

## Documentation Plan

Will update the "running a sequencer" guide.

## Disclaimer

The information set out herein is for discussion purposes only and does not represent any binding indication or commitment by Aztec Labs and its employees to take any action whatsoever, including relating to the structure and/or any potential operation of the Aztec protocol or the protocol roadmap. In particular: (i) nothing in these projects, requests, or comments is intended to create any contractual or other form of legal relationship with Aztec Labs or third parties who engage with this AztecProtocol GitHub account (including, without limitation, by responding to a conversation or submitting comments) (ii) by engaging with any conversation or request, the relevant persons are consenting to Aztec Labs’ use and publication of such engagement and related information on an open-source basis (and agree that Aztec Labs will not treat such engagement and related information as confidential), and (iii) Aztec Labs is not under any duty to consider any or all engagements, and that consideration of such engagements and any decision to award grants or other rewards for any such engagement is entirely at Aztec Labs’ sole discretion. Please do not rely on any information on this account for any purpose - the development, release, and timing of any products, features, or functionality remains subject to change and is currently entirely hypothetical. Nothing on this account should be treated as an offer to sell any security or any other asset by Aztec Labs or its affiliates, and you should not rely on any content or comments for advice of any kind, including legal, investment, financial, tax, or other professional advice.
