# Publishing TxObjects

|                      |                                   |
| -------------------- | --------------------------------- |
| Issue                | [title](github.com/link/to/issue) |
| Owners               | @just-mitch @LHerskind @Maddiaa0  |
| Approvers            |                                   |
| Target Approval Date | 2024-09-11                        |

## Executive Summary

We currently publish transaction effects to L1. This means we execute the public portion of the transaction, accumulate all of its side effects, and publish those to the L1 contract.

In contrast, we're moving to a world where we simply publish the outputs of the private execution (performed by a user's PXE) and the public call requests.

Further, we are not requiring validators participating in the pending chain to execute transactions, and are merely required to verify the private proofs of transactions in a block that has been proposed.

## Introduction

We first outline the changes needed in various components to support this work.

### Committee Signature Scheme

- Optimistic BLS

To see how we get to this, look at [Pleistarchus](https://github.com/AztecProtocol/aztec-packages/issues/7978).

### What is published, when

A proposer will collect signatures from the committee, and then publish (within a single L1 transaction) the content in blobs and his "proposal" to the rollup contract:

- CallData
  - proposal:
    - numTxs
    - txsHash (a commitment to first nullifiers of all transactions in the proposal)
    - kzgHashes (a commitment to the versioned KZG hashes which include all the transactions of the proposal)
    - inHash
    - GlobalVariables
      - blockNumber
      - slotNumber
      - timestamp
      - coinbase
      - feeRecipient
      - gasSetting (`fee_per_da_gas`, `fee_per_l1_gas`)
  - Proposer sig (ECDSA)
  - Attestations:
    - aggregate BLS sig
    - bitmap for missing signatures
- Blobs
  - Tx1
    - max fee
    - note hashes (from private)
    - nullifiers (from private)
    - l2ToL1Messages (from private)
    - note encrypted logs (from private)
    - encrypted logs (from private)
    - unencrypted logs (from private)
    - public call request 1
      - contract address
      - call context
        - msgSender
        - storageContractAddress
        - functionSelector
        - isDelegateCall
        - isStaticCall
      - args
    - public call request 2
    - ...
  - Tx2
  - ...

> Most of the global variables could be directly populated by L1, but providing it makes it a lot clearer what the reason of failure is if such a one is encountered. Also the `inHash` can be populated by L1.

#### DA Oracle Changes

When the data is to be submitted as part of the same transaction as the block proposal to the L1 contract, we have two variations possible:

1. Remove the data availability oracle in its whole, and simply use the versioned KZG hashes directly
2. Save the versioned KZG hashes in the data availability oracle

Solution 1 is significantly cheaper as it don't update storage. Furthermore, by requiring that the versioned KZG hashes are part of the header provided, we can show the exact KZG hashes using just the transaction and the commitment to the block hash, see `BlockLog.blockHash`.

#### Rollup Contract Changes
> There is probably some 1-off from the `count` `block_number` like values.

```python
struct State:
  pending_proposal_count: uint64;
  pending_slot: uint64;
  proven_block_count: uint64;
  proven_slot: uint64;

struct ProposalLog:
  proposal_hash: bytes32;
  slot: uint256;
  archive: bytes32;

proposals: public(HashMap[uint256, ProposalLog])
state: public(State);

# The old `process`
def propose(proposal, proposer_sig, attestations):
  '''
  Notice that no signatures are checked, all of that is optimistic 
  '''
  assert hash([h for h in tx.blob_versioned_hashes]) == proposal.kzgHashes # Replaces DA oracle
  assert proposal.gas_settings.is_sane() # To be designed
  assert proposal.slot > state.pending_slot and proposal.slot == get_current_slot()
  assert proposal.timestamp == get_time_at_slot(proposal.slot) and proposal.timestamp <= block.timestamp
  assert proposal.block_number == state.pending_proposal_count
  assert proposal.inHash == INBOX.consume(proposal.block_number)

  self.proposals[proposal.block_number] = ProposalLog(sha256(proposal,  proposer_sig, attestations), proposal.slot)
  self.state.pending_proposal_count += 1
  self.state.pending_slot = proposal.slot

def challenge_proposal(proposal, proposer_sig, attestations):
  '''
  Implement challenges for:
  - Bad proposer
  - Bad attestation
  '''
  pass


def submit_proof(proof, archive):
  '''
  Notice that this only supports sequential proofs as we always feed `self.state.proven_archive` as start state.
  '''
  proposal_hashes = []
  block_number_start = self.state.proven_block_count
  end_slot = get_last_slot_in_epoch(get_epoch_from_slot(self.proposals[block_number_start].slot))

  block_number = block_number_start

  for bn in range(block_number_start, block_number_start + EPOCH_LENGTH):
    proposal_log = self.proposals[bn]
    if proposal_log.slot <= end_slot:
      proposal_hashes.append(proposal_log.proposal_hash)
      block_number = bn
    else:
      break

  assert len(proposal_hashes) > 0, 'no proposals'

  prev_archive = self.proposals[self.state.proven_block_count - 1]
  assert proof.verify(prev_archive, proposal_hashes, archive)

  self.payout_fees();

  self.state.proven_slot = proposal_log[-1].slot
  self.state.proven_block_count = block_number + 1
  self.proposals[block_number] = archive
```

- TODO:
  - What are we going to do with stuff like the outhashes? They depend on the execution, so we cannot really do it at the time of the proposal if that is. So we would practically need it to happen with the entire epoch at this point. Might just be another tree to make it cheaper. It gets kinda funky with finding the block number because it depends.

### Forced inclusion of transactions

- Need to fix some notation on what is the "full" proposal etc.
- My syntax is not really valid vyper but I just enjoy writing it that way, sorry not sorry.

```python
struct ForceInclusion:
  nullifier: bytes32
  include_by_slot: uint256
  included: bool

struct ForceInclusionProof:
  proposal: Proposal
  forced_inclusion_index: uint256, 
  block_number: uint256
  membership_proof: bytes32[]

forced_inclusions: public(HashMap[uint256, ForceInclusion])
forced_inclusion_tip: public(uint256)
forced_inclusion_count: public(uint256)

FORCE_INCLUSION_DEADLINE: immutable(uint256)

def initiate_force_include(tx, proof, block_number_proven_against):
  archive = self.proposals[block_number_proven_against].archive
  assert proof.verify(archive, tx)

  self.forced_inclusions[self.forced_inclusion_count] = ForceInclusion(
    nullifier = tx.nullifiers[0], 
    include_by_slot = get_current_slot() + FORCE_INCLUSION_DEADLINE
  )
  self.forced_inclusion_count += 1

def show_included(proposal, forced_inclusion_index, block_number, membership_proof):
  nullifier = self.forced_inclusions[forced_inclusion_index].nullifier

  assert self.proposals[block_number].proposal_hash == proposal.hash()
  assert membership_proof.verify( nullifier,proposal.txs_hash)

  self.forced_inclusions[forced_inclusion_index].nullifier.included = True

  self.progress_forced_inclusion_tip() 

def progress_forced_inclusion_tip():
  cache = self.forced_inclusion_tip
  for i in range(cache, self.forced_inclusion_count):
    if not self.forced_inclusions[i].included:
      return
    self.forced_inclusion_tip = cache

def submit_proof(proof, archive):
  # super.submit_proof(proof, archive)
  
  forced_tip = self.forced_inclusions[self.forced_inclusions_tip]
  assert forced_tip.included_by_slot == 0 or forced_tip.included_by_slot > proposal_hashes[-1].slot, 'force'

def submit_proof_with_force(proof, archive, force_inclusion_proofs):
  # super.submit_proof(proof, archive)

  for fip in force_inclusion_proofs:
    self.show_included(fip)

  forced_tip = self.forced_inclusions[self.forced_inclusions_tip]
  assert forced_tip.included_by_slot == 0 or forced_tip.included_by_slot > proposal_hashes[-1].slot, 'force'
```

### Blob circuits

### Rollup circuits

### Prover interactions

### Keeping track of chain state

How do nodes keep track of the pending archive since they are not published to L1?

### Private kernel verification

Validators need to verify the private kernels

### Transaction invalidation

The rollup should _only_ fail if the private kernel is invalid.

Presently the rollup will fail if any of the following conditions happen:

- Make list

## Interface

Who are your users, and how do they interact with this? What is the top-level interface?

## Implementation

Delve into the specifics of the design. Include diagrams, code snippets, API descriptions, and database schema changes as necessary. Highlight any significant changes to the existing architecture or interfaces.

Discuss any alternative or rejected solutions.

## Change Set

Fill in bullets for each area that will be affected by this change.

- [ ] Cryptography
- [ ] Noir
- [ ] Aztec.js
- [ ] PXE
- [ ] Aztec.nr
- [ ] Enshrined L2 Contracts
- [ ] Private Kernel Circuits
- [ ] Sequencer
- [ ] AVM
- [ ] Public Kernel Circuits
- [ ] Rollup Circuits
- [ ] L1 Contracts
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
