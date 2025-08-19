# Forced Inclusion

|                      |                                    |
| -------------------- | ---------------------------------- |
| Issue                | [title](github.com/link/to/issue)  |
| Owners               | @lherskind                         |
| Approvers            | @just-mitch @aminsammara @Maddiaa0 |
| Target Approval Date | YYYY-MM-DD                         |

# Executive Summary

We propose a method to provide the Aztec network with similar **inclusion** censorship resistance as that of the base-layer.

The mechanism uses a delayed forced inclusion queue on L1, and requires the ability to include valid but failing transactions (many of these changes overlaps with tx-objects). After some delay, proposed blocks are required to include transactions from the queue, and failing to do so will reject the blocks.

The mechanism requires a minimum number of transactions to be included from the forced inclusion queue each epoch. If this minimum is not met then based fallback mode is entered. The based fallback mode needed for the forced inclusion mechanism introduces the concept of a based fallback epoch. During a based fallback epoch, blocks must be proposed and proven in the same transaction (nothing new there vs previous based fallback implementations). 

In this mechanism, any proven based fallback block containing the previously mentioned minimum number of forced inclusion transactions progresses the state to the next based fallback epoch. If the minimum is not met by the end of a based fallback epoch, the block containing the most forced inclusion transactions is finalized, and the state progresses to the next epoch. 

When in based fallback mode, whenever the forced inclusion queue is emptied of all transactions that are required to be included, based fallback mode can be exited. 

# **Implementation**

While we would like most of the updates to be on the contract level, there are some checks that simply cannot be performed at the time where the insertion into the queue is performed.

Namely, while we can check that the private kernel is valid against a specific archive root at the time of queue insertion, we don't know yet how it will alter the state as it depends on the time it gets inserted on L2. As mentioned, there is essentially an upper bound on that from the (anchor block) delay.

For this reason, we need to alter L2 execution and proving circuits, such that they will **not** cause an invalid rollup if a **FORCED** transaction were to fail due to:

1. **Pass but no diff**: Revert in public setup
2. **Pass but no diff**: Fails due to late inclusion
3. **Pass but no diff**: Fails due to stale anchor 
4. **Pass but no diff**: Duplicate nullifiers
5. **Invalid rollup**: Sequencer lies about the sibling paths to make it seem like duplicate nullifiers.

Additionally, on L2 we need the following

1. We bypass the fee payment when the fee payer matches a specific magic address: namely the `FIFPC` address on L2 (an abbreviation for **forced inclusion fee paying contract**)
2. We accumulate the mana spent for txs using the `FIFPC` separately, such that we have 2 values that are outputted from the circuit.
3. We compute a `forced_inclusion_root` that is the root of a tree of the transactions using the `FIFPC` address as fee payer, and verify this root vs. a header input.

For the sake of simplicity, we assume that the above changes are made and describe the high-level architecture changes, before diving into the different aspects.

The idea is as follows

- We take the idea of a delayed queue, that after some delay, forces the blocks to order transactions based on the queue. When inserting into the delayed queue, we can check the private kernel proof (fairly expensive 💸) and we store the transaction hash along with a bit of metadata, e.g., the time at which it must be included, which proposer included the transaction whenever it gets included, etc.
- Forced inclusion transactions must specify the FIFPC as their fee payer on L2. This is used to ensure the mapping “all L1 forced inclusion queue transactions are treated as forced inclusion transactions on L2” holds. The FIFPC handles fee payment for forced inclusion transacitons in a unique way, so forced inclusion transactions do not need to pay L2 mana.
- Headers are amended to include a merkle root of the forced inclusion transactions which they include, as well as the number of forced inclusion transaction they refer to. This needs to be verified in the circuits. This is used to ensure the mapping “all L2 forced inclusion transactions are present in the L1 forced inclusion queue” holds. Together with the previous bullet point, this ensures a 1-to-1 mapping of forced inclusion transactions on L1 and L2.
- At the time of epoch proof inclusion, there is no need to verify anything related to forced inclusion transactions in the L2 blocks, although for simplicity we pass the number of forced inclusion transactions in L2 as a param. It may be simpler to store this as a variable in L1.
- It is not currently imposed where in a block forced inclusion transactions are executed. However, the root on L2 must be constructed using the same ordering as the forced inclusion queue on L1.

Additionally, we add functionality to handle the following:

- Payment of forced inclusion fees happen on L1, and are settled at proof time.
- If not enough forced inclusion transactions (enough is set as `FORCED_INCLUSION_LIVENESS_PARAM`) are popped over the course of 2 epochs, based fallback is triggered.
- In based fallback, blocks are either:
    - immediately accepted if the forced inclusion queue is emptied, or `FORCED_INCLUSION_LIVENESS_PARAM` transactions are popped from the queue.
    - Added to an implicit queue ordered by the number of transactions the block pops from the forced inclusion queue. If no block is immediately accepted during an epoch, the block popping the most transactions can be accepted as final.

**NOTE**: The based fallback transitions are still a work in progress.

# Forced Inclusion Contracts

```python
struct ForceInclusion:
    tx_hash: bytes32
    include_by_epoch: uint256
    fee_paid: uint256 # fee accounting
    proposer: address  # proposer assigned when included in a proposed block

struct ForceInclusionProof:
    forced_inclusion_root : bytes32 # Merkle root of FI txs included in the proposed block
    num_forced_inclusions: uint256 # num leaves covered by the root
    
struct BasedFallbackBlock:
    header: Header
		proof: Proof
    tx_count: uint256
    epoch_forced_inclusion_tx_count: uint256
    archive: bytes32
    fees: FeePayment[EPOCH_LENGTH]

# --- Storage Variables ---
forced_inclusions: public(HashMap[uint256, ForceInclusion])
total_forced_inclusions: public(uint256)
forced_inclusion_proven_tip : public(uint256) # last FI tx proven
forced_inclusion_pending_tip : public(uint256) # last FI tx proposed 

FORCED_INCLUSION_DEADLINE: immutable(uint256)
FIFPC_ADDRESS : immutable(address)

FORCED_INCLUSION_LIVENESS_PARAM: immutable(uint256) # number of FI txs that must be popped per epoch
fallback_primed : bool
based_fallback: bool
based_fallback_leader: BasedFallbackBlock #tracks the nextt based fallback block to be added when in based fallback mode
based_fallback_epoch: uint256

# --- Constructor ---
def __init__(deadline: uint256, fifpc_address: address, liveness_param:uint256):
    self.FORCED_INCLUSION_DEADLINE = deadline
    self.FIFPC_ADDRESS =  fifpc_address  # FIFPC address on L2
    self.FORCED_INCLUSION_LIVENESS_PARAM = liveness_param
		self.fallback_primed = false
		self.based_fallback = false	
		self.based_fallback_epoch = 0	

# --- User-Facing Function ---
@external
def initiate_force_include(
    tx: Tx,
    block_number_proven_against: uint256
    anchor_proof: Proof
):
    assert block_number_proven_against <= self.proven_tip.block_number # here, self.proven_tip returns the block at the tip of the proven chain

    archive = self.proposals[block_number_proven_against].archive
    assert archive != bytes32(0)
    assert anchor_proof.verify(archive, tx) # supposed to verify the tx is valid wrt to the anchor block at block_number_proven_against
		assert tx.fee_payer== self.FIFPC_ADDRESS # verifies FIFPC is used 
		
		# fee accounting
		
		self.total_forced_inclusions += 1
    self.forced_inclusions[self.total_forced_inclusions] = ForceInclusion(
        tx_hash = tx.nullifiers[0],
        include_by_epoch = get_current_epoch() + 1 + self.FORCE_INCLUSION_DEADLINE,
        fee_paid=msg.value
        proposer=empty(address) # proposer assigned later at propose()
    )
    
# --- Proposer Functions ---
@external
def propose(header: Header):
    super.propose(header)
    epoch = self.get_epoch_at(header.global_variables.timestamp)
	  
	  expected_root: bytes32 = get_tree_root(
        self.forced_inclusion_pending_tip, 
        header.num_forced_inclusions
    )# a function that returns the root of the tree corresponding to the forced inclusion transactions in forced_inclusions between pending and pending + fip.num_forced_inclusions. Should match the forced_root function be used in the circuits.
		assert expected_root == header.force_inclusion_root
		
		# fee accounting	
    for i: uint256 in range(fip.num_forced_inclusions):
		    self.forced_inclusion_pending_tip += 1 # progress the pending tip
        forced_inclusions[self.forced_inclusion_pending_tip].proposer= msg.sender
		
		# assert there is no pending forced inclusion transactions in the queue given the proposer tries to propose non-forced inclusion transactions		
    if header.tx_count > fip.num_forced_inclusions && self.forced_inclusion_pending_tip < self.total_forced_inclusions:
				assert self.forced_inclusions[self.forced_inclusion_pending_tip].include_by_epoch > epoch 						

def based_fallback_propose(
		header: Header,
		fip: ForceInclusionProof 
		proof,
    tx_count: uint256,
    epoch_forced_inclusion_tx_count: uint256
    archive: bytes32
    fees: FeePayment[EPOCH_LENGTH]
):
		assert self.based_fallback ==True
    epoch = self.get_epoch_at(header.global_variables.timestamp)
	  assert epoch <= based_fallback_epc
	  
	  # a function that returns the root of the tree corresponding to the forced inclusion transactions in forced_inclusions between pending and pending + fip.num_forced_inclusions. Should match the forced_root function be used in the circuits.
	  expected_root: bytes32 = get_tree_root(
        self.forced_inclusion_pending_tip, 
        fip.num_forced_inclusions
    )
		assert expected_root == fip.force_inclusion_root
	  
	  if epoch_forced_inclusion_tx_count >= min(FORCED_INCLUSION_LIVENESS_PARAM, self.total_forced_inclusions - self.forced_inclusion_proven_tip  : # immediately propose and prove block
			  super.propose(header)
			  super.submit_next_epoch_proof(
		    proof, tx_count, epoch_forced_inclusion_tx_count, archive, fees
		) # note, also passing epoch_forced_inclusion_tx_count to enforce this number is valid. Might be easier ways to track this.
		
				# fee distribution	
				fee_collected: uint256= 0
		    for i: uint256 in range(1, epoch_forced_inclusion_tx_count+1):
		        self.proven_tip += 1 # given epoch has been proven, increase the proven tip of the forced inclusion queue by the number of forced inclusion transactions during the proven epoch
		        fee_collected +=self.forced_inclusions[self.proven_tip].fee_paid
				send(msg.sender, fee_collected);
						# send proposer all fees
	  
	  else: # FORCED_INCLUSION_LIVENESS_PARAM requirement not met, block must wait until end of based fallback epoch. 
			  assert epoch_forced_inclusion_tx_count > based_fallback_leader.epoch_forced_inclusion_tx_count # require new block proposes more forced inclusions than previous block
			  assert header.tx_count == fip.num_forced_inclusions 
			  assert super.verify_basedfallback_proof(
				    header, proof, tx_count, epoch_forced_inclusion_tx_count, archive, fees
				) # don't submit, verify only for now
			  based_fallback_leader = BasedFallbackBlock(
							header,
							proof,
					    tx_count,
					    epoch_forced_inclusion_tx_count,
					    archive,
					    fees
				)# store leader
			  # fee accounting	
		    for i: uint256 in range(1,epoch_forced_inclusion_tx_count+1):
				    forced_inclusions[self.forced_inclusion_pending_tip+i].proposer= msg.sender

@external
def prune():
    super.prune() # Call parent contract's prune logic.
		self.forced_inclusion_pending_tip = self.proven_tip # reset pending tip of forced inclusion queue to last proven transaction
		
def finalize_based_fallback_propose() :
    assert self.based_fallback_epoch < self.get_epoch_at(header.global_variables.timestamp)
		super.propose(self.based_fallback_leader.header)
		super.submit_next_epoch_proof(
		    self.based_fallback_leader.proof, self.based_fallback_leader.tx_count, self.based_fallback_leader.epoch_forced_inclusion_tx_count, self.based_fallback_leader.archive, self.based_fallback_leader.fees
		)
		self.based_fallback_leader = 0
		for i: uint256 in range(1, self.based_fallback_leader.epoch_forced_inclusion_tx_count+1):
		    self.proven_tip += 1 # given epoch has been proven, increase the proven tip of the forced inclusion queue by the number of forced inclusion transactions during the proven epoch
		    fee_collected +=self.forced_inclusions[self.proven_tip].fee_paid
		send(self.based_fallback_leader.header.proposer, fee_collected);
		self.based_fallback_epoch = self.get_epoch_at(header.global_variables.timestamp) +1 # conservatively set based_fallback_epoch to next epoch

		
def exit_based_fallback() :
		# this function should require assertions from an Aztec epoch committee to exit
		self.based_fallback= False
		self.fallback_primed = False 
		based_fallback_leader = 0
		
# --- Internal / View Functions for Forced Inclusion Logic ---
@view
def forced_inclusion_liveness_fault(epoch: uint256, tx_count: uint256, epoch_forced_inclusion_tx_count: uint256) -> bool:
		if tx_count == epoch_forced_inclusion_tx_count:
				return False
		if self.forced_inclusion_pending_tip == self.total_forced_inclusions:
				return False
		if self.forced_inclusions[self.proven_tip + epoch_forced_inclusion_tx_count].include_by_epoch > epoch:
				return False
		if epoch_forced_inclusion_tx_count >= FORCED_INCLUSION_LIVENESS_PARAM: # enough forced inclusion transactions were included this epoch
				return False
		# if all of the above if statements are false, this means the first forced inclusion transaction in the queue after those proven this epoch is also "due to be proven" and that not enough forced inclusion transactions were included this epoch(enough is equivalent to FORCED_INCLUSION_LIVENESS_PARAM). 
		return True		

# --- Overridden Parent Function ---
@overridedef submit_proof(
    proof,
    tx_count: uint256,
    epoch_forced_inclusion_tx_count: uint256
    archive: bytes32
    fees: FeePayment[EPOCH_LENGTH]
):
    assert self.based_fallback == False 
    epoch = self.get_epoch_at(self.get_timestamp_for_slot(self.blocks[self.provenBlockCount].slot_number))
    
    super.submit_next_epoch_proof(
		    proof, tx_count, epoch_forced_inclusion_tx_count, archive, fees
		) # note, also passing epoch_forced_inclusion_tx_count to enforce this number is valid. Might be easier ways to track this.
    
    if forced_inclusion_liveness_fault(epoch, tx_count, epoch_forced_inclusion_tx_count): # violation of the forced inclusion liveness requirement
				****if ****self.fallback_primed == True: # Trigger has already been primed
						self.based_fallback = True # based fallback next epoch
						self.based_fallback_epoch = self.get_epoch_at(header.global_variables.timestamp) +1 # conservatively set based_fallback_epoch to next epoch
				self.fallback_primed = True # primes based fallback mode. This needs to be set to false after based fallback mode is entered. 
    
    # fee distribution	
    for i: uint256 in range(1, epoch_forced_inclusion_tx_count+1):
        self.proven_tip += 1 # given epoch has been proven, increase the proven tip of the forced inclusion queue by the number of forced inclusion transactions during the proven epoch
        fi_fee_half: uint256 =self.forced_inclusions[self.proven_tip].fee_paid /2 # proposer and prover receive half of the fee paid. 50:50 split is arbitrary
        send(self.forced_inclusions[self.proven_tip].proposer, fi_fee_half)
				send(msg.sender, fi_fee_half); # for each fip, send half of the forced inclusion fee paid to the proposer
				# can be made more efficient by batching transfers	  
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

## Proposed FIFPC L2 Execution Changes

All forced inclusion transactions (FI txs) queued on L1 must set the special “forced inclusion Fee Paying Contract”, `FIFPC`, as their fee payer / FPC. The processing of `FIFPC` transactions on L2 will allow the L1 to verify that only FI txs queued on L1 used the `FIFPC`, by forcing a commitment to all `FIFPC` transactions to be reported to L1. With this, we are able to ensure a 1-to-1 mapping of FI txs queued on L1 with all FIFPC transactions processed on L2. The changes to L2 execution are as follows:

1. Create a special “forced inclusion Fee Paying Contract (`FIFPC`). 
    1. `FIFPC` noir contract development: added as part of genesis at "magic" address. (h/t Lasse)
    2. `FeeJuice` noir contract: allow the `FIFPC` magic address to mint funds such that it can cover itself (h/t Lasse)
2. For each block, add a parameter which commits to the number of transactions using `FIFPC`. If the actual number of `FIFPC` transactions differs from the committed number, the block is invalid, which is enforced at proof time. 
3. For each epoch, maintain in L2 state:
    1. An array of `FIFPC` fees collected, let's say `_args.fiFees[]`, similar to `_args.fees[]`, 
    2. A commitment to the FI txs processed this epoch. This will be a proof parameter used to validate processed FI txs on L2 match those processed on L1.
4. **Accounting**: 
    1. Each time the `FIFPC` is used (by an FI tx)
        1. Mint `max_fee` on behalf of the respective FI tx
        2. Calculate actual gas fee, `actual_fee`, as is normal in an FPC
            1. pay `actual_fee` ****to the L2 accounting contract
            2. add the actual gas fee to the `_args.fiFees[]` index corresponding to the current block.
            3. burn `max_fee-actual_fee`.
    2. In `handleRewardsAndFees()` , calculate fee to be collected by proposers and provers as normal, with an additional line of code which decreases the fee to be collected by the corresponding entry in `_args.fiFees[]`
    3. Burn sum(`_args.fiFees[]`)  

## Based Fallback Mechanism Explainer

[The original discussion on based fallback can be found here.](https://www.notion.so/Based-Fallback-Mechanism-249360fc38d080948962d2966ad68fd9?pvs=21) In this section, we describe at a high-level the working design being used for the based fallback.

1. Based Fallback is entered after 2 consecutive epochs where the minimum liveness threshold $L > 0$ is not met. Not meeting the liveness threshold in an epoch means less than $L$  transactions were proposed in that epoch.
    1. Design wise, this can be pseudo enforced by:
        1. disabling normal proof submission, 
        2. having L2 nodes disregard such epochs
        3. forcing proofs to be sent through a special “based_fallback_” function which handles forking the chain.
2. Based fallback proceeds in **based fallback epochs** which currently have the same length as normal epochs, although this may need to be increased to enable permissionless block proposals.
3. Once in based fallback, all block proposals must be accompanied by a proof for that block. 
4. Let there be `$F$` transactions in the forced inclusion queue when based fallback mode is entered. During a based fallback slot, the canonical proposed block is decided according to the following rules:
    1. If any block proposal contains `min(FORCED_INCLUSION_LIVENESS_PARAM, $F$)` forced inclusion transactions, this block is made canonical and the based fallback epoch ends.
    2. Else, if no block proposal contains the `min(FORCED_INCLUSION_LIVENESS_PARAM, $F$)` forced inclusion transactions, at the end of the based fallback slot, the block proposal containing the most forced inclusion transactions is made canonical. Ties are decided by time-priority. 
5. (WIP) Based fallback can be exited if and only if all of the following conditions hold:
    1. The forced inclusion queue has been emptied
    2. The Aztec committee corresponding to the current L1 slot (or perhaps the current Aztec epoch is not dependent on the L1 slot?) sends an aggregated signature to the L1 smart contract, signalling the committee is online. The most straightforward way for this signature to be provided would be through a normal-mode block proposal.
        1. We may want a separate deadline within a based fallback slot for this committee signature to come online. This would avoid honest-but-slow prover work being invalidated close to proving being finished.

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
