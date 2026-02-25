- Owner: @LHerskind
- Approvers:
  - @aminsammara
  - @Maddiaa0
  - @just-mitch
  - @joeandrews
- Target DD Approval Date: 2025-05-23
- Target Project Delivery Date: 2025-05-28


> [!info] Keywords
>The key words "MUST", "MUST NOT", "REQUIRED", "SHALL", "SHALL NOT", "SHOULD", "SHOULD NOT", "RECOMMENDED", "MAY", and "OPTIONAL" in this document are to be interpreted as described in [RFC 2119](https://datatracker.ietf.org/doc/html/rfc2119).


# Executive Summary

This design changes fundamental assumptions and properties of the governance. The main design changes are:
1) Only rollup stakers have a say in governance, meaning that end users have no direct say in governance;
2) The voting power from stake can be delegated, and will by default be delegated to the rollup itself, which will follow the signalling;
3) "Willing" stake can be moved by governance and bypass the exit delay.
4) At the end of execution of proposals from the governance proposaler the canonical instance must have >X fraction of stake;

To do so, a number of changes are required:

A new Governance Staking Escrow (GSE) contract is introduced.  
This contract is used to escrow the assets of the stakers across different rollups such that it can be "moved" to a different rollup en-masse without needing individual exits. This is done using encapsulated accounting, such that every instance have their own account, and there is an additional "canonical" accounting that is movable. 

Having this in one contract, also allow us to re-use the existing `Governance` contract when limiting to only the sequencers having power, by limiting the `Governance` such that only the GSE can deposit into it, and thereby only the sequencers can have voting power.

The obvious implications are, that end users only have the softest of ignorable power over the rollup, and that it become harder to deal with failures within the sequencer set because they now are the only actors having a say.

> [!info]- Note of disagreement 
> Let it be known that I (@LHerskind) disagree strongly but commit to building
> [^1]. The points of disagreements are:
> 1) Relying on sequencers being aligned with users seems like a fever dream.
>     - See [solana governance - a comprehensive analysis](https://www.helius.dev/blog/solana-governance--a-comprehensive-analysis#cosmos)
> 2) Requiring no action by default to have upgrades seems dangerous to me
> 3) Bypassing safety measures for speed and convenience, ye I don't like it.
> 4) I don't believe using the amount of stake is a good measure for this. For example, if there are huge improvements to newer versions and they require less stake, they now have trouble becoming canonical.
>     - Some oddness related to staking and slashing, is that kicking 
>
>At the bare minimum it should be simple to revert. I suggest using a toggable whitelist for the governance. This will increase costs, keep the option.

# Timeline

- Build the Staking Escrow (without voting): 4 days
- Extend with Governance and Delegation: 4 days
- Updating and extending tests to cover new cases: 4 days

Total: 12 days
# Implementation

We will be discussing the implementation in two stages, first dealing with the staking alone, and then adding the extra logic needed for the governance and delegation.

## Stage One - Staking Escrow

As the first stage, we will focus just on the stake moving part, and the steps we take to realise it.

With staking escrow, we mean that there should be a common location (the GSE) where all the information to keep the staking set operational should be stored. 
This means that for every validator in the set, we should have information to construct the chunk: 
```solidity
struct Validator {
	address attester;
	address proposer;
	address withdrawer;
	uint256 stake;
}
```


We then will have this information for EVERY rollup instance (only possible to add a new if it is the current canonical as per the Registry). 

```solidity
mapping(Rollup => Validator[]) validatorSets;
```

At this point, we have logic that works very much like what we have currently, but merely using external storage. Only the "owning" `Rollup` can update its validator set, e.g., `add`, `remove` and `slash`. 

When depositing into a rollup, the rollup will forward the funds and information to be stored in the `GSE`. Likewise a withdrawal will be the rollup requesting the `GSE` to give it funds and delete a specific user. 

When sampling a committee etc, the rollup instance will ask the `GSE` for the size of its set such that it can sample, and then ask it to get the validators at specific indicies. 

The change comes when we say that we need "willing" stake to move to a new rollup "automatically" when it becomes canonical. To support this, we create an additional set, that is assigned a `MAGIC_CANONICAL_ADDRESS` instead of a specific instance, and alter the getters such that the the will return only the specific instance unless the rollup is canonical, where its validator set should be the union of the two sets.

```solidity
function getValidatorSet(address _instance) {
	set = validatorSet[_instance]

	if (isCanonical(_instance)){
		set = set ⋃ validatorSet[MAGIC_CANONICAL_ADDRESS];
	}
	
	return set;
}
```

This alters deposits slightly, as when depositing into the current canonical it should be possible to chose to either go into the validator set of the specific instance, or for that of the canonical.

Because this `canonical` validator set is *moved* when a new rollup becomes canonical, it **must** be valid on the new set if it was valid on the old. Essentially, if you want to use the same `GSE` the validator requirements (not exit delay) are the same, e.g., stake and the data that must be submitted.

If this is not the case, you might have that attesters that were valid on a previous rollup is moved to a new, where they would not have been able to deposit. An example of this, could be that the new one want to increase the amount staked. Unless it goes over the list and validates them individually, it won't know who are valid and who aren't - so the criteria must be kept stable.

To reduce this hurdle slightly, the call to add a new rollup must be explicitly done by the `Governance` such that it is possible to not move funds into a new version where they won't fit (in structure).

Since parts of the storage are not longer directly owned by the rollup, it must alter how it is storing things such as exits. Currently, it relies on fine grained control over the set, being able to remove an attester from the validator set, without deleting their information.

Implications:
- If you need to update the staking parts you are in for pain because it will need a new `GSE` so no fancy automove without completely broken state.
- Pending Chain safety of the "old" chain is reduced around the time of upgrades.

## Stage Two - Governance

This is the stage were we need to alter the `GSE` and other chunks to support requirement 1, 2 and 3.

### Requirement 1 
To satisfy 1, we can extend the `Governance` contract with a whitelist, that only allow the `GSE` to participate. That way, only people staking will potentially have a say. We wish to make this whitelist `toggable` such that it can be turned off if it is desired that not only the block producers should have a say after all.

As long as we require that the only deposits allowed into the `GSE` is for rollups that have been canonical, there is something at stake and only stakers in the end could have voting power.

Note, that because it is not possible for anyone but the `GSE` to deposit into the governance, it is not possible for anyone but the `GSE` to call `proposeWithLock`, which used to be the emergency hatch in the case where the rollup for some reason is not proposing any actions. To ensure that it is still possible to make a proposal outside, we should add a relayer of the `proposeWithLock` on the `GSE`

```solidity
function proposeWithLock(IPayload _proposal, address _to) external override(IGSE) {
	uint256 amount = GOVERNANCE.getConfiguration().proposeConfig.lockAmount;
	STAKING_ASSET.transferFrom(msg.sender, address(this), amount);
	STAKING_ASSET.approve(address(GOVERNANCE), amount);
	GOVERNANCE.proposeWithLock(_proposal, _to);
}
```

Note, that while it is possible to propose this way, the vote itself is still not open to anyone but the `GSE`, which brings us to requirement 2 
### Requirement 2

To support requirement 2, we wish to take any funds that are deposited into the `GSE` and deposit them into the governance, such that they increase the power of the `GSE`. Then we must implement voting power delegation on the `GSE` itself such that it is possible for the stakers to use their voting power.

However, as there was a strong urge to have no-one cast votes for things to occur, the deposit should be default delegate the voting power to the rollup instance. The rollup instance itself is then to implement logic to to decide how it will use its power.

This can be done in a manner similar to what is often done for governance tokens, where we are to keep checkpoints of the voting power of addresses, and update those checkpoints as balance is moved around, updated along with adding or removing validators and slashes. 

For the `canonical` voting power, a special case using the `MAGIC_CANONICAL_ADDRESS` is to be used, note however, that unless there is a separate checkpoint around when the canonical is moved around, it might be the case that the power for a vote in the past is passed along in case of an upgrade (edge case).

The `GSE` must have logic to allow the cast of votes from anyone with voting power, so if a staker does not agree with the rollup, there is a way for him to vote against it.

### Requirement 3

> [!info] Point of discussion
>Is it desired to always require > 2/3 of stake stake to be on the canonical for the proposal to be passable, or is it acceptable that this is bypassed when a proposal is made using the `proposeAndLock`? 

To support requirement 3, we will alter the `GovernanceProposer` such that it any proposals from it will be extended with a check at the end that the stake held in the canonical is >2/3 of the stake in the `GSE` (instance directly + canonical). 

Note, that while >2/3 of the stake might be in the canonical, it does not mean that they all agree. The requirement is offspring from the real requirement that the new rollup will quickly start producing blocks and have "sufficient" security on its pending chain. 

In the case where a proposal is made through the `proposeAndLock` we do **not** enforce this requirement, since it is:
1) expected to be an emergency, and used to save the rollup so we can accept worse performance
2) since the proposal is still to be pushed through by the voting power, it is still only the rollups and sequencers that have a say, so if they disagreed they could simply have ignored it. 

Another interesting implication is in the case where a change is to be made to the `GSE`, it will be incredibly hard to get it added as canonical without also changing the governance proposer, since the governance proposer relies on this >2/3 of stake in the `GSE` and here none of the new stake would be in that `GSE`.

### Other

Beyond this that are directly linked to a single of these requirements, the act of having deposited the funds into the governance after the rollup and `GSE` means that there are significant number of "hoops" to jump through to exit. Namely, the `GSE` might not have a exit delay, but the rollup instance and the `Governance` both. 

So the UX of exiting is pretty horrible, as it will be a number of steps to actually get the funds fully out.

# Change Set

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
- [x] Economics
- [ ] P2P Network
- [ ] DevOps

# Test Plan

Beyond updating a big chunk of the tests that we already have, we need to also add new tests for the `GSE` and for moving to the next canonical rollup.

[^1]: https://i.imgur.com/DO7MHLq.png
