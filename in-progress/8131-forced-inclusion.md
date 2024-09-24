# Forced Inclusion

|                      |                                    |
| -------------------- | ---------------------------------- |
| Issue                | [title](github.com/link/to/issue)  |
| Owners               | @lherskind                         |
| Approvers            | @just-mitch @aminsammara @Maddiaa0 |
| Target Approval Date | YYYY-MM-DD                         |

## Executive Summary

We propose a method to provide the Aztec network with similar **inclusion** censorship resistance of the base-layer.

The mechanisms uses a delayed queue on L1, and require the ability to include valid but failing transactions (many of these changes overlaps with tx-objects).
After some delay, the following blocks are complied to include transactions from the queue, and failing to do so will reject the blocks.

The length of the delay should take into account the expected delays of shared mutable, as it could be impossible to force a transaction that uses shared mutable if the queue delay is too large.

## Introduction

While the [based fallback mechanism](8404-based-fallback.md) provide a mechanism to which we could provide ledger growth, to properly satisfy our liveness requirements, we need to improve the censorship resistance guarantees of the system.
However for the censorship resistance to be meaningful, we will briefly go over what we define as censorship.

We use a similar definition of a censored transaction as the one outlined in [The Hand-off Problem](https://blog.init4.technology/p/the-hand-off-problem) (a good read that you should look into):

> _"a transaction is censored if a third party can prevent it from achieving its goal."_

For a system as the ours, even with the addition of the [based fallback mechanism](8404-based-fallback.md), there is a verity of methods a censor can use to keep a transaction out.

The simplest is that the committee simply ignore the transaction.
In this case, the user would need to wait until a more friendly committee comes along, and he is fully dependent on the consensus mechanism of our network being honest.

Note, that there is a case where a honest committee would ignore your transaction, you might be paying an insufficient fee.
This case should be easily solved, pay up you cheapskate!

But lets assume that this is not the case you were in, you paid a sufficient fee and they keep excluding it.

In rollups such as Arbitrum and Optimism both have a mechanism that allow the user to take his transactions directly to the base layer, and insert it into a "delayed" queue.
After some delay have passed, the elements of the delayed queue can be forced into the ordering, and the sequencer is required to include it, or he will enter a game of fraud or not where he already lost.

The delay is introduced into the system to ensure that the forced inclusions cannot be used as a way to censor the rollup itself.

Curtesy of [The Hand-off Problem](https://blog.init4.technology/p/the-hand-off-problem), we borrow this great figure:
![There must be a hand-off from unforced to forced inclusion.](https://substackcdn.com/image/fetch/f_auto,q_auto:good,fl_progressive:steep/https%3A%2F%2Fsubstack-post-media.s3.amazonaws.com%2Fpublic%2Fimages%2F35f3bee4-0a8d-4c40-9c8d-0a145be64d87_3216x1243.png)

The hand-off is here the point where we go from the ordering of transactions that the sequencer/proposer is freely choosing and the transactions that they are forced to include specifically ordered.
For Arbitrum and Optimisms that would be after this delay passes and it is forced into the ordering.

By having this forced insertion into the ordering the systems can get the same **inclusion** censorship resistance as their underlying baselayer.
As long as ledger growth is also ensured, it is looking pretty good on the liveness property.

However, nothing is really that easy.
Note the emphasis on **inclusion** censorship resistance.
While this provides a method to include the transaction, the transaction might itself revert, and so it is prevented from achieving its goal!

This is particularly an issue in build-ahead models, as the delay ensure that the sequencer have plenty of time to include transactions, before the hand-off, that will alter the state of the chain, potentially making the transaction revert.

Again, [The Hand-off Problem](https://blog.init4.technology/p/the-hand-off-problem) have a wonderful example and image:
Consider that you have forced a transactions that is to use a trading pair or lending market, the sequencer could include your transaction right after it have emptied the market or pushed it just enough for your tx to fail to then undo the move right after.
![The sequencer or builder can manipulate the state at the hand-off.](https://substackcdn.com/image/fetch/f_auto,q_auto:good,fl_progressive:steep/https%3A%2F%2Fsubstack-post-media.s3.amazonaws.com%2Fpublic%2Fimages%2F9b449e22-66d0-4fe1-bc25-28aea3329e72_2799x1428.png)

As this attack relies on contentious state being accessed, it is especially prone to happen for transactions operating in the public domain.
For a private transaction, they might occur if the same user sent multiple transactions using the same notes (a double-spend) which should rightfully be stopped.
Nevertheless, even a private transaction that is not double-spending might run into issues if its "lifetime" `max_block_number` have a smaller value than the time of forced inclusion.
If the proposers can delay the transaction sufficiently it would end up reverting even if no state actually changed.

A different attack could be to make the fees spike such that your forced transaction might have insufficient funds and end up reverting as an effect.
This can be avoided by not requiring forced transactions to pay the fee, as long as the transaction have a bounded amount of gas.
A reason that this could be acceptable is that the cost to go to L1 SHOULD be far greater than going to the L2, so you cannot use it as a mechanism to dos as it is still much more expensive than sending the same transaction and paying L2 gas for it.

However, it opens a annoying problem for us, the circuits would need to know that it is a forced transaction to give us that "special" treatment.

And how will we let it learn this fact?
We essentially have a list of to be forced transactions at the contract, and we need to know if the block includes any of these.
The naive way would be to loop through the transactions hashes, but then you perform a `sload` for every transaction (bye bye cheap transactions).
Alternatively you could have the proposer provide hints - he can tell which of the transactions are forced!
But what if he lies?
In the case where he lies, the circuit would believe it was a normal transaction, and he gotta pay up.
At the contract level, it would not check any value as it do not believe anything is in the forced inclusion, and if included before the deadline, the deadline will not make the proof submission fail either.

For those reasons, we will take the simple way out.
Let him pay, he might need to send 2 forced transactions, one to fund a balance and the second to perform his actual transaction, but that is part of the deal - take it or leave it.

To minimize the proposers ability to make the transaction fail it can be beneficial to force the hand-off to happen at the start of a block.
This essentially pushes the above example into a case of "multi-block censorship attack", which can be risky if the entity censoring is not producing both blocks.
If the entity is producing both blocks, it can be seen fairly close to the same block with the caveat of some TWAP logic etc behaving differently.

In the following sections, we will outline a design that allows us to provide **inclusion** guarantees to the users.

We will **NOT** provide a mechanism that provide **execution** guarantees.


> Consideration around minimum block size:  
> Since one attack vector a censor could employ is to create blocks of just 1 transaction from the forced queue and thereby censor most for a longer duration it might be beneficial to require a minimum block size.

## Implementation

While we would like most of the updates to be on the contract level, there are some checks that simply cannot be performed at the time where the insertion into the queue is performed.

Namely, while we can check that the private kernel is valid against a specific archive root at the time of queue insertion, we don't know yet how it will alter the state as it depends on the time it gets inserts.
As mentioned there is essentially an upper bound on that from the delay.

For this reason, we need to alter the circuits[^1], such that they will **not** cause an invalid rollup if a **FORCED** transaction were to fail due to:

- A revert in public setup (usually called non-revertible)
- Not included before `max_block_number`
- Have duplicate nullifiers
- Have invalid sibling pairs
- Have insufficient funds for the fee

[^1]: The reader who have spent too much time in these documents might recall that this have a big overlap with the changes needed if the tx objects idea is to be implemented 😯.

There is just one issue as mentioned at the end of the last chapter - figuring out if it is forced or not is a huge pain.
Therefore we will likely need to support it for all transactions instead, as we cannot easily discern the types from one another.

For the sake of simplicity, we will briefly assume that the above changes are made and describe the high-level architecture changes, before diving into the different aspects.

The idea is fairly simple:

- As part of the `Header` include a `txs_hash` which is the root of a SHA256 merkle tree, whose leafs are the first nullifiers (the transaction hashes) of the transactions in the block.
- The rollup circuits have to ensure that this `txs_hash` is build correctly, e.g., are from the transaction hashes of the same transactions published to DA.
- We take the idea of a delayed queue, that after some delay, forces the blocks to order transactions based on the queue.
  When inserting into the delayed queue, we can check the private kernel proof (fairly expensive 💸) and we store the transaction hash along with a bit of metadata, e.g., the time at which it must be included etc.
- At the time of epoch proof inclusion, the `txs_hash` roots can be used to prove the inclusion of members from the queue.
  If specific transactions were required and are not proven to be included, the ethereum transaction simple reverts.

Beware that we only really address the forced inclusion needs when the proof is proposed.
Nevertheless, the criteria for inclusion can be based on the time of the proposal.
This would mean that someone can make a proposal that does not include forced inclusions (which should have been included), and people might believe it to be the pending chain if they are not checking if it satisfy the force inclusions.

### The Delayed Queue Contract

Below we outline a delayed queue in vyper-like pseudo code.
Here assuming that is an extension of the rollup contract so we have access to proven tip and such.
Also note, that we are not too concerned about gas in below snippet, it is mainly there to convey an idea.

```python
struct ForceInclusion:
  tx_hash: bytes32
  include_by_epoch: uint256
  included: bool


struct ForceInclusionProof:
  proposal: ProposalHeader
  attestations: Attestations
  forced_inclusion_index: uint256,
  block_number: uint256
  index_in_block: uint256
  membership_proof: bytes32[]


forced_inclusions: public(HashMap[uint256, ForceInclusion])
forced_inclusion_tip: public(uint256)
forced_inclusion_count: public(uint256)


FORCE_INCLUSION_DEADLINE: immutable(uint256)


def __init__(deadline: uint256):
  self.FORCE_INCLUSION_DEADLINE = deadline


def initiate_force_include(
    tx: Tx,
    block_number_proven_against: uint256
):
  '''
  To be used by a user if they are getting massively censored by
  the committees.
  '''

  assert block_number_proven_against <= self.proven_tip.block_number

  archive = self.proposals[block_number_proven_against].archive
  assert archive != empty(bytes32)
  assert proof.verify(archive, tx)

  self.forced_inclusions[self.forced_inclusion_count] = ForceInclusion(
    tx_hash = tx.nullifiers[0],
    include_by_epoch = get_current_epoch() + 1 + self.FORCE_INCLUSION_DEADLINE
  )
  self.forced_inclusion_count += 1


def show_included(fip: ForceInclusionProof) -> bool:
  '''
  Convince the contract that a specific forced inclusion at `forced_inclusion_index` was
  indeed included in a block.
  '''
  if self.forced_inclusions[fip.forced_inclusion_index].included:
    return False

  assert fip.forced_inclusion_index < self.forced_inclusion_count
  tx_hash = self.forced_inclusions[fip.forced_inclusion_index].nullifier

  assert self.proposals[fip.block_number].hash == hash(fip.proposal, fip.attestations)
  assert fip.membership_proof.verify(tx_hash, fip.proposal.txs_hash)

  self.forced_inclusions[fip.forced_inclusion_index].included = True

  return self.progress_forced_inclusion_tip()


def progress_forced_inclusion_tip() -> bool:
  before = self.forced_inclusion_tip
  for i in range(self.forced_inclusion_tip, self.forced_inclusion_count):
    if not self.forced_inclusions[i].included:
      return
    self.forced_inclusion_tip = i
  return self.forced_inclusion_tip != before


@view
def force_until(epoch: uint256, tx_count: uint256) -> uint256:
  '''
  Given the total number of transactions in the blocks of the epoch, return the index
  we should have progressed to in the forced inclusion queue

  I think this one maybe still have some issues with inclusion. Think we have to do the "progress" check.
  Which could get really strange with the epoch.
  '''
  if tx_count == 0:
    return self.forced_inclusion_tip

  inclusions = 0;
  force_until = self.forced_inclusion_tip

  for i in range(self.self.forced_inclusion_tip, self.forced_inclusion_count):
    fi = self.forced_inclusions[i]
    if fi.included:
      # This was included in the past
      continue

    if fi.include_by_epoch > epoch + 1:
      break

    inclusions += 1
    force_until = i

    if inclusions == tx_count:
      break

  return force_until


@override
def submit_next_epoch_proof(proof, tx_count: uint256, archive: bytes32, fees: FeePayment[EPOCH_LENGTH]):
  epoch = self.get_epoch_at(self.get_timestamp_for_slot(self.blocks[self.provenBlockCount].slot_number))
  super.submit_next_epoch_proof(proof, tx_count, archive, fees)
  assert self.force_until(epoch, tx_count) <= self.forced_inclusion_tip, 'missing force inclusions'


def submit_proof_with_force(proof, tx_count: uint256, archive, fees: FeePayment[EPOCH_LENGTH], fips: ForceInclusionProof[]):
  epoch = self.get_epoch_at(self.get_timestamp_for_slot(self.blocks[self.provenBlockCount].slot_number))
  super.submit_next_epoch_proof(proof, tx_count, archive, fees)
  forced_until = self.force_until(epoch, tx_count)

  fip_block = 0
  fip_index = 0
  for fip in fips:
    assert fip.block_number > last_block_number_in_prior_epoch
    assert fip.block_number <= last_block_number_in_current_epoch

    if fip.block_number != fip_block:
      fip_block = fip.block_number
      fip_index = 0

    assert fip.index_in_block == fip_index, 'incorrect ordering'
    assert self.show_included(fip), 'did not progress the queue, incorrect ordering'

    fip_index += 1

  assert forced_until <= self.forced_inclusion_tip, 'missing force inclusions'
```

The reason we have the constraints on the block being in the epoch is fairly simple.
If we did not have this check, it would be possible to provide a proof for a transactions that was included in a previous epoch.
This could happen for example if you also had a block in the prior epoch.
Lets say that there are 2 transactions that have passed their "deadline" so they must be included.
You provide a block with 2 transactions, the first is from the forced queue, but the second is not.
The `force_until` would return that you need to progress by 2.
You then provide it the proof for the prior tx, it progress by 1, and then the proof for your new, the second.
At this point, you progressed by 2, but only one of them was actually new.

If someone have included a forced transaction earlier than it was required, anyone can use the `show_included` to mark it as included and progress the state of the delayed queue.

Notice that the forced inclusions outlined does **not** strictly require insertion into the beginning of the epoch.
But only that it is within the start of blocks within the epoch.

Also, observe, that a failure to include the forced transactions will be caught at the time of proof verification, not at the time of proposal!

#### Stricter inclusion constraints

By being stricter with our constraints, and more loose with our gas expenditure 😎 we can change the system such that it:
- Enforces the ordering earlier in the life-cycle;
- Force the delayed queue to be included as the first transactions, e.g., from the very start of the epoch, limiting the proposers power.

By extending the checks of the proposal, we can cause an early failure, such that we don't have to wait until the block have been proven to catch them meddling with the force inclusion ordering.

It requires a bit more accounting, and will likely be slightly more expensive, however, the improved properties seems to make up for that.

Could I not have written this in the first go?
Well, yes, but it might get confusing with both the pending and non pending functions so I'm going to keep them separate for now.


```python
# Tracks the current active "reality":
# Effectively a count on the number of pending chain reorgs.
active_pending: uint256
# For all the potential realities, tracks where the tip is
forced_pending_tip: HashMap[uint256, uint256]
# For all the potential realities, tracks what have been included
included_pending: HashMap[uint256, HashMap[uint256, bool]]

def propose(header: Header, fips: ForceInclusionProof[]):
  super.propose(header)

  epoch = self.get_epoch_at(header.global_variables.timestamp)
  force_until = force_until_pending(epoch, header.tx_count)

  for i, fip in enumerate(fips):
    assert fip.block_number == header.global_variables.block_number, 'incorrect block'
    assert fip.index_in_block == i, 'incorrect ordering'
    assert self.show_included_pending(fip), 'did not progress the queue, incorrect ordering'

  assert force_until <= self.forced_pending_tip[self.active_pending], 'missing force inclusions'


def prune():
  super.prune()
  self.active_pending += 1
  self.forced_pending_tip[self.active_pending] = self.forced_inclusion_tip


@view
def force_until_pending(epoch: uint256, tx_count: uint256) -> uint256:
  '''
  Very similar to `force_until` with the caveat that we also skip if it have been
  included previously in the pending chain.
  '''

  # Similar to the force_until
  if tx_count == 0:
    return self.forced_pending_tip[self.active_pending]

  inclusions = 0;
  force_until = self.forced_pending_tip[self.active_pending]

  for i in range(self.forced_pending_tip[self.active_pending] , self.forced_inclusion_count):
    fi = self.forced_inclusions[i]

    if fi.included or self.included_pending[self.active_pending][i]: # The diff is down here!
      # This was included in the past
      continue

    if fi.include_by_epoch > epoch + 1:
      break

    inclusions += 1
    force_until = i

    if inclusions == tx_count:
      break

  return force_until


def show_included_pending(fip: ForceInclusionProof) -> bool:
  '''
  Convince the contract that a specific forced inclusion at `forced_inclusion_index` was
  indeed included in a block.
  '''
  if self.forced_inclusions[fip.forced_inclusion_index].included:
    return False

  assert fip.forced_inclusion_index < self.forced_inclusion_count
  tx_hash = self.forced_inclusions[fip.forced_inclusion_index].tx_hash

  assert self.proposals[fip.block_number].hash == hash(fip.proposal, fip.attestations)
  assert fip.membership_proof.verify(tx_hash, fip.proposal.txs_hash)

  self.included_pending[self.active_pending][fip.forced_inclusion_index] = True

  return self.progress_forced_inclusion_tip_pending()


def progress_forced_inclusion_tip_pending() -> bool:
  before = self.forced_pending_tip[self.active_pending]
  for i in range(self.forced_pending_tip[self.active_pending], self.forced_inclusion_count):
    if not (self.forced_inclusions[i].included OR self.included_pending[self.active_pending][i]):
      break
    self.forced_pending_tip[self.active_pending] = i
  return self.forced_pending_tip[self.active_pending] != before


@override
def submit_proof(proof, tx_count: uint256, archive):
  epoch = self.get_epoch_at(self.get_timestamp_for_slot(self.blocks[self.provenBlockCount].slot_number))
  super.submit_next_epoch_proof(proof, tx_count, archive, fees)
  forced_until = self.force_until(epoch, tx_count)

  # Notice that this is very similar to `progress_forced_inclusion_tip_pending`
  before = self.forced_inclusion_tip
  for i in range(self.forced_inclusion_tip, self.forced_inclusion_count):
    if not (self.forced_inclusions[i].included OR self.included_pending[self.active_pending][i]):
      break
    self.forced_inclusion_tip = i
  
  assert forced_until <= self.forced_inclusion_tip, 'missing force inclusions'
```

### Block Validation

At the circuit level the block validation is altered slightly.
Similarly to how `txs_effects_hash` and `out_hash` compute the `txs_hash` and include it into the header.

That's it.

### Transaction Validation

A transaction is "valid" if and only if it can be included in a block (and subsequently an epoch), and the proof of that epoch can be verified on L1.

We need to ensure that all transactions with a valid private kernel is deemed valid, e.g., can be proven with the rollup circuits.

For this reason, we need to alter the circuits[^1], such that they will **not** cause an invalid rollup if transaction were to fail due to:

- A revert in public setup (also called non-revertible)
- Not included before `max_block_number`
- Have duplicate nullifiers
- Have invalid sibling pairs
- Have insufficient fee

The protocol must gracefully handle these cases, and instead of having the transaction be invalid, it should allow the transaction to be included, but with a "failed" status and **absolutely no** side effects.

In the event of a "failed" transaction, the transaction will appear in the block with its `tx_hash`, but not much else.
This require some changes to the transaction decoder and base rollups.
Also, it means that these transactions could be "replayed", potentially at a point in time where they would not be invalid, e.g., say the public setup no-longer fails.

For issues due to other assertions than invalid sibling paths we would need not perform the assertion, but instead "throw away" the side effects.

```noir
// Old
assert(
    self.kernel_data.public_inputs.constants.tx_context.version == self.constants.global_variables.version,
    "kernel version does not match the rollup version"
);

// New
self.purge_side_effects_unless(
    self.kernel_data.public_inputs.constants.tx_context.version == self.constants.global_variables.version,
   KERNEL_VERSION_MISMATCH // some error code we could put in the output
);
```

**Invalid sibling paths**:
As the sequencer is the one providing membership paths for the base rollup, it must not be possible for him to deliberately provide bad paths, thereby making the tx "invalid" and make it have no effect.
To address this, we can add another check to each of our membership or non memberships, to ensure that the paths provided were not utter nonsense.
Remember that failure to prove inclusion is not equal non-inclusion.
This check is fairly simple, if it is a membership check where an index was provided, and it fails, the sequencer must show what the "real" value was, and that it differs.
If it is a membership without a provided index, and it fails, a non-membership must be made.
If it is a non-membership we must prove that it was in there.
Essentially the sequencer is to do an xor operation, with membership and non-membership - one of them must be valid if he is not lying.

**No side effects**:
While there have previously been ideas to include the `tx_hash` (first nullifier) in the case that these checks fail, I don't think that these are fully compatible with forced inclusion.
Consider the fact, that the `tx_hash` is emitted as the nullifier equal to the hash of the `tx_request` from `address(0)`.
If I can create a `tx_request` such that the nullifier emitted from `address(0)` collides with any existing nullifiers that are not `tx_hash`es, requiring it to be inserted would require two of the same nullifiers to be included in the nullifier tree.
For a normal transaction, the transaction could not be included, and I would need to create a new one. 
But with a forced transaction, it might be impossible for me to include the transaction due to the circuits, but at the same time I am forced to include it by the rollup contract; this would halt the chain.

As a result, if any transaction fails, it will only appear in the `txs_hash` merkle tree root of the block header.

**Why not only do this for forced transactions?**
Look back at the introduction where we talked about this.

### PXE

The PXE should also change slightly, as it could offer sending a forced transaction instead of the usual flow.

### Sequencer

The sequencers would need to take into account the forced queue.
This could be done fairly simple by just having the "vanilla" sequencer build their blocks using first this queue and then their mempool.

## Change Set

Fill in bullets for each area that will be affected by this change.

- [ ] Cryptography
- [ ] Noir
- [ ] Aztec.js
- [x] PXE
- [ ] Aztec.nr
- [ ] Enshrined L2 Contracts
- [ ] Private Kernel Circuits
- [x] Sequencer
- [ ] AVM
- [ ] Public Kernel Circuits
- [x] Rollup Circuits
- [x] L1 Contracts
- [ ] Prover
- [ ] Economics
- [ ] P2P Network
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
