# Optimistic Attestation Signature Validation Design Document

- Owner: @spalladino
- Approvers:
  - @LHerskind or @just-mitch or @Maddiaa0
  - @aminsammara or @joeandrews
  - @PhilWindle

## Summary

In order to reduce L1 gas costs, we want to avoid verifying the validators' ECDSA signatures for block attestations on every block proposal.

We propose having them posted to L1, but not verified unless strictly needed.

## Background

Signature verification today costs about 160k gas per L2 proposed block. This is expensive.

In our benchmarks, a median `propose` call with a committee size of 48 validators costs `448,378` gas, and removing the `ValidatorSelectionLib.verify` function brings down this cost to `286,616`, saving `161762` gas (36% cheaper).

## Design and Rationale

Attestations provide the pending chain with the economic security of the epoch's validator committee that the txs for the block are available, and that the new state root follows correctly from executing those txs. Attestations also act as training wheels for our proving system, in case an attacker can generate a proof for an invalid public function execution.

### Full Nodes

To keep the same economic security for the pending chain, L2 nodes need to verify attestations on their own before accepting an L2 block as valid. This needs to be enforced in the `archiver` as blocks are being processed. Assuming the archiver is the sole source of truth for L1 data for the block, an L2 node will never serve data that does not have the security of the validator committee.

### Attestors

Before attesting to a proposal, validators check that the parent block hash is valid. Assuming validators only accept an L2 block if it has its attestations, as per the paragraph above, then they should not sign a block proposal unless it builds off a block that has all attestations. This means that attesting to a block is equivalent to attesting to it and to all its previous blocks in the epoch, and that these previous blocks have their attestations posted to L1.

### Proposers

Today the L1 rollup contract only accepts a new L2 block if it builds off from the previous one, and it's not possible for a new block to build off from an older one. This makes it easier to process the chain since it doesn't have any _forks_. This also helps with L1 reorgs: let's say the block for slot N+1 does not land, so the proposer for N+2 builds off from N; if N+1 eventually does get included via an L1 reorg, N+2 will be reverted automatically by L1.

To maintain this invariant, a proposer for slot N first needs to check that all previous blocks have their corresponding attestations. This will be monitored by the `archiver` as it processes L1. Before posting a new block, a proposer will first need to _invalidate_ all previous blocks with incorrect attestations. This requires a new method in the rollup contract that, given a block number and the attestations originally posted by its proposer, it confirms that attestations are invalid and rolls back to the block immediately before. The `sequencer` will need the additional logic to construct this call, and bundle it with its proposal.

### Proving

Assuming our circuits and proving systems are sound, a prover can post a proof for a given epoch without having to verify any attestation, which is enough for convincing L1 of the correctness of the proven state root. However, if we were to do this, we lose the training wheels provided by the economic security of the attestation committee, in the event of a bug in proving.

It follows that we want attestations to be verified. And as mentioned above, we know that verifying the attestations for the last block in an epoch is equivalent to verifying them for every block _in the epoch_, since every block in the epoch is attested by the same committee members, so the total stake is the same. So we should demand provers to verify the attestations of the last block in the epoch when they upload a proof.

## Open Questions

### How do provers verify the attestations from the last block in the epoch?

We have two options:

1. Prove the the validity of the attestations in the root rollup circuit (or in an extra circuit which gets recursively verified by the root rollup). This means no additional L1 gas costs at the expense of slightly longer rollup proving costs. This protects against any bugs on the AVM, but it does not protect against bugs in the overall proving system.

2. Prove the validity of the attestations on L1, as part of the rollup contract method for submitting a proof. This means higher L1 gas costs, but protects against any bugs on the proving system.

Given the tradeoffs in security, I push for the second option.

### Who can invalidate blocks, and what is the incentive?

One option is to restrict the rollup new `invalidate` method to the proposer in the current slot, so they can clear up previous invalid blocks before submitting, or to a prover submitting a proof, so they can clear up invalid blocks at the end of the epoch being proven (unclear if this is actually needed, given a prover can just submit a partial epoch proof without including the tail of invalid blocks).

Since invalidating a block is an expensive operation, a proposer can be given a gas rebate for this action. This rebate could be taken from the proposer who posted the block with invalid attestations. However, this means enshrining a slashing mechanism in the system, which involves additional complexity. We could initially require proposers (or provers) to absorb this additional expense, assuming rewards will be enough to offset it.

Alternatively, we can keep this method open for anyone to call. Assuming there is no reward for this action, we expect only block proposers to actually call it. Should we introduce a gas rebate and reward, we could end up with multiple nodes racing to claim this reward.

Given the incentives, I suggest keeping the method open and with no rewards. And to minimize complexity, I suggest no gas rebates at all.

### Where do attestations get posted?

While the cheapest option is not to post attestations at all, and require these to be sourced from the p2p layer in order to invalidate a block, we quickly run into data availability issues, since the invalidator may not have access to the invalid attestations in order to post them to L1 to trigger the invalidation.

Two options remain: posting them to calldata or to blobs. The flow in both cases is similar: proposers post attestations in either of them, and store in L1 a commitment to them (we can also modify the block hash to include a commitment to a set of attestations, to avoid an extra `SSTORE`, but this is a larger change). On block proposal, we check that the hash corresponds to the data posted. On (in)validation, the caller re-posts the attestations to L1, which get re-hashed and compared against the stored commitment, and then verified.

Calldata for a 48-sized committee is `(48 * 2/3 * 65) + (48 * 1/3 * 20) = 2400` bytes, or `38400` gas (note that after [EIP7623](https://eips.ethereum.org/EIPS/eip-7623) this could shoot up to `96k` depending on execution gas). This can be saved in favor of moving the attestations to blocks.

While posting on blobs is cheaper, it is more complex. As @iAmMichaelConnor points out:

> If you were to put the attestations and and attested block data in a static part of the 0th blob of the tx (say, the first 500 fields of the blob), then in the event that you need to do a fraud demonstration (I call them "demonstrations" to avoid confusion with the word "proof"), you might be able to unpack that data efficiently. You would need to do some maths in typescript-land to compute a batched KZG witness for the first 500 values of the blob; `blob[0], ..., blob[499]`. When you do your fraud proof tx, you'd need to feed-in those 500 uint256 values as calldata, along with a Q, C (48 bytes each). The smart contract would already have hard-coded a commitment to the zero polynomial for the first 500 roots of unity. And with that data, you can probably call the point evaluation precompile (50k gas) to demonstrate that those 500 values do really exist within the blob.
>
> Cons:
>
> - Complex, so more surface for bugs.
> - I'd need to double-check the maths, if you like the sound of it.
> - Miranda will not enjoy the news that we want to modify what's inside a blob.
> - It's not something that's easy to iterate on.
> - It'll be hard to update the circuits to put block proposal stuff in that fist blob.

Given these cons, I'd push for posting to CALLDATA.

### Do we accept a proven epoch with intermediate blocks that contain missing attestations?

From the design above, it follows that the L1 rollup contract would happily accept a proof for an epoch where only its last block contains valid attestations. Since L1 is the source of truth, all L2 nodes should adjust their view of the chain to accept unattested blocks if they are part of the proven chain.

Considering the above, what should an L2 node do if they see two blocks N and N+1 in L1, both from the same epoch, where N does not have its attestations? While this situation should not happen since the proposer for N+1 should refuse to build on N, there is nothing in the rollup contract that prevents it from happening. And since attestation for a block is economically equivalent to an attestation to also all its previous blocks within the same epoch, L2 nodes could happily accept both blocks N and N+1 in this example.

It's unclear to me whether this may lead to situations where proposers purposefully omit attestations for a block, knowing that this gets "patched" in the following one. This doesn't seem to be the case if the attestation committee refuses to sign off N+1 given the lack of attestations on L1 for N, but I still wanted to flag it.

The open question remains on whether L2 nodes should accept blocks N and N+1 in the example above, or wait until their epoch gets proven. For simplicity, I'd push for only accepting such blocks once they get proven.

## Changes to L1 Rollup Contract

### `propose`

Changes to `propose` include computing and storing the `attestationsHash` for each block, as well as storing the `ProposePayload` digest, so both can be used for (in)validation later. This involves an extra 318 gas for hashing (assuming 48 as committee size), plus 40k gas for additional `SSTORE`s (see "Optimizations" below to bring down this number).

### `invalidate`

We add a new `invalidate` method that removes a given block from the pending chain (and all following ones) after showing that its attestations were invalid. Assuming attestations were pushed in CALLDATA:

```
invalidate(blockNumber, attestations, committee, invalidIndex)
  let block = storage.blocks[blockNumber]
  let storedAttestationHash = block.attestationsHash
  require(storedAttestationHash === hash(attestations))

  let slotNumber = block.slotNumber
  let committeeCommitment = getCommitteeCommitmentAtSlot(slotNumber)
  require(committeeCommitment == hash(committee))

  let digest = block.proposalDigest
  require(ecrecover(attestations[invalidIndex], digest) !== committee[invalidIndex])
  storage.tips = storage.tips.updatePendingBlockNumber(blockNumber - 1)
```

Considering we need to do only a single `ECRECOVER`, we can estimate the gas for this operation to be `3000 * 31 = 93k` gas less than the current proposal validation, plus `4200` for the two SLOAD operations (`attestationsHash` and `committeeCommitment`), and the 38400 gas for calldata. This results in `160k - 93k + 4.2k + 38k = 110k` gas. Note that this function should hardly ever be called.

### `submitProof`

In addition to verifying the rollup validity proof, `submitProof` also needs to check the validity of attestations in the last block in the epoch (see "Proving" and "How do provers verify the attestations from the last block in the epoch" above).

```
submitProof(currentArgs, attestationsOrAddresses)
  let block = storage.blocks[currentArgs.endBlock]
  let storedAttestationHash = block.attestationsHash
  require(storedAttestationHash === hash(attestationsOrAddresses))

  let slotNumber = block.slotNumber
  let committeeCommitment = getCommitteeCommitmentAtSlot(slotNumber)

  let digest = block.proposalDigest
  let recoveredCommittee = [ecrecover(attestation, digest) if attestation is signature else attestation for attestation in attestationsOrAddresses]
  require(committeeCommitment == digest(recoveredCommittee))
```

We estimate additional gas costs to be `160k` (current cost for verification), plus `4200` for the two SLOAD operations (`attestationsHash` and `committeeCommitment`), and `38400` for the extra calldata, for a total of about `200k` gas.

### Optimizations

The changes above involve storing two additional words in the `CompressedBlockLog` storage for the rollup contract. These could instead be stored as a single word by hashing them together, and requesting them as input arguments on any functions that use them (`invalidate` and `submitProof`). This means we'd require an additional `318 + 42 + 20k` gas for `propose` (hashing attestations, hashing the `attestationsHash` and `digest` together, and storing this last value).

Note that, if we also shove the `blobCommitmentsHash` in this digest (which is only used once in `ProposeLib#propose` and once in `EpochProofLib#getEpochProofPublicInputs`), we can save the extra 20k from the `SSTORE`:

```diff
struct CompressedBlockLog {
  CompressedSlot slotNumber;
  bytes32 archive;
  bytes32 headerHash;
- bytes32 blobCommitmentsHash;
+ bytes32 hash(blobCommitmentsHash, attestationsHash, payloadDigest)
}
```

Assuming we implement the optimizations listed above, we can get to `160k` less gas per block proposal, with an extra cost for proof submission of `200k`. Amortizing this extra cost across 32 blocks in an epoch, we end up with `154k` less gas per block proposal

## Disclaimer

The information set out herein is for discussion purposes only and does not represent any binding indication or commitment by Aztec Labs and its employees to take any action whatsoever, including relating to the structure and/or any potential operation of the Aztec protocol or the protocol roadmap. In particular: (i) nothing in these projects, requests, or comments is intended to create any contractual or other form of legal relationship with Aztec Labs or third parties who engage with this AztecProtocol GitHub account (including, without limitation, by responding to a conversation or submitting comments) (ii) by engaging with any conversation or request, the relevant persons are consenting to Aztec Labs’ use and publication of such engagement and related information on an open-source basis (and agree that Aztec Labs will not treat such engagement and related information as confidential), and (iii) Aztec Labs is not under any duty to consider any or all engagements, and that consideration of such engagements and any decision to award grants or other rewards for any such engagement is entirely at Aztec Labs’ sole discretion. Please do not rely on any information on this account for any purpose - the development, release, and timing of any products, features, or functionality remains subject to change and is currently entirely hypothetical. Nothing on this account should be treated as an offer to sell any security or any other asset by Aztec Labs or its affiliates, and you should not rely on any content or comments for advice of any kind, including legal, investment, financial, tax, or other professional advice.
